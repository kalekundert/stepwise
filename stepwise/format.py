#!/usr/bin/env python3

import re
import textwrap
from math import inf
from more_itertools import last

# When I make a table class, here are some places I can use it:
# - builtins/conditions.py
# - ~swmb/laser_scanner.py

NO_WRAP = object()

class Block:
    
    def format_text(self, width):
        raise NotImplementedError

    def replace_text(self, pattern, repl, **kwargs):
        raise NotImplementedError

class preformatted(Block):

    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return f'{self.__class__.__name__}({self.content!r})'

    def __eq__(self, other):
        return type(self) == type(other) and self.content == other.content

    def format_text(self, width):
        return format_text(self.content, NO_WRAP)

    def replace_text(self, pattern, repl, **kwargs):
        self.content = replace_text(self.content, pattern, repl, **kwargs)



class List(Block):
    """
    Format a list of values.

    Falsey values can be added to the list, but will be ignored for all 
    formatting purposes.
    """
    default_br = '\n'

    def __init__(self, *items, br=None):
        self.items = list(items)
        self.br = br or self.default_br

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(repr(x) for x in self.items)})'

    def __eq__(self, other):
        from itertools import zip_longest

        if type(self) != type(other):
            return False

        sentinel = object()
        for a, b in zip_longest(self, other, fillvalue=sentinel):
            if a != b:
                return False

        return True

    def __iter__(self):
        yield from (x for x in self.items if x)

    def __reversed__(self):
        yield from (x for x in self.items[::-1] if x)

    def __len__(self):
        return sum(1 for _ in self)

    def __getitem__(self, i):
        return self.items[i]

    def __iadd__(self, item):
        self.items.append(item)
        return self

    def replace_text(self, pattern, repl, reverse=False, **kwargs):
        it = reversed if reverse else iter
        self.items = list(it([
                replace_text(x, pattern, repl, **kwargs)
                for x in it(self)
        ]))


class unordered_list(List):
    default_br = '\n'

    def __init__(self, *items, prefix='- ', **kwargs):
        super().__init__(*items, **kwargs)
        self.prefix = prefix

    def format_text(self, width):
        return self.br.join(
                format_list_item(x, width, self.prefix)
                for x in self
        )

class ordered_list(List):
    default_br = '\n\n'

    def __init__(self, *items, start=1, indices=None, prefix="{}. ", **kwargs):
        super().__init__(*items, **kwargs)
        self.prefix = prefix
        self.start = start
        self.indices = indices

    def format_text(self, width):
        indices = self.indices or range(self.start, self.start + len(self))
        indices = list(indices)

        if len(indices) != len(self):
            raise ValueError(f"got {len(indices)} indices for {len(self)} list items")

        # Consider the lengths of all the indices, because the largest won't 
        # necessarily be the longest (e.g. negative numbers).
        prefix_lens = (len(self.prefix.format(i)) for i in indices)
        max_prefix_len = max(prefix_lens, default=0)

        return self.br.join(
                format_list_item(
                    x, width,
                    f'{self.prefix.format(i):>{max_prefix_len}}',
                )
                for i, x in zip(indices, self)
        )

class paragraph_list(List):
    default_br = '\n\n'

    def __init__(self, *items, **kwargs):
        super().__init__(*items, **kwargs)

    def format_text(self, width):
        return self.br.join(
                format_text(x, width)
                for x in self
        )

ul = unordered_list
ol = ordered_list
pl = paragraph_list
pre = preformatted

class _noop_dict:

    def __setitem__(self, k, v):
        pass

    def get(self, key, default=None):
        return default

def format_text(obj, width):
    """
    :param width:
        NO_WRAP: disable line wrapping
        inf: wrap with infinite line width.  This is different than NO_WRAP, because newlines will be joined (but paragraphs will not).
        int: wrap to the given width.
    """
    if not isinstance(obj, str):
        return obj.format_text(width)

    if width is NO_WRAP:
        return obj

    text = re.sub(r'(?m) $', '', obj)
    text = textwrap.dedent(text)

    paragraphs = re.split('\n\\s*\n', text)
    paragraphs = [
            textwrap.fill(
                x, width,
                drop_whitespace=True,
                break_long_words=False,
            )
            for x in paragraphs if x
    ]
    return '\n\n'.join(paragraphs)

def format_list_item(obj, width, prefix):
    n = len(prefix)
    w = NO_WRAP if width is NO_WRAP else max(1, width - n)

    li = format_text(obj, w)
    li = textwrap.indent(li, n * ' ')
    li = prefix + li[n:]

    return li
    
def replace_text(obj, pattern, repl, reverse=False, info=_noop_dict(), **kwargs):
    if isinstance(obj, str):

        def subn_helper():
            # Adjust the count parameter to account for substitutions that were 
            # made in other calls.  Avoid going into this conditional if the 
            # user explicitly specified `count=0`, because that means to 
            # replace every occurrence of the pattern as per the `re` module 
            # documentation.

            if kwargs.get('count'):
                kwargs['count'] -= info.get('n', 0)
                if kwargs['count'] <= 0:
                    return obj, 0

            # The `re` module doesn't have built-in support for substituting 
            # the rightmost occurrences of a pattern, so if we are asked for 
            # that, we have to do it manually.

            if not (reverse and 'count' in kwargs):
                return re.subn(pattern, repl, obj, **kwargs)

            else:
                matches = list(re.finditer(pattern, obj))

                if not matches:
                    return obj, 0

                else:
                    m = matches[-kwargs['count']]
                    i = m.start()
                    obj_left = m.string[:i]
                    obj_right = m.string[i:]
                    obj_right_repl, n = re.subn(pattern, repl, obj_right, **kwargs)
                    return obj_left + obj_right_repl, n

        obj_repl, n = subn_helper()
        info['n'] = info.get('n', 0) + n
        return obj_repl
    else:
        obj.replace_text(pattern, repl, reverse=reverse, info=info, **kwargs)
        return obj



