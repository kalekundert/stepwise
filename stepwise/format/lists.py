#!/usr/bin/env python3

from .format import (
        Formatter, format_text, replace_text, _align_indents_if_possible
)
from itertools import repeat
from more_itertools import repeat_last, mark_ends, interleave, chunked

class List(Formatter):
    """
    Format a list of values.

    Falsey values can be added to the list, but will be ignored for all 
    formatting purposes.
    """
    default_br = '\n'
    force_alignment = True

    def __init__(self, *items, br=None):
        self._items = list(items)
        self.br = br or self.default_br

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(repr(x) for x in self._items)})'

    def __eq__(self, other):
        return type(self) == type(other) and self._items == other._items

    def __iter__(self):
        yield from self._items

    def __len__(self):
        return len(self._items)

    def __getitem__(self, i):
        return self._items[i]

    def __setitem__(self, i, item):
        self._items[i] = item

    def __iadd__(self, item):
        self._items.append(item)
        return self

    def _format_items(self, width, *, indents, **kwargs):
        return _format_list(
                items=self._items,
                indents=indents,
                width=width,
                br=self.br,
                force_alignment=self.force_alignment,
                **kwargs,
        )

    def replace_text(self, pattern, repl, **kwargs):
        self._items = _replace_list(
                self._items, pattern, repl, **kwargs,
        )


class paragraph_list(List):
    default_br = '\n\n'
    force_alignment = False

    def __init__(self, *items, **kwargs):
        super().__init__(*items, **kwargs)

    def format_text(self, width, **kwargs):
        return self._format_items(
                width,
                indents=repeat(('', '')),
                **kwargs,
        )

class unordered_list(List):
    default_br = '\n'

    def __init__(self, *items, prefix='- ', **kwargs):
        super().__init__(*items, **kwargs)
        self.prefix = prefix

    def format_text(self, width, **kwargs):
        return self._format_items(
                width,
                indents=repeat((self.prefix, ' ' * len(self.prefix))),
                **kwargs,
        )

class ordered_list(List):
    default_br = '\n\n'

    def __init__(self, *items, start=1, indices=None, prefix="{}. ", **kwargs):
        super().__init__(*items, **kwargs)
        self.prefix = prefix
        self.start = start
        self.indices = indices

    def format_text(self, width, **kwargs):
        indices = self.indices or range(self.start, self.start + len(self))
        indices = list(indices)

        if len(indices) != len(self):
            raise ValueError(f"got {len(indices)} indices for {len(self)} list items")

        # Consider the lengths of all the indices, because the largest won't 
        # necessarily be the longest (e.g. negative numbers).
        prefix_lens = (len(self.prefix.format(i)) for i in indices)
        max_prefix_len = n = max(prefix_lens, default=0)

        return self._format_items(
                width,
                indents=(
                    (f'{self.prefix.format(i):>{n}}', ' ' * n)
                    for i in indices
                ),
                **kwargs,
        )

class definition_list(Formatter):
    # Note that you can put the definition on the line below the key by using a 
    # newline in prefix[0].

    def __init__(self, *items, prefix='{}: ', indent='  ', br='\n'):
        self._keys, self._values = map(list, zip(*items)) if items else ([], [])
        self._prefix = prefix
        self._indent = indent
        self.br = br

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(repr(x) for x in self)})'

    def __eq__(self, other):
        return (
                type(self) == type(other) and
                self._keys == other._keys and
                self._values == other._values and
                self.prefix == other.prefix and
                self.indent == other.indent and
                self.br == other.br
        )

    def __iter__(self):
        yield from zip(self._keys, self._values)

    def __len__(self):
        return len(self._keys)

    def __getitem__(self, i):
        if isinstance(i, int):
            return self._keys[i], self._values[i]
        else:
            i = self._keys.index(i)
            return self._values[i]

    def __setitem__(self, key, value):
        try:
            i = self._keys.index(key)
        except ValueError:
            self._keys.append(key)
            self._values.append(value)
        else:
            self._values[i] = value

    def __iadd__(self, item):
        key, value = item
        self._keys.append(key)
        self._values.append(value)
        return self

    def format_text(self, width, **kwargs):
        return _format_list(
                items=self._values,
                indents=(
                    (self.prefix.format(k), self.indent)
                    for k in self._keys
                ),
                width=width,
                br=self.br,
                **kwargs,
        )

    def replace_text(self, pattern, repl, **kwargs):
        objs = interleave(self._keys, self._values)
        objs = _replace_list(objs, pattern, repl, **kwargs)
        self._keys, self._values = map(list, zip(*chunked(objs, 2))) \
                if objs else ([], [])

    @property
    def prefix(self):
        if self._prefix.endswith('\n'):
            return self._prefix + self._indent
        else:
            return self._prefix

    @property
    def indent(self):
        return self._indent

def _format_list(items, indents, width, br, force_alignment=True, **kwargs):
        if force_alignment:
            # This function modifies `kwargs`, so it must called before any 
            # of those values are read.
            force_alignment = not _align_indents_if_possible(kwargs)

        item_indent_iter = (
                (item, indent)
                for item, indent in zip(items, indents)
                if item
        )
        kwargs_indent_iter = repeat_last((
                kwargs.get('initial_indent', ''),
                kwargs.get('subsequent_indent', ''),
        ))

        def next_kwargs(indent):
            initial_indent, subsequent_indent = indent
            return {
                    **kwargs,
                    'initial_indent': \
                        next(kwargs_indent_iter) + initial_indent,
                    'subsequent_indent': \
                        next(kwargs_indent_iter) + subsequent_indent,
            }

        list_str = ''

        if force_alignment:
            list_str += next(kwargs_indent_iter) + '\n'

        for is_first, is_last, (item, indent) in mark_ends(item_indent_iter):
            list_str += format_text(item, width, **next_kwargs(indent))
            list_str += br * (not is_last)

        return list_str

def _replace_list(objs, pattern, repl, **kwargs):
    return [
            replace_text(x, pattern, repl, **kwargs) if x else x
            for x in objs
    ]
