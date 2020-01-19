#!/usr/bin/env python3

import sys
import shlex
import arrow
import re
import textwrap
import io
import subprocess as subp
from nonstdlib import plural
from more_itertools import one
from copy import copy
from pathlib import Path
from pkg_resources import iter_entry_points
from .config import config

class Protocol:
    BLANK_REGEX = r'^\s*$'
    DATE_FORMAT = 'MMMM D, YYYY'
    COMMAND_REGEX = r'^[$] (.+)'
    STEP_REGEX = r'^(- |\d+\. )(.+)'
    FOOTNOTE_HEADER_REGEX = r'Notes?:|Footnotes?:'
    FOOTNOTE_REGEX = r'\[(\d+)\]'
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

        raise ValueError(f"expected stream or string or list-like, not {type(x)}")

    @classmethod
    def parse_stdin(cls):
        if not sys.stdin.isatty():
            return cls.parse_stream(sys.stdin)
        else:
            return cls()

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

            raise UserError(f"expected '- ...' or 'Note[s]:', not '{line}'")

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

            raise UserError(f"expected '[#] ...', not '{line}'")

        def parse_continued_footnote(line, state):
            id = state['id']
            indent = state['indent']
            assert id in protocol.footnotes

            if match := re.match(cls.INDENT_OR_BLANK_REGEX(indent), line):
                protocol.footnotes[id] += match.group(2) + '\n'
                return Transition(parse_continued_footnote, state=state)

            return Transition(parse_new_footnote, line_parsed=False)

        current_parser = parse_date
        current_state = {}

        i = 0
        while i < len(lines):
            transition = current_parser(lines[i], current_state)
            i += transition.line_parsed
            current_parser = transition.next_parser
            current_state = transition.next_state

        # Clean up blank lines
        protocol.steps = [x.strip() for x in protocol.steps]
        protocol.footnotes = {k: v.strip() for k,v in protocol.footnotes.items()}

        # Complain if things don't make sense.
        protocol.check_footnotes()
        protocol.renumber_footnotes()

        return protocol

    def show(self):
        s = ''.join([
                self.show_date(),
                self.show_commands(),
                self.show_steps(),
                self.show_footnotes(),
        ])

        if s.endswith('\n'):
            s = s.rstrip() + '\n'

        return s

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

        # Concatenate all the steps.
        target.steps = sum([x.steps for x in protocols], [])

        # Merge and renumber the footnotes.
        cursor = 0
        target.footnotes = {}

        for protocol in protocols:
            if not protocol.footnotes:
                continue

            p = copy(protocol)
            p.renumber_footnotes(cursor + 1)
            cursor = max(p.footnotes)

            assert not set(p.footnotes) & set(target.footnotes)
            target.footnotes.update(p.footnotes)

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

        def update_id(m):
            old_id = int(m.group(1))
            new_id = new_ids[old_id]
            return f'[{new_id}]'

        self.steps = [
                re.sub(self.FOOTNOTE_REGEX, update_id, step)
                for step in self.steps
        ]
        self.footnotes = {
                new_ids[k]: v
                for k,v in self.footnotes.items()
        }

    def check_footnotes(self):
        """
        Complain if there are footnotes in the protocol that don't refer to 
        anything.
        """
        lines = self.show().split('\n')
        for i, line in enumerate(lines, start=1):
            for match in re.finditer(self.FOOTNOTE_REGEX, line):
                id = int(match.group(1))
                if id not in self.footnotes:
                    raise UserError(f"unknown footnote [{id}] on line {i}: '{line.strip()}'")

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
            slug.append(argv[0] if argv[0] != 'stepwise' else argv[1])

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


class UserError(Exception):
    pass

class NoProtocolsFound(UserError):

    def __init__(self, name, search_dirs):
        self.name = name
        self.search_dirs = search_dirs

    def __str__(self):
        err = f"no protocols matching '{self.name}' in:\n"
        for dir in self.search_dirs:
            err += f"    {dir}\n"
        return err

class MultipleProtocolsFound(UserError):

    def __init__(self, name, hits):
        self.name = name
        self.hits = hits

    def __str__(self):
        err = f"multiple protocols matching '{self.name}':\n"
        for hit in self.hits:
            err += f"    {hit}\n"
        return err

def load(name, args):
    """
    Find a protocol by name, then load it in a filetype-specific manner.
    """

    hits = []
    dirs = find_protocol_dirs()

    for dir in dirs:
        hits += list(dir.glob(f'**/{name}'))
        hits += list(dir.glob(f'**/{name}.*'))

    hit = one(
        hits,
        NoProtocolsFound(name, dirs),
        MultipleProtocolsFound(name, hits),
    )

    check_version_control(hit)

    if is_executable(hit):
        p = subp.run([str(hit), *args], stdout=subp.PIPE, text=True)
        p.check_returncode()
        content = p.stdout
    else:
        content = hit.read_text()

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

    # Add specific directories specified by the user.
    dirs += config.search.path

    # Add directories found above the current working directory.
    for parent in Path.cwd().resolve().parents:
        for name in config.search.find:
            dir = parent / name
            if dir.exists():
                dirs.append(dir)

    # Add directories specified by plugins.
    for plugin in iter_entry_points('stepwise.protocol_dirs'):
        dirs += plugin.load()

    # Remove directories blacklisted by the user.
    dirs = [x for x in dirs if x not in config.search.ignore]

    return dirs

def find_protocol_names():
    """
    Return a list of all valid protocol names.
    """
    return sorted([
        path.name
        for dir in find_protocol_dirs()
        for path in dir.glob('*')
    ])

def check_version_control(path):
    def warn(*args, **kwargs):
        print("Warning:", *args, **kwargs, file=sys.stderr)

    # Hack to skip this check for plugins.
    if 'site-packages' in str(path):
        return

    # Check that the file is in a repository.
    p1 = subp.run(
            shlex.split('git rev-parse --show-toplevel'),
            cwd=path.resolve().parent,
            capture_output=True, text=True
    )
    if p1.returncode != 0:
        warn(f"'{path}' is not in a git repository!")

    git_dir = Path(p1.stdout.strip())
    git_relpath = path.resolve().relative_to(git_dir)

    # Check that the file is being tracked.
    p2 = subp.run(
            ['git', 'log', '-n1', '--pretty=format:%H', '--', git_relpath],
            cwd=git_dir,
            capture_output=True,
    )
    if p2.returncode != 0:
        warn(f"'{path}' has never been committed!")

    # Check that the file doesn't have any uncommitted changes.
    p3 = subp.run(
            shlex.split('git ls-files --modified --deleted --others --exclude-standard'),
            cwd=git_dir,
            capture_output=True, text=True,
    )
    if str(git_relpath) in p3.stdout:
        warn(f"'{path}' has uncommitted changes.")

def is_executable(path):
    import os, stat
    return stat.S_IXUSR & os.stat(path)[stat.ST_MODE]

