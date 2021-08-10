#!/usr/bin/env python3

import sys, os, re, pickle, shlex, functools
import appcli
import inform
from pathlib import Path
from contextlib import contextmanager
from traceback import print_exc
from fnmatch import fnmatch
from voluptuous import Schema
from more_itertools import one
from inform import warn, error, codicil, set_culprit, get_culprit
from .protocol import Protocol
from .printer import format_protocol
from .format import preformatted
from .config import StepwiseConfig
from .utils import load_and_sort_plugins
from .errors import *

PICKLE_HEADER = pickle.dumps(None)[0]

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
    specifically identifying any protocol.  See `_match_tag()` for a complete 
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
    __config__ = [StepwiseConfig]

    ignore_globs = appcli.param(
            'search.ignore',
            cast=Schema([str]),
            default=[],
    )
    local_paths = appcli.param(
            'search.find',
            cast=Schema([str]),
            default=['protocols'],
    )
    global_paths = appcli.param(
            'search.path',
            cast=Schema([str]),
            default=[],
    )

    _singleton = None

    def __init__(self):
        self.collections = []

        def add(collection, i=None):
            is_available = collection.is_available()
            is_unique = collection.is_unique(self.collections)
            is_ignored = any(
                    fnmatch(collection.name, x)
                    for x in self.ignore_globs
            )

            if is_available and is_unique and not is_ignored:
                self.collections.insert(
                        len(self.collections) if i is None else i,
                        collection,
                )
        
        # Add directories found above the current working directory.
        cwd = Path.cwd().resolve()
        for parent in (cwd, *cwd.parents):
            for name in self.local_paths:
                add(PathCollection(parent/name))

        # Add specific directories specified by the user.
        for dir in self.global_paths:
            add(PathCollection(dir))

        # Add directories specified by plugins.
        for plugin in load_and_sort_plugins('stepwise.protocols'):
            try:
                add(PluginCollection(plugin))
            except AttributeError as err:
                warn(f"no protocol directory specified for '{plugin.module_name}.{plugin.name}' plugin.")
                codicil(str(err))

        # Add the current working directory.

        # Do this after everything else, so it'll get bumped if we happen to be 
        # in a directory represented by one of the other collections.  But put 
        # it ahead of all the other collections, so that tags are evaluated for 
        # local paths before anything else.

        add(CwdCollection(), 0)

    @classmethod
    def from_singleton(cls):
        # Use `Library._singleton` instead of `cls._singleton` so we don't end 
        # up with multiple singletons.
        if Library._singleton is None:
            Library._singleton = cls()
        return Library._singleton

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
        using `_match_tag()`.
        """
        if self.entries is None:
            self.entries = list(self._load_entries())

        for entry in self.entries:
            if score := _match_tag(tag, entry.full_name):
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
        self.root = Path(root).expanduser().resolve()
        super().__init__(name or str(self.root))

    def __repr__(self):
        return f'{self.__class__.__name__}({self.root!r})'

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
        pass

    def __repr__(self):
        return f'{self.__class__.__name__}()'

    @property
    def root(self):
        # Recalculate the current working directory on each access, because it 
        # might change.
        return Path.cwd()

    @property
    def name(self):
        return self.root

    def find_entries(self, tag):
        if tag is None:
            return  # Yield nothing.

        rel_path = Path(tag)
        abs_path = self.root / rel_path

        if abs_path.exists():
            yield _match_tag(tag, rel_path), self._load_entry(rel_path)

class PluginCollection(PathCollection):
    """
    Provide access to protocols installed as plugins to stepwise.
    """

    def __init__(self, plugin):
        super().__init__(
                root=plugin.protocol_dir,
                name=f'{plugin.entry_point.module_name}.{plugin.entry_point.name}',
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

    def __repr__(self):
        return f'{self.__class__.__name__}({self.collection!r}, {self.name!r})'

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
            with set_culprit(self.name):
                self.check_version_control()
        except VersionControlWarning as err:
            err.report(informant=warn)

        return ProtocolIO.from_file(self.path, args, name=self.name)

    def check_version_control(self):
        return _check_version_control(self.path)

class PluginEntry(PathEntry):

    def check_version_control(self):
        pass

class ProtocolIO:
    """
    Represent a user-provided protocol that may or may not have been 
    successfully parsed.

    `ProtocolIO` objects have two primary attributes:

    - `errors`
    - `protocol`

    The `errors` attribute is a count of the number of errors that have been 
    generated so far in the pipeline.  If there have been any errors, 
    `protocol` will be a string containing the raw text for the protocol.  This 
    text won't be properly formatted, but it should help the user figure out 
    what the problems were.  If there haven't been any errors, `io.protocol` 
    will be a fully initialized `stepwise.Protocol` instance representing the 
    protocol.

    The methods of this class should never raise.  Any errors that occur should 
    be caught and reported to stderr.
    """
    ok_to_raise = False
    all_errors = 0

    def no_errors(f):
        """
        Guarantee that the decorated function will not raise any exceptions.

        This decorator is meant to be used on ``from_*()`` functions, which 
        attempt to load a protocol and return a `ProtocolIO` instance 
        indicating success or failure.  If an exception is raised in one of 
        these function, the decorator will handle it and return a `ProtocolIO` 
        instance indicating failure.

        Note that if one `@no_errors`-decorated function is called by another, 
        the former will be allowed to raise exceptions normally.  Exceptions 
        are only caught for the top level function call.
        """

        @classmethod
        @functools.wraps(f)
        def wrapper(cls, *args, **kwargs):
            ok_to_raise_prev = cls.ok_to_raise
            cls.ok_to_raise = True

            try:
                io = f(cls, *args, **kwargs)

            except Exception as err:
                if cls.ok_to_raise:
                    raise

                io = cls("", 1)

                if isinstance(err, StepwiseError):
                    err.report()
                else:
                    print_exc(file=sys.stderr)

            cls.ok_to_raise = ok_to_raise_prev
            cls.all_errors += io.errors
            return io

        return wrapper


    def __init__(self, protocol=None, errors=0):
        self.protocol = protocol if protocol is not None else Protocol()
        self.errors = errors

    @no_errors
    def from_stdin(cls):
        """
        Read a protocol from stdin.

        This is meant mostly for interprocess communication via pipes.  If 
        stdin is attached to a pipe (i.e. not a TTY), expect it to contain a 
        pickled `ProtocolIO` instance.  This format allows arbitrary python 
        objects to be passed between processes, and prevents the need to parse 
        any protocol steps more than once.
        """

        # Don't try to read from a TTY, because it will hang until the user 
        # enters an EOF.
        if sys.stdin.isatty():
            return cls()

        return cls.from_bytes(sys.stdin.buffer.read())

    @no_errors
    def from_library(cls, tag, args=None, library=None):
        """
        Read a protocol matching the given tag.

        See `Library` for a description of how tags are used to identify and 
        load protocols.
        """
        library = library or Library.from_singleton()
        return library.find_entry(tag).load_protocol(args or [])

    @no_errors
    def from_file(cls, path, args, name=None):
        """
        Read a protocol from the given path.

        There are a few ways for a path to be interpreted as a protocol:

        - If the path is executable, it is executed.  The script can write to 
          stdout either the text of a protocol or a pickled `ProtocolIO` 
          instance.  (The latter may happen if the script invokes stepwise.)

        - If the path has the '*.txt' extension, it will be read and parsed 
          into a `Protocol` instance.

        - Otherwise, the file will be taken as an "attachment".  A simple 
          protocol will be created containing the attachment.
        """

        def from_file(path, args, name):
            path = Path(path)
            cmd = str(path), *args

            # If the path is a python file, run it without starting a new 
            # process.  Starting new python processes is quite expensive, so 
            # while this adds some complexity, it's an important optimization 
            # for protocols built from lots of python scripts.
            if path.suffix == '.py':
                p = _run_python_script(path, args)
                if p.returncode != 0:
                    raise LoadError(f"command {shlex.join(cmd)!r} failed with status {p.returncode}")
                return cls.from_bytes(p.stdout)

            # If the path is a text file, read it:
            if path.suffix == '.txt':
                return cls.from_text(path.read_text())

            # If the path is a script, run it:
            try:
                from subprocess import run, PIPE, DEVNULL

                p = run(cmd, stdout=PIPE, stdin=DEVNULL)
                if p.returncode != 0:
                    raise LoadError(f"command {shlex.join(cmd)!r} with status {p.returncode}")

                return cls.from_bytes(p.stdout)

            # Otherwise, attach the file to a new protocol:
            except OSError:
                io = cls()
                io.protocol = Protocol(
                        steps=[preformatted(f"<{name or path.name}>")],
                )
                io.protocol.attachments = [path]
                return io

        with inform.set_culprit(name or path):
            io = from_file(path, args, name)

        if not io.errors:
            io.protocol.set_current_date()
            io.protocol.set_current_command(name, args)

        return io

    @no_errors
    def from_bytes(cls, bytes):
        from io import BytesIO
        from pickle import UnpicklingError

        ios = []
        unread_bytes = bytes

        # Byte streams (such as stdin) can consist of any number of pickled 
        # `ProtocolIO` instances followed optionally by a text protocol.  The 
        # most common case is for stdin to consist of a single pickle, 
        # corresponding to the output from the previous command in a pipeline.  
        # More interesting behavior is possible if you're using `zsh` with the 
        # MULTIOS option enabled (the default), which allows processes to get 
        # stdin from multiple sources (e.g. pipes, redirects, heredocs).
        # 
        # The text protocol must come last because there's no way to tell how 
        # big it's supposed to be.  So when we encounter bytes that can't be 
        # interpreted as a pickle, we read to the end of the stream and try to 
        # parse it as a text protocol.
        # 
        # It's possible for stdin to be empty, e.g. if there are nested 
        # stepwise processes (e.g. if a protocol calls stepwise itself).  In 
        # this case, the outer process will read stdin, and the inner process 
        # will have nothing to read.

        while unread_bytes:
            unread_buffer = BytesIO(unread_bytes)
            header_byte = unread_buffer.getbuffer()[0]

            # Check the pickle header to decide whether or not this is a 
            # pickle.  Note that pickle itself can't do this robustly, because 
            # protocol=0 doesn't have a header.  We know that we're using a 
            # binary pickle protocols, though, so we can make this check.

            if header_byte == PICKLE_HEADER:
                try:
                    io = pickle.load(unread_buffer)
                except Exception as err:
                    raise LoadError(str(err)) from err

                if not isinstance(io, cls):
                    raise LoadError(f"unpickled {io.__class__.__name__!r}, expected {cls.__name__!r}")

                ios.append(io)

            else:
                io = cls.from_text(unread_bytes.decode())
                ios.append(io)
                break

            unread_bytes = unread_buffer.read()

        return cls.merge(*ios)

    @no_errors
    def from_text(cls, text):
        """
        Read a protocol from the given text.

        See `Protocol.parse()` for more information.  This function adds some 
        additional error handling and sanity checking.
        """
        io = cls()

        try:
            io.protocol = Protocol.parse(text)

        except ParseError as err:
            if not cls.all_errors:
                warn("the protocol could not be properly rendered due to error(s):")
            err.report(informant=warn)

            io.protocol = err.content
            io.errors = 1

        else:
            io.protocol.set_current_date()

            if not io.protocol.steps:
                warn("protocol is empty.", culprit=inform.get_culprit())

        return io

    @no_errors
    def merge(cls, *others):
        if not others:
            return cls()

        io = cls()
        io.errors = sum(x.errors for x in others)

        if not io.errors:
            io.protocol = Protocol.merge(*(x.protocol for x in others))
        else:
            # When merging with the empty protocol created by default if stdin 
            # is empty, an extraneous newline will be added to the front of the 
            # protocol.  The strip() call deals with this.
            def str_from_protocol_or_error(p):
                return p if isinstance(p, str) else format_protocol(p)

            protocol_strs = [
                    str_from_protocol_or_error(x.protocol)
                    for x in others
            ]
            io.protocol = '\n'.join(protocol_strs).strip()

        return io

    def make_quiet(self, quiet):
        """
        Helper function to implement the `--quiet` flag.
        """
        if quiet and not self.errors:
            self.protocol.clear_footnotes()
    
    def set_current_date(self):
        if not self.errors:
            self.protocol.set_current_date()

    def to_stdout(self, force_text=False):
        """
        Write the protocol to stdout.

        If stdout is attached to a pipe (i.e. not a TTY), write the pickled 
        `ProtocolIO` instance.  The command attached to the pipe (assumed to 
        be a stepwise command) can recover this instance using 
        `ProtocolIO.from_stdin()`.  This format allows arbitrary python 
        objects to be passed between processes, and prevents the need to parse 
        any protocol steps more than once.

        Otherwise, print the formatted protocol to stdout for the user to see.  
        This behavior can also be forced with the `force_text` argument.
        """
        if sys.stdout.isatty() or force_text:
            from pydoc import pager
            from .printer import format_protocol

            out = format_protocol(self.protocol) \
                    if not self.errors else self.protocol
            pager(out + '\n')

        else:
            # Raise if there's a broken pipe error.
            from signal import signal, SIGPIPE, SIG_DFL
            signal(SIGPIPE, SIG_DFL)

            try:
                pickle.dump(self, sys.stdout.buffer)

            # If the pipe closed while we were making the protocol (e.g. if it 
            # hit an early error), there's no point outputting anything.  Just 
            # exit gracefully.
            except BrokenPipeError:
                return

            # Pickling can fail, e.g. if the protocol has non-pickle-able 
            # attributes, and can raise any kind of exception.  If this 
            # happens, record the error and output an empty `ProtocolIO`:
            except Exception as err:
                print_exc(file=sys.stderr)
                io_err = ProtocolIO('', 1)
                pickle.dump(io_err, sys.stdout.buffer)

    del no_errors

def load(command, library=None):
    tag, *args = \
            shlex.split(command) \
            if isinstance(command, str) else \
            map(str, command)
    return ProtocolIO.from_library(tag, args, library=library)

def load_file(path, args=None):
    return ProtocolIO.from_file(path, args)

def load_text(text, args=None):
    return ProtocolIO.from_text(text, args)

def read_merge_write_exit(io, *, quiet=False, force_text=False):
    # It's most performant to load the protocol specified on the CLI before 
    # trying to read a protocol from stdin.  The reason is subtle, and has to 
    # do with the way pipes work.  For example, consider the following 
    # pipeline:
    #
    #   sw pcr ... | sw kld ...
    #
    # Although the output from `sw pcr` is input for `sw kld`, the two commands 
    # are started by the shell at the same time and run concurrently.  However, 
    # `sw kld` will be forced to wait if it tries to read from stdin before `sw 
    # pcr` has written to stdout.  With this in mind, it make sense for `sw 
    # kld` to do as much work as possible before reading from stdin.

    io.make_quiet(quiet)
    io.set_current_date()

    io_stdin = ProtocolIO.from_stdin()
    io_stdout = ProtocolIO.merge(io_stdin, io)
    io_stdout.to_stdout(force_text)
    sys.exit(io_stdout.errors)


def _match_tag(tag, name):
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
        >>> from stepwise import _match_tag
        >>> _match_tag('pcr', '/home/rfranklin/pcr')
        (3)
        >>> _match_tag('rf/pcr', '/home/rfranklin/pcr')
        (3, 2)
        >>> _match_tag('rf', '/home/rfranklin/pcr')
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

def _run_python_script(path, args):
    """
    Run the given python script without launching a new process.

    Starting a python process is expensive, so when we need to run a python 
    script, we can save a lot of time by running it in directly in this 
    process.  In order for this to work, though, we need to temporarily 
    configure this process to look like a new one:

    - Replace `sys.path[0]` with the directory of the script being executed.  
      This allows the script to use local imports.
    - Put the desired arguments in `sys.argv`.
    - Set `__name__` to `'__main__'`.
    - Catch `SystemExit` exceptions.
    - Replace the stdout file descriptor with a pipe, so that we can read any 
      output generated by the script no matter how it's generated.
    - Replace the stdin file descriptor with an empty pipe, so that the script 
      read input on stdin that's meant for us.

    Returns:
        code: int
        stdout: bytes

    Note that stderr is not captured.
    """
    from runpy import run_path
    from traceback import print_exc
    from subprocess import CompletedProcess

    argv = [str(path), *args]
    dir = path.parent.resolve()
    p = CompletedProcess(argv, 0)

    with \
            _capture_stdout() as stdout, \
            _preserve_stdin(), \
            _munge_sys_argv(argv), \
            _munge_sys_path(dir) \
    :
        try:
            run_path(str(path), run_name='__main__')

        except Exception as err:
            print_exc(file=sys.stderr)
            p.returncode = 1

        except SystemExit as err:
            # We need to handle SystemExit as if we were the python 
            # interpreter.  From the python documentation:
            #
            #    If [err.code] is an integer, it specifies the system exit 
            #    status (passed to C's exit() function); if it is None, the 
            #    exit status is zero; if it has another type (such as a 
            #    string), the object's value is printed and the exit status is 
            #    one.
            #
            # https://docs.python.org/3/library/exceptions.html?highlight=systemexit#SystemExit

            if isinstance(err.code, int):
                p.returncode = err.code
            elif err.code is None:
                p.returncode = 0
            else:
                print(err.code, file=sys.stderr)
                p.returncode = 1

    p.stdout = stdout.getvalue()
    assert isinstance(p.returncode, int), repr(p.returncode)
    return p

@contextmanager
def _capture_stdout():
    from io import BytesIO
    from threading import Thread

    out = BytesIO()

    def replace_stdout(fd):
        # Flush any pending output.
        sys.stdout.flush()

        # Replace stdout with the given file descriptor.
        os.dup2(fd, fd_stdout)
        os.close(fd)

    def read_pipe():
        f = os.fdopen(fd_pipe_read, 'rb')

        # Read (blocking) until the pipe is closed.
        out.write(f.read())
        f.close()

    # Save the original stdout.
    fd_stdout = sys.stdout.fileno()
    fd_stdout_dup = os.dup(fd_stdout)

    # Replace stdout with a pipe.
    fd_pipe_read, fd_pipe_write = os.pipe()
    replace_stdout(fd_pipe_write)

    # Read the pipe from a background thread, to prevent the pipe buffer from 
    # filling up (which would hang the program).
    p = Thread(target=read_pipe)
    p.start()

    try:
        yield out

    finally:
        # Restore stdout.  This also closes the writing end of pipe, because it 
        # overwrites the last file descriptor pointing to it.  In turn, this 
        # allows the background thread to finish reading.
        replace_stdout(fd_stdout_dup)
        p.join()

@contextmanager
def _preserve_stdin():
    # Save the original stdin.
    fd_stdin = sys.stdin.fileno()
    fd_stdin_dup = os.dup(fd_stdin)

    # Make a pipe to replace stdin with.
    r, w = os.pipe()
    os.dup2(r, fd_stdin)

    # Close the pipe, so there's nothing to read.
    os.close(w)

    try:
        yield

    finally:
        # Restore stdout.
        os.dup2(fd_stdin_dup, fd_stdin)

@contextmanager
def _munge_sys_argv(argv):
    saved_argv = sys.argv
    sys.argv = [str(x) for x in argv]
    try:
        yield
    finally:
        sys.argv = saved_argv

@contextmanager
def _munge_sys_path(dir):
    sys.path.append(str(dir))
    try:
        yield
    finally:
        sys.path.pop()

def _check_version_control(path):
    """
    Raise a warning if the given path has changes that haven't been committed.
    """
    from subprocess import run

    # Check that the file is in a repository.
    p1 = run(
            shlex.split('git rev-parse --show-toplevel'),
            cwd=path.parent,
            capture_output=True, text=True
    )
    if p1.returncode != 0:
        raise VersionControlWarning(f"not in a git repository!", culprit=get_culprit() or path)

    git_dir = Path(p1.stdout.strip()).resolve()
    git_relpath = path.relative_to(git_dir)

    # Check that the file is being tracked.
    p2 = run(
            ['git', 'log', '-n1', '--pretty=format:%H', '--', git_relpath],
            cwd=git_dir,
            capture_output=True,
    )
    if p2.returncode != 0:
        raise VersionControlWarning(f"not committed", culprit=get_culprit() or path)

    # Check that the file doesn't have any uncommitted changes.
    p3 = run(
            shlex.split('git ls-files --modified --deleted --others --exclude-standard'),
            cwd=git_dir,
            capture_output=True, text=True,
    )
    if str(git_relpath) in p3.stdout:
        raise VersionControlWarning(f"uncommitted changes", culprit=get_culprit() or path)

