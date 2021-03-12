#!/usr/bin/env python3

from .format import Formatter, replace_text, _align_indents_if_possible
from more_itertools import mark_ends

class preformatted(Formatter):
    """
    Represent a string that has already been formatted.

    :param content: must be a string; can't be a formatted block.
    """

    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return f'{self.__class__.__name__}({self.content!r})'

    def __eq__(self, other):
        return type(self) == type(other) and self.content == other.content

    def format_text(self, width, **kwargs):
        aligned = _align_indents_if_possible(kwargs)
        initial_indent = kwargs.get('initial_indent', '')
        subsequent_indent = kwargs.get('subsequent_indent', '')

        lines = self.content.splitlines(True)

        if len(lines) == 0:
            return initial_indent

        if len(lines) == 1:
            return initial_indent + lines[0]

        if not aligned:
            lines = ['\n', *lines]

        out = ''
        for is_first, _, line in mark_ends(lines):
            out += initial_indent if is_first else subsequent_indent
            out += line

        return out

    def replace_text(self, pattern, repl, **kwargs):
        # This could mess up the formatting.
        self.content = replace_text(self.content, pattern, repl, **kwargs)



