#!/usr/bin/env python3

import sys
import os
import pickle
import shlex
import arrow
import re
import textwrap
import io
import subprocess as subp
import inform
import shutil
from nonstdlib import plural, indices_from_str, pretty_range as str_from_indices
from more_itertools import one
from copy import copy
from pathlib import Path
from pkg_resources import iter_entry_points
from inform import warn, error
from traceback import print_exc
from .config import config
from .utils import *

class Protocol:
    BLANK_REGEX = r'^\s*$'
    DATE_FORMAT = 'MMMM D, YYYY'
    COMMAND_REGEX = r'^[$] (.+)'
    STEP_REGEX = r'^(- |\s*\d+\. )(.+)'
    FOOTNOTE_HEADER_REGEX = r'Notes?:|Footnotes?:'
    FOOTNOTE_REGEX = r'\[(\d+(?:[-,]\d+)*)\]'
    FOOTNOTE_DEF_REGEX = fr'^({FOOTNOTE_REGEX} )(.+)'
    INDENT_OR_BLANK_REGEX = lambda n: fr'^({" "*n}|\s*$)(.*)$'

    @classmethod
    def from_anything(cls, x):
        from collections.abc import Iterable

        if isinstance(x, Protocol):
            return x
        if isinstance(x, str):
            return cls(steps=[x])
        if isinstance(x, Iterable):
            return cls(steps=x)

        raise ParseError(f"cannot interpret {x!r} as a protocol")

    def __init__(self, *, date=None, commands=None, steps=None, footnotes=None):
        self.date = date
        self.commands = commands or []
        self.steps = steps or []
        self.footnotes = footnotes or {}

    def __repr__(self):
        return f'Protocol(date={self.date!r}, commands={self.commands!r}, steps={self.steps!r}, footnotes={self.footnotes!r})'

    def __str__(self):
        return self.show()
    
    def __iadd__(self, other):
        self.append(other)
        return self

    @classmethod
    def parse(cls, x):
        from collections.abc import Sequence

        if isinstance(x, io.IOBase):
            return cls.parse_stream(x)
        if isinstance(x, str):
            return cls.parse_str(x)
        if isinstance(x, Sequence):
            return cls.parse_lines(x)

        raise ParseError(f"expected stream or string or list-like, not {type(x)}")

    @classmethod
    def parse_stream(cls, stream):
        return cls.parse_str(stream.read())

    @classmethod
    def parse_str(cls, text):
        return cls.parse_lines(text.splitlines())

    @classmethod
    def parse_lines(cls, lines):
        protocol = cls()

        class Transition:

            def __init__(self, next_parser, state=None, line_parsed=True):
                self.next_parser = next_parser
                self.next_state = state or {}
                self.line_parsed = line_parsed

        def parse_date(line, state):
            """
            If the first non-empty line contains a date, parse it.
            """
            if re.match(cls.BLANK_REGEX, line):
                return Transition(parse_date)

            try:
                protocol.date = arrow.get(line, cls.DATE_FORMAT)
                return Transition(parse_command)
            except arrow.ParserError:
                return Transition(parse_command, line_parsed=False)

        def parse_command(line, state):
            """
            Interpret each line beginning with '$ ' as a command.
            """
            if match := re.match(cls.COMMAND_REGEX, line):
                protocol.commands.append(match.group(1))
                return Transition(parse_command)

            if re.match(cls.BLANK_REGEX, line):
                return Transition(parse_command)

            return Transition(parse_new_step, line_parsed=False)

        def parse_new_step(line, state):
            if re.match(cls.FOOTNOTE_HEADER_REGEX, line):
                return Transition(parse_new_footnote)

            if match := re.match(cls.STEP_REGEX, line):
                state['indent'] = len(match.group(1))
                protocol.steps.append(match.group(2) + '\n')
                return Transition(parse_continued_step, state=state)

            raise ParseError(
                    template=truncate_error("expected a step (e.g. '- ...' or '1. ...'), not '{}'", line),
                    culprit=inform.get_culprit(),
            )

        def parse_continued_step(line, state):
            indent = state['indent']

            if match := re.match(cls.INDENT_OR_BLANK_REGEX(indent), line):
                protocol.steps[-1] += match.group(2) + '\n'
                return Transition(parse_continued_step, state=state)

            return Transition(parse_new_step, line_parsed=False)

        def parse_new_footnote(line, state):
            if match := re.match(cls.FOOTNOTE_DEF_REGEX, line):
                id = state['id'] = int(match.group(2))
                state['indent'] = len(match.group(1))
                protocol.footnotes[id] = match.group(3) + '\n'
                return Transition(parse_continued_footnote, state=state)

            if re.match(cls.BLANK_REGEX, line):
                return Transition(parse_new_footnote)

            raise ParseError(
                    template=truncate_error("expected a footnote (e.g. '[1] ...'), not '{}'", line),
                    culprit=inform.get_culprit(),
            )

        def parse_continued_footnote(line, state):
            id = state['id']
            indent = state['indent']
            assert id in protocol.footnotes

            if match := re.match(cls.INDENT_OR_BLANK_REGEX(indent), line):
                protocol.footnotes[id] += match.group(2) + '\n'
                return Transition(parse_continued_footnote, state=state)

            return Transition(parse_new_footnote, line_parsed=False)


        def truncate_error(message, problem):
            max_width = shutil.get_terminal_size().columns
            max_problem_width = max_width - len(message.format('')) - 1
            truncated_problem = textwrap.shorten(
                    problem, max_problem_width, placeholder='...')
            return message.format(truncated_problem)

        def check_footnotes(footnotes):
            """
            Complain if there are any footnotes that don't refer to anything.
            """
            for i, line in enumerate(lines, start=1):
                for match in re.finditer(cls.FOOTNOTE_REGEX, line):
                    refs = indices_from_str(match.group(1))
                    unknown_refs = set(refs) - set(footnotes)
                    if unknown_refs:
                        raise ParseError(
                                template=f"unknown {plural(unknown_refs):footnote/s} [{str_from_indices(unknown_refs)}]",
                                culprit=inform.get_culprit(i),
                                unknown_refs=unknown_refs,
                        )

        try:
            current_parser = parse_date
            current_state = {}

            i = 0
            while i < len(lines):
                with inform.add_culprit(i+1):
                    transition = current_parser(lines[i], current_state)
                    i += transition.line_parsed
                    current_parser = transition.next_parser
                    current_state = transition.next_state

            # Clean up blank lines.
            protocol.steps = [x.strip() for x in protocol.steps]
            protocol.footnotes = {k: v.strip() for k,v in protocol.footnotes.items()}

            # Clean up footnotes.
            check_footnotes(protocol.footnotes)
            protocol.renumber_footnotes()

            return protocol

        except ParseError as err:
            err.reraise(content='\n'.join(lines))
        
    def show(self):
        s = ''.join([
                self.show_date(),
                self.show_commands(),
                self.show_steps(),
                self.show_footnotes(),
        ])
        return s.rstrip()

    def show_date(self):
        s = ''
        if self.date:
            s += self.date.format(self.DATE_FORMAT)
            s += '\n\n'
        return s

    def show_commands(self):
        s = ''
        if self.commands:
            for cmd in self.commands:
                s += f'$ {cmd}\n'
            s += '\n'
        return s

    def show_steps(self):
        indent = len(str(len(self.steps))) + 2

        s = ''
        for i, step in enumerate(self.steps, start=1):
            s += f'{f"{i}. ":>{indent}}'
            s += textwrap.indent(step, ' ' * indent).strip()
            s += '\n\n'
        return s

    def show_footnotes(self):
        s = ''
        if self.footnotes:
            s += f'{plural(self.footnotes):Note/s}:\n'
            indent = len(str(max(self.footnotes))) + 3

            for i in sorted(self.footnotes):
                s += f'{f"[{i}] ":>{indent}}'
                s += textwrap.indent(self.footnotes[i], ' ' * indent).strip()
                s += '\n\n'
        return s

    def append(self, other):
        self.merge(self, other, target=self)

    def prepend(self, other):
        self.merge(other, self, target=self)

    @classmethod
    def merge(cls, *protocols, target=None):
        if target is None: target = cls()
        protocols = [
                cls.from_anything(copy(x) if x is target else x)
                for x in protocols
        ]

        # Use the most recent date.
        dates = [x.date for x in protocols if x.date is not None]
        target.date = sorted(dates)[-1] if dates else None

        # Concatenate all the commands.
        target.commands = sum([x.commands for x in protocols], [])

        # Merge the steps and footnotes.  This requires renumbering the 
        # footnotes.
        cursor = 0
        target.steps = []
        target.footnotes = {}

        for protocol in protocols:
            p = copy(protocol)

            # Don't try to renumber the footnotes if there aren't any.  This 
            # happens when using the += operator to add steps.  The steps might 
            # reference footnotes that haven't been defined yet, and trying to 
            # renumber them causes the code to crash.
            if p.footnotes:
                p.renumber_footnotes(cursor + 1)

            # Footnotes should never be clobbered.
            assert not set(p.footnotes) & set(target.footnotes)

            target.steps.extend(p.steps)
            target.footnotes.update(p.footnotes)

            cursor = max(target.footnotes, default=0)

        return target

    def prune_footnotes(self):
        """
        Remove footnotes that aren't referenced in the protocol.

        This can happen if a particular footnote applies to a part of a 
        protocol that wasn't included.
        """
        referenced_ids = {
                int(m.group(1))
                for m in re.finditer(self.FOOTNOTE_REGEX, self.show_steps())
        }
        self.footnotes = {
                k: v
                for k, v in self.footnotes.items()
                if k in referenced_ids
        }
        self.renumber_footnotes()

    def renumber_footnotes(self, start=1):
        """
        Renumber the footnotes consecutively from the given starting value.

        The new numbers will start at the given value and increase one-by-one 
        without gaps.  The footnotes will remain in the same order as they were 
        previously.  References to the footnotes in the steps will be updated.
        """

        old_ids = sorted(self.footnotes)
        new_ids = {j: i for i, j in enumerate(old_ids, start=start)}
        
        def renumber_footnote(m):
            ii = indices_from_str(m.group(1))
            jj = [new_ids[i] for i in ii]
            return f'[{str_from_indices(jj)}]'

        self.steps = [
                re.sub(self.FOOTNOTE_REGEX, renumber_footnote, step)
                for step in self.steps
        ]
        self.footnotes = {
                new_ids[k]: v
                for k,v in self.footnotes.items()
        }

    def clear_footnotes(self):
        self.steps = [
                re.sub(rf'\s*{self.FOOTNOTE_REGEX}', '', step)
                for step in self.steps
        ]
        self.footnotes = {}

    def pick_slug(self):
        """
        Return a identifier for this protocol, e.g. that could be used as a 
        file name.

        The identifier is made by combining the date and the various commands associated with the protocol.
        """
        slug = []

        if self.date:
            slug.append(self.date.format("YYYYMMDD"))

        for cmd in self.commands:
            argv = shlex.split(cmd)
            arg0 = argv[0] if argv[0] != 'stepwise' else argv[1]
            slug.append(Path(arg0).stem)

        if slug:
            return '_'.join(slug)
        else:
            return 'protocol'

    def set_current_date(self):
        self.date = arrow.now()

    def set_current_command(self):
        # But also figure out full name of current script.
        argv = Path(sys.argv[0]).name, *sys.argv[1:]
        self.commands = [shlex.join(argv)]

class ProtocolIO:
    """
    Represent a user-provided protocol that may or may not have been 
    successfully parsed.

    `ProtocolIO` objects have two attributes: `errors` and `protocol`.  
    `errors` is a count of the number of errors that have been generated so far 
    in the pipeline.  If there have been any errors, `protocol` will be a 
    string containing the raw text for the protocol.  This text won't be 
    properly formatted, but it should help the user figure out what the 
    problems were.  If there haven't been any errors, `io.protocol` will be a 
    fully initialized `stepwise.Protocol` instance representing the protocol.
    """

    # The methods of this class should never raise, so that commands can always 
    # be pipelined no matter what goes wrong.

    @classmethod
    def from_stdin(cls):
        if sys.stdin.isatty():
            return cls()

        try:
            return pickle.load(sys.stdin.buffer)

        except Exception as err:
            error(
                    f"error parsing stdin: {err}",
                    codicil="This error commonly occurs when the output from a non-stepwise command is piped into a stepwise command.  When usings pipes to combine protocols, make sure that every command is a stepwise command.",
                    wrap=True,
            )
            return cls("", 1)

    @classmethod
    def from_cli(cls, command, args, quiet=False, show_error_header=False):
        io = cls()

        try:
            io.protocol = load(command, args)

        except ParseError as err:
            if show_error_header:
                warn("the protocol could not be properly rendered due to error(s):")
            err.report(informant=warn)

            io.protocol = err.content
            io.errors = 1

        except StepwiseError as err:
            err.report()

            io.protocol = ''
            io.errors = 1

        except Exception as err:
            print_exc(file=sys.stderr)

            io.protocol = ''
            io.errors = 1

        else:
            if not io.protocol.steps:
                warn("protocol is empty.", culprit=command)

            io.protocol.set_current_date()
            io.protocol.set_current_command()
            if quiet: io.protocol.clear_footnotes()

        return io

    @classmethod
    def merge(cls, *others):
        io = cls()
        io.errors = sum(x.errors for x in others)

        if not io.errors:
            io.protocol = merge(*(x.protocol for x in others))
        else:
            # When merging with the empty protocol created by default is stdin 
            # is empty, an extraneous newline will be added to the front of the 
            # protocol.  The strip() call deals with this.
            io.protocol = '\n'.join((str(x.protocol) for x in others)).strip()

        return io

    def __init__(self, protocol=None, errors=0):
        self.protocol = protocol or Protocol()
        self.errors = errors

    def to_stdout(self, force_text=False):
        if sys.stdout.isatty() or force_text:
            print(self.protocol)
        else:
            try:
                pickle.dump(self, sys.stdout.buffer)
            except Exception as err:
                print_exc(file=sys.stderr)
                io = ProtocolIO('', 1)
                pickle.dump(io)

def load(name, args):
    """
    Find a protocol by name, then load it in a filetype-specific manner.
    """

    hit = find_protocol_path(name)
    culprit = hit['path']

    if hit['type'] != 'plugin':
        try:
            check_version_control(hit['path'])
        except VersionControlWarning as err:
            err.report(informant=warn)

    if is_executable(hit['path']):
        cmd = str(hit['path']), *args
        culprit = f'`{shlex.join(cmd)}`'
        p = subp.run(cmd, stdout=subp.PIPE, text=True)
        if p.returncode != 0:
            raise LoadError(f"command failed with status {p.returncode}", culprit=culprit)
        content = p.stdout
    elif hit['path'].suffix == '.txt':
        content = hit['path'].read_text()
    else:
        return Protocol(steps=[f"<{hit['relpath']}>"])

    with inform.set_culprit(culprit):
        return parse(content)

def parse(input):
    return Protocol.parse(input)

def merge(*protocols):
    return Protocol.merge(*protocols)

def find_protocol_dirs():
    """
    Return a list of any directories that could contain protocols.
    """
    dirs = []

    def add_dir(dir, type, name):
        dir, name = Path(dir), str(name)
        if dir.exists() and name not in config.search.ignore:
            dirs.append(dict(dir=dir, type=type, name=name))

    # Add specific directories specified by the user.
    for dir in config.search.path:
        add_dir(dir, 'path', dir)

    # Add directories found above the current working directory.
    for parent in Path.cwd().resolve().parents:
        for name in config.search.find:
            add_dir(parent/name, 'parent', parent/name)

    # Add directories specified by plugins.
    for plugin in iter_entry_points('stepwise.protocol_dirs'):
        for dir in plugin.load():
            add_dir(dir, 'plugin', f'{plugin.module_name}.{plugin.name}')

    return dirs

def find_protocol_paths(key=None, dirs=None):
    from itertools import chain

    # This could be more configurable, i.e. something like .gitignore
    def hidden(name):
        return any((
                name.startswith('.'),
                name.startswith('__'),
        ))

    hits = [] 
    dirs = dirs or find_protocol_dirs()
    key = key or ''

    for dir in dirs:
        for root, subdirs, files in os.walk(dir['dir']):
            subdirs[:] = [d for d in subdirs if not hidden(d)]

            for file in files:
                if hidden(file): continue

                path = Path(root) / file
                relpath = path.relative_to(dir['dir'])
                hit = dict(path=path, relpath=relpath, **dir)

                if key == path.stem: return [hit]
                if key in path.stem: hits.append(hit)

    return hits

def find_protocol_path(name):
    if (p := Path(name)).exists():
        return dict(
                dir=p.parent,
                path=p,
                relpath=p.relative_to(p.parent),
                type='cwd',
                name=p.parent,
        )
    else:
        dirs = find_protocol_dirs()
        hits = find_protocol_paths(name, dirs)
        return one(
            find_protocol_paths(name),
            NoProtocolsFound(name, dirs),
            MultipleProtocolsFound(name, hits),
        )

def check_version_control(path):
    path = path.resolve()

    # Check that the file is in a repository.
    p1 = subp.run(
            shlex.split('git rev-parse --show-toplevel'),
            cwd=path.parent,
            capture_output=True, text=True
    )
    if p1.returncode != 0:
        raise VersionControlWarning(f"not in a git repository!", culprit=path)

    git_dir = Path(p1.stdout.strip()).resolve()
    git_relpath = path.relative_to(git_dir)

    # Check that the file is being tracked.
    p2 = subp.run(
            ['git', 'log', '-n1', '--pretty=format:%H', '--', git_relpath],
            cwd=git_dir,
            capture_output=True,
    )
    if p2.returncode != 0:
        raise VersionControlWarning(f"not committed", culprit=path)

    # Check that the file doesn't have any uncommitted changes.
    p3 = subp.run(
            shlex.split('git ls-files --modified --deleted --others --exclude-standard'),
            cwd=git_dir,
            capture_output=True, text=True,
    )
    if str(git_relpath) in p3.stdout:
        raise VersionControlWarning(f"uncommitted changes", culprit=path)

def is_executable(path):
    import os, stat
    return stat.S_IXUSR & os.stat(path)[stat.ST_MODE]

