#!/usr/bin/env python3

import sys, shlex, re, textwrap
import arrow, inform
from pathlib import Path
from math import inf
from inform import plural, parse_range, format_range
from .format import paragraph_list, ordered_list, unordered_list, preformatted
from .format import format_text, replace_text
from .errors import *

import functools

class Protocol:
    # Steps can either be strings or formatting objects.  Strings will be 
    # automatically wrapped; use `format.preformatted` to prevent this.

    BLANK_REGEX = r'^\s*$|^#.*'
    DATE_FORMAT = 'MMMM D, YYYY'
    COMMAND_REGEX = r'^[$] (.+)'
    STEP_REGEX = r'^(- |\s*\d+\. )(.+)'
    FOOTNOTE_HEADER_REGEX = r'Notes?:|Footnotes?:'
    FOOTNOTE_REGEX = r'\[(\d+(?:[-,]\d+)*)\]'
    FOOTNOTE_DEF_REGEX = fr'^\s*(\[(\d+)\] )(.+)'
    INDENT_OR_BLANK_REGEX = lambda n: fr'^({" "*n}|\s*$)(.*)$'

    def __init__(self, *, date=None, commands=None, steps=None, footnotes=None):
        self.date = date
        self.commands = commands or []
        self.steps = steps or []
        self.footnotes = footnotes or {}
        self.attachments = []

    def __repr__(self):
        return f'{self.__class__.__name__}(date={self.date!r}, commands={self.commands!r}, steps={self.steps!r}, footnotes={self.footnotes!r})'

    def __bool__(self):
        return bool(self.steps)

    def __add__(self, other):
        return Protocol.merge(self, other)

    def __iadd__(self, other):
        self.append(other)
        return self

    def __getitem__(self, i):
        return self.steps[i]

    @classmethod
    def parse(cls, x):
        """
        Construct a protocol from a stream (i.e. an open file object), a 
        string, of a list of lines.

        No line-wrapping will be applied to the content parsed by this method.
        """
        from io import IOBase
        from collections.abc import Sequence

        if isinstance(x, IOBase):
            return cls._parse_stream(x)
        if isinstance(x, str):
            return cls._parse_str(x)
        if isinstance(x, Sequence):
            return cls._parse_lines(x)

        raise ParseError(f"expected stream or string or list-like, not {type(x)}")

    @classmethod
    def _parse_stream(cls, stream):
        return cls._parse_str(stream.read())

    @classmethod
    def _parse_str(cls, text):
        return cls._parse_lines(text.splitlines())

    @classmethod
    def _parse_lines(cls, lines):
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
                    template=truncate_error("expected a step (e.g. '- …' or '1. …'), not '{}'", line),
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
                    template=truncate_error("expected a footnote (e.g. '[1] …'), not '{}'", line),
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
            from shutil import get_terminal_size
            max_width = get_terminal_size().columns
            max_problem_width = max_width - len(message.format('')) - 1
            truncated_problem = textwrap.shorten(
                    problem, max_problem_width, placeholder='…')
            return message.format(truncated_problem)

        def check_footnotes(footnotes):
            """
            Complain if there are any footnotes that don't refer to anything.
            """
            for i, line in enumerate(lines, start=1):
                for match in re.finditer(cls.FOOTNOTE_REGEX, line):
                    refs = parse_range(match.group(1))
                    unknown_refs = set(refs) - set(footnotes)
                    if unknown_refs:
                        raise ParseError(
                                template=f"unknown {plural(unknown_refs):footnote/s} [{format_range(unknown_refs)}]",
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
            protocol.steps = [
                    preformatted(x.strip())
                    for x in protocol.steps
            ]
            protocol.footnotes = {
                    k: preformatted(v.strip())
                    for k, v in protocol.footnotes.items()
            }

            # Clean up footnotes.
            check_footnotes(protocol.footnotes)
            protocol.renumber_footnotes()

            return protocol

        except ParseError as err:
            err.reraise(content='\n'.join(lines))
        
    def format_text(self, width=inf, **kwargs):
        pl = paragraph_list(
                self._format_date(),
                self._format_commands(),
                self._format_steps(),
                self._format_footnotes(),
        )
        return pl.format_text(width, **kwargs)

    def _format_date(self):
        if self.date:
            return self.date.format(self.DATE_FORMAT)

    def _format_commands(self):
        return unordered_list(*map(preformatted, self.commands), prefix='$ ')

    def _format_steps(self):
        return ordered_list(*self.steps)

    def _format_footnotes(self):
        pl = paragraph_list(br='\n')

        if self.footnotes:
            pl += f'{plural(self.footnotes):Note/s}:'
            pl += ordered_list(
                    *self.footnotes.values(),
                    indices=self.footnotes.keys(),
                    prefix='[{}] ',
            )

        return pl

    def print(self):
        from .library import ProtocolIO
        io = ProtocolIO(self)
        io.to_stdout()

    def append(self, other):
        self.merge(self, other, target=self)

    def prepend(self, other):
        self.merge(other, self, target=self)

    @classmethod
    def merge(cls, *protocol_like, target=None):
        from copy import copy
        from collections.abc import Iterable
        from math import inf
        from .library import ProtocolIO
        from .format import format_text

        if target is None:
            target = cls()

        # Support different ways of specifying protocol steps.
        protocols = []
        for obj in protocol_like:

            if isinstance(obj, Protocol):
                protocol = obj

            elif isinstance(obj, ProtocolIO):
                if obj.errors: continue
                protocol = obj.protocol

            elif isinstance(obj, str):
                protocol = cls(steps=[obj])

            # The interface specified by `format.Formatter()`:
            elif hasattr(obj, 'format_text') and hasattr(obj, 'replace_text'):
                protocol = cls(steps=[obj])

            elif isinstance(obj, Iterable):
                protocol = cls(steps=obj)

            else:
                raise ParseError(f"cannot interpret {obj!r} as a protocol.")

            if protocol is target:
                protocol = copy(protocol)

            protocols.append(protocol)

        # Use the most recent date.
        dates = [x.date for x in protocols if x.date is not None]
        target.date = max(dates, default=None)

        # Concatenate all the commands.
        target.commands = sum([x.commands for x in protocols], [])

        # Concatenate the steps and merge/renumber the footnotes.
        target.steps = []
        target.footnotes = {}
        next_footnote_key = 1

        for protocol in protocols:
            p = copy(protocol)
            f = lambda x: format_text(x, inf)

            footnote_map = {}
            footnote_keys = {f(v): k for k, v in target.footnotes.items()}
            
            # Avoid duplicate footnotes.
            for i, note in p.footnotes.items():
                note = f(note)
                if note in footnote_keys:
                    footnote_map[i] = footnote_keys[note]
                else:
                    footnote_map[i] = next_footnote_key
                    next_footnote_key += 1

            # Don't try to renumber the footnotes if there aren't any.  This 
            # happens when using the += operator to add steps.  The steps might 
            # reference footnotes that haven't been defined yet, and trying to 
            # renumber them triggers an error.  Honestly this is probably a 
            # sign that += is too overloaded, but for now this approach works.
            if p.footnotes:
                p.renumber_footnotes(footnote_map)

            target.steps.extend(p.steps)
            target.footnotes.update(p.footnotes)

        return target

    def add_footnotes(self, *footnotes):
        i0 = max(self.footnotes, default=0) + 1
        ii = []

        for i, footnote in enumerate(footnotes, i0):
            if footnote:
                self.footnotes[i] = footnote
                ii.append(i)

        return f' [{format_range(ii)}]' if ii else ''

    def insert_footnotes(self, *footnotes, pattern=r'(?=[.:])'):
        """
        Insert the given footnotes into the protocol immediately after the 
        given pattern.
        """

        if not footnotes:
            return

        # The protocol could have footnotes in any order, so number these  
        # footnotes based on `max() + 1` instead of `len() + 1` or similar.
        ref0 = max(self.footnotes, default=0) + 1
        refs = range(ref0, ref0 + len(footnotes))
        ref_str = f'[{format_range(refs)}]'

        def sub(m):
            sep = '' if m.string[m.end() - 1] == ' ' else ' '
            return m.group() + sep + ref_str

        for i, step in reversed(list(enumerate(self.steps))):
            state = {}
            self.steps[i] = replace_text(
                    step, pattern, sub,
                    state=state,
                    count=1,
            )
            if state.get('n'):
                break
        else:
            raise ValueError(f"pattern {pattern!r} not found in protocol.")

        for ref, footnote in zip(refs, footnotes):
            self.footnotes[ref] = footnote

    def renumber_footnotes(self, new_ids=1):
        """
        Renumber the footnotes.

        The footnotes will remain in the same order as they were previously.  
        References to the footnotes in the steps will be updated.  There are 
        three ways to specify what the new footnote numbers should be:

        - int: The new numbers will start at the given value and increase 
          one-by-one without gaps.  

        - dict: The keys are the current footnote numbers, and the values are 
          the new ones.  Each current number must be present in the dictionary.

        - callable: The callable will be called with a current footnote number 
          as the only argument, and should return the corresponding new 
          footnote number.
        """

        old_ids = sorted(self.footnotes)

        if isinstance(new_ids, int):
            new_ids = {j: i for i, j in enumerate(old_ids, start=new_ids)}
        if callable(new_ids):
            new_ids = {j: new_ids(j) for j in old_ids}

        def renumber_footnote(m):
            ii = parse_range(m.group(1))
            jj = [new_ids[i] for i in ii]
            return f'[{format_range(jj)}]'

        self.steps = [
                replace_text(x, self.FOOTNOTE_REGEX, renumber_footnote)
                for x in self.steps
        ]
        self.footnotes = {
                new_ids[k]: v
                for k,v in self.footnotes.items()
        }

    def deduplicate_footnotes(self):
        duplicate_ids = {}

        for k, v in self.footnotes.items():
            note = format_text(v, inf)
            duplicate_ids.setdefault(note, []).append(k)

        new_ids = {}
        for ids in duplicate_ids.values():
            new_id = min(ids)

            for id in ids:
                assert id not in new_ids
                new_ids[id] = new_id

        self.renumber_footnotes(new_ids)

    def merge_footnotes(self):
        """
        Look for footnotes that appear back to back (e.g. possibly due to 
        `add_footnotes()` or `insert_footnotes()`) and combine them.
        """

        def merge_footnotes(m):
            ref_ids = set()
            for ref_str in re.findall(self.FOOTNOTE_REGEX, m.group()):
                ref_ids |= parse_range(ref_str)
            return f'[{format_range(ref_ids)}]'

        self.steps = [
                replace_text(
                    x, rf'{self.FOOTNOTE_REGEX}(\s*{self.FOOTNOTE_REGEX})+',
                    merge_footnotes,
                )
                for x in self.steps
        ]

    def prune_footnotes(self):
        """
        Remove footnotes that aren't referenced in the protocol.

        This can happen if a particular footnote applies to a part of a 
        protocol that wasn't included.
        """

        def union(it):
            return set.union(set(), *it)

        formatted_steps = self._format_steps().format_text(inf)
        referenced_ids = union(
                parse_range(m.group(1))
                for m in re.finditer(self.FOOTNOTE_REGEX, formatted_steps)
        )
        self.footnotes = {
                k: v
                for k, v in self.footnotes.items()
                if k in referenced_ids
        }
        self.renumber_footnotes()

    def clear_footnotes(self):
        self.steps = [
                replace_text(x, rf'\s*{self.FOOTNOTE_REGEX}', '')
                for x in self.steps
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
            for arg0 in argv:
                if arg0 in ('sw', 'stepwise'): continue
                if arg0.startswith('-'): continue
                break
            slug.append(Path(arg0).stem)

        if slug:
            return '_'.join(slug)
        else:
            return 'protocol'

    def set_current_date(self):
        self.date = arrow.now()

    def set_current_command(self, cmd=None, args=None):
        nonprintable = {
            ord('\n'): '\\n',
            ord('\a'): '\\a',
            ord('\b'): '\\b',
            ord('\f'): '\\f',
            ord('\n'): '\\n',
            ord('\r'): '\\r',
            ord('\t'): '\\t',
            ord('\v'): '\\v',
        }
        if cmd is None:
            cmd = sys.argv[1]
        if args is None:
            args = sys.argv[2:]

        argv = 'sw', cmd, *args
        command = shlex.join(argv).translate(nonprintable)
        self.commands = [command]

