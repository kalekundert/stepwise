#!/usr/bin/env python3

import os, pickle, shlex, subprocess as subp
import inform
from more_itertools import one
from pathlib import Path
from pkg_resources import iter_entry_points
from inform import warn
from .protocol import ProtocolIO
from .config import load_config
from .errors import *

class Library:
    """
    Provide access to every protocol available to the user.

    The protocols are organized into "collections", which are groups of related 
    protocols.  Which collections are available to the user at any moment can 
    depend on factors such as the current working directory, the user's 
    configuration settings, which plugins are installed, whether the internet 
    is available, etc.

    The primary role of the library is to search through every available 
    collection for protocols matching a given "tag".  Tags are fuzzy patterns 
    meant to be succinct (i.e. easily typed on the command line) yet capable of 
    specifically identifying any protocol.  See `match_tag()` for a complete 
    description of the tag syntax.

    Strictly speaking, collections are groups of "entries" rather than 
    protocols.  Entries are protocol factories.  For the example of a 
    collection representing a directory, each entry in that collection would 
    represent a file in that directory.  The actual protocol instances would 
    come from the entries either reading or executing those files.

    Collections and entries are intended to be highly polymorphic, so that many 
    different means of accessing protocols (e.g. files, plugins, network 
    drives, websites, etc.) can be supported.
    """

    def __init__(self):
        self.collections = []
        config = load_config()

        def add(collection, i=None):
            is_available = collection.is_available()
            is_unique = collection.is_unique(self.collections)
            is_ignored = collection.name in config.search.ignore

            if is_available and is_unique and not is_ignored:
                self.collections.insert(
                        len(self.collections) if i is None else i,
                        collection,
                )
        
        # Add directories found above the current working directory.
        cwd = Path.cwd().resolve()
        for parent in (cwd, *cwd.parents):
            for name in config.search.find:
                add(PathCollection(parent/name))

        # Add specific directories specified by the user.
        for dir in config.search.path:
            add(PathCollection(dir))

        # Add directories specified by plugins.
        plugins = sorted(
                iter_entry_points('stepwise.protocols'),
                key=lambda x: (
                    x.module_name == 'stepwise',
                    x.module_name,
                    x.name
                ),
        )
        for plugin in plugins:
            add(PluginCollection(plugin))

        # Add the current working directory.

        # Do this after everything else, so it'll get bumped if we happen to be 
        # in a directory represented by one of the other collections.  But put 
        # it ahead of all the other collections, so that tags are evaluated for 
        # local paths before anything else.

        add(CwdCollection(), 0)

    def find_entries(self, tag):
        """
        Yield the best-scoring entries matching the given tag.
        """
        scored_entries = [
                scored_entry
                for collection in self.collections
                for scored_entry in collection.find_entries(tag)
        ]
        no_score = object()
        best_score = max((x for x, _ in scored_entries), default=no_score)
        return [
                entry
                for score, entry in scored_entries
                if score == best_score
        ]

    def find_entry(self, tag):
        """
        Return the single entry matching the given tag.

        If there are either zero or multiple entries that match the given 
        tag, an exception will be raised.
        """
        entries = self.find_entries(tag)
        return one(
                entries,
                NoProtocolsFound(tag, self.collections),
                MultipleProtocolsFound(tag, entries),
        )

class Collection:
    """
    Abstract base class representing a group of related protocols.
    """

    def __init__(self, name):
        self.name = str(name)
        self.entries = None

    def is_available(self):  # (abstract)
        """
        Return True if the protocols in this collection can be accessed.

        For example, if the collection represents a network drive, return true 
        if internet is connected and the drive is responsive.
        """
        raise NotImplementedError

    def is_unique(self, collections):
        """
        Return False if another collection representing all the same protocols 
        as this one is present in the given list.
        
        Sometimes it's possible for there to be multiple collections 
        representing, for example, the same directory.  This method is used to 
        remove the duplicates, which would otherwise cause problems.
        """
        return not any(self.name == x.name for x in collections)

    def find_entries(self, tag):
        """
        Yield any entries matching the given tag.

        This method can be overridden in subclasses.  By default, it caches a 
        list of all the entries in the collection, then searches that list 
        using `match_tag()`.
        """
        if self.entries is None:
            self.entries = list(self._load_entries())

        for entry in self.entries:
            if score := match_tag(tag, entry.full_name):
                yield score, entry

    def _load_entries(self):  # (abstract)
        """
        Yield all of the entries in this collection.
        """
        raise NotImplementedError

class PathCollection(Collection):
    """
    Provide access to protocols stored as files within a directory on the local 
    filesystem.

    Be careful to avoid using this collection on directories it wasn't meant 
    for.  Every file contained in any level of subdirectory is considered a 
    protocol (unless ignored, see below).  If this collection were applied to a 
    directory containing lots of non-protocol files, it could make it harder 
    for the user to specify real protocols.  This collection could also be very 
    expensive if applied to a large directory (e.g. ~), because it has to build 
    a complete list of all its protocols in order to perform searches.

    If the directory (or any of its subdirectories) contain a file called 
    `.stepwiseignore`, it can specify paths that should not be considered 
    protocols.  This file has the exact same syntax as the more well-known 
    `.gitignore`.
    """

    def __init__(self, root, name=None):
        self.root = Path(root).resolve()
        super().__init__(name or str(self.root))

    def is_available(self):
        return self.root.exists()

    def _load_entries(self):
        # I'd like to replace this with something that understands the same 
        # syntax as `.gitignore` files, but I can't find a library to do that! 
        def ignore(p):
            return p.startswith('.') or p.startswith('__')

        for root, subdirs, files in os.walk(self.root):
            subdirs[:] = sorted(d for d in subdirs if not ignore(d))

            for file in sorted(files):
                if ignore(file): continue

                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(self.root)
                yield self._load_entry(rel_path)

    def _load_entry(self, rel_path):
        return PathEntry(self, rel_path)

class CwdCollection(PathCollection):
    """
    Provide access to protocols stored as files within the current working 
    directory.

    The current working directory can't be treated as a regular directory (see 
    `PathCollection`) because it can be expected to contain a large number of 
    non-protocol files.  To avoid the problems this could cause, any protocols 
    in the current directory must be specified using complete paths (including 
    the file extension).
    """

    def __init__(self):
        super().__init__(Path.cwd())

    def find_entries(self, tag):
        if tag is None:
            return  # Yield nothing.

        rel_path = Path(tag)
        abs_path = self.root / rel_path

        if abs_path.exists():
            yield match_tag(tag, rel_path), self._load_entry(rel_path)

class PluginCollection(PathCollection):
    """
    Provide access to protocols installed as plugins to stepwise.
    """

    def __init__(self, plugin):
        super().__init__(
                root=plugin.load(),
                name=f'{plugin.module_name}.{plugin.name}',
        )
    def _load_entry(self, rel_path):
        return PluginEntry(self, rel_path)

class Entry:
    """
    Abstract base class representing a factory for a single protocol.

    The most important method of this class is `load_protocol()`, which 
    instantiates and returns a `ProtocolIO` instance from whatever input the 
    entry needs (e.g. files, web requests, etc).
    """

    def __init__(self, collection, name):
        self.collection = collection
        self.name = str(name)

    @property
    def full_name(self):
        from os.path import normpath, join
        return normpath(join(self.collection.name, self.name))

    def load_protocol(self):  # (abstract)
        """
        Instantiate a `ProtocolIO` instance corresponding to this entry.

        Generally, the correct way to do this is by calling one of the 
        `ProtocolIO.from_*()` methods.  It should rarely (if ever) be necessary 
        to call the `ProtocolIO` constructor directly.
        """
        raise NotImplementedError

class PathEntry(Entry):

    def __init__(self, collection, relpath):
        self.relpath = Path(relpath)
        self.path = collection.root / relpath
        super().__init__(collection, self.relpath.with_suffix(''))

    def load_protocol(self, args):
        try:
            with inform.set_culprit(self.name):
                self.check_version_control()
        except VersionControlWarning as err:
            err.report(informant=warn)

        return ProtocolIO.from_file(self.path, args, name=self.name)

    def check_version_control(self):
        return check_version_control(self.path)

class PluginEntry(PathEntry):

    def check_version_control(self):
        pass

def match_tag(tag, name):
    """
    Indicate if the given tag matches the given name.

    The purpose of a tag is to succinctly identify a protocol by name.  A 
    protocol's name can be anything, but is generally something like a 
    filesystem path.  To be more specific, names have two parts:

    - The name of the collection containing the protocol.  If the collection is 
      a directory, this is the path to that directory.  If the collection is a 
      plugin, this is the name of the plugin.  Different kinds of collections 
      may have different naming conventions.

    - The name of the protocol within its collection.  Typically this is the 
      path to the protocol within the collection, although again, different 
      collections may have different naming conventions.

    A match is determined by splitting both the tag and the name into parts 
    delimited by `os.sep` (e.g. '/' on Unix systems).  Each part in the tag 
    must match a part in the name, and the last part in the tag must match the 
    last part of the name.  If the tag has multiple parts, the corresponding 
    parts of the name must appear in the same order (but not necessarily 
    consecutively).  Individual parts are matched using the `fnmatch` syntax, 
    e.g. '*' to match anything.  For convenience, '..' can be used instead of 
    '*', since '*' often needs to be escaped to avoid shell expansion.  Partial 
    matches are allowed, but full matches are preferred.

    Each successful match is given a score indicating how good the match is.  
    Everything else being equal, one match will score higher than another if:

    - More of the rightmost parts of the name are matched.  For example, 
      the tag 'a/b' matches '_/a/_/b' better than 'a/_/_/b', because the 'a' is 
      further to the right in the former name.

    - An individual part is matched better.  Best is if the whole part is 
      matched.  Second best is if the beginning of the part is matched.  Third 
      best is if the middle of the part is matched.  Worst is if the part isn't 
      matched.  For example, the tag `a` matches `a` better than `ab`, and `ab` 
      better than `ba`.

    Arguments:
        tag (str): The tag.  If `None`, every name will match.
        name (str): The name to compare the tag against.

    Returns:
        A score indicating whether the name matches the tag, and if so, how 
        good the match is.  The score object is not guaranteed to have any 
        particular type, but is guaranteed to have the following properties:

        - It will evaluate to `True` if there was a match and `False` 
          otherwise.

        - It will support the comparison operators, and the best match will 
          evaluate greater than any other match.
            
    Examples:
        >>> from stepwise import match_tag
        >>> match_tag('pcr', '/home/rfranklin/pcr')
        (3)
        >>> match_tag('rf/pcr', '/home/rfranklin/pcr')
        (3, 2)
        >>> match_tag('rf', '/home/rfranklin/pcr')
        ()
    """
    from os import sep 
    from os.path import normpath
    from fnmatch import fnmatch

    if tag is None:
        return (0,)

    def match_parts(name_parts, tag_parts, scores=(), required=False):
        if not tag_parts: return scores
        if not name_parts: return ()

        name_part = name_parts[-1]
        tag_part = tag_parts[-1]

        if fnmatch(name_part, f'{tag_part}'):
            score = 3
        elif fnmatch(name_part, f'{tag_part}*'):
            score = 2
        elif fnmatch(name_part, f'*{tag_part}*'):
            score = 1
        else:
            score = 0

        if score > 0:
            return match_parts(
                    name_parts[:-1],
                    tag_parts[:-1], 
                    (*scores, score),
            )
        else:
            if required: return ()
            return match_parts(
                    name_parts[:-1],
                    tag_parts,
                    (*scores, score),
            )

    name_parts = normpath(name).split(sep)
    tag_parts = normpath(tag).replace('..', '*').strip('*').split(sep)

    return match_parts(name_parts, tag_parts, required=True)

def check_version_control(path):
    """
    Raise a warning if the given path has changes that haven't been committed.
    """
    # Check that the file is in a repository.
    p1 = subp.run(
            shlex.split('git rev-parse --show-toplevel'),
            cwd=path.parent,
            capture_output=True, text=True
    )
    if p1.returncode != 0:
        raise VersionControlWarning(f"not in a git repository!", culprit=inform.get_culprit() or path)

    git_dir = Path(p1.stdout.strip()).resolve()
    git_relpath = path.relative_to(git_dir)

    # Check that the file is being tracked.
    p2 = subp.run(
            ['git', 'log', '-n1', '--pretty=format:%H', '--', git_relpath],
            cwd=git_dir,
            capture_output=True,
    )
    if p2.returncode != 0:
        raise VersionControlWarning(f"not committed", culprit=inform.get_culprit() or path)

    # Check that the file doesn't have any uncommitted changes.
    p3 = subp.run(
            shlex.split('git ls-files --modified --deleted --others --exclude-standard'),
            cwd=git_dir,
            capture_output=True, text=True,
    )
    if str(git_relpath) in p3.stdout:
        raise VersionControlWarning(f"uncommitted changes", culprit=inform.get_culprit() or path)