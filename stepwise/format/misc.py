#!/usr/bin/env python3

from .format import Formatter, replace_text, _align_indents_if_possible
from .lists import paragraph_list, unordered_list
from more_itertools import mark_ends

class preformatted(Formatter):
    """
    Represent a string that has already been formatted.

    :param content: must be a string; can't be a formatted block.
    """

    def __init__(self, content):
        self.content = str(content)

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

def step_from_str(step_str, delim, *, wrap=True, level=1):
    fields = split_by_delim_count(step_str, delim, count=level)

    if len(fields) == 1:
        wrapper = str if wrap else preformatted
        return wrapper(fields[0])

    return paragraph_list(
            step_from_str(fields[0], delim, wrap=wrap, level=level+1),
            unordered_list(*(
                step_from_str(x, delim, wrap=wrap, level=level+1)
                for x in fields[1:]
            )),
            br='\n\n' if level == 1 else '\n',
    )

def split_by_delim_count(str, delim, count):
    return list(iter_by_delim_count(str, delim, count))

def iter_by_delim_count(str, delim, count):
    """
    Split the given string wherever the given delimiter appear *exactly* the 
    given number of times in a row.
    """
    if len(delim) != 1:
        raise ValueError(f"delimiter must be a single character, not: {delim!r}")

    curr_field = ''
    curr_delim = ''

    for c in str:
        if c == delim:
            curr_delim += c
        else:
            if curr_delim:
                if len(curr_delim) == count:
                    yield curr_field
                    curr_field = ''
                else:
                    curr_field += curr_delim

                curr_delim = ''

            curr_field += c

    if len(curr_delim) == count:
        yield curr_field
        yield ''
    else:
        yield curr_field + curr_delim

def oxford_comma(items, conj='and'):
    if len(items) == 2:
        return '{0[0]} {1} {0[1]}'.format(items, conj)

    result = ''
    for i, item in enumerate(items):
        if i == len(items) - 1:
            result += '{}'.format(item)
        elif i == len(items) - 2:
            result += '{}, {} '.format(item, conj)
        else:
            result += '{}, '.format(item)
    return result

