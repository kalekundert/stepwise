#!/usr/bin/env python3

import re
import textwrap

_UNINITIALIZED = object()

class Formatter:
    
    def format_text(self, content_width, page_width, **kwargs):
        raise NotImplementedError

    def replace_text(self, pattern, repl, **kwargs):
        raise NotImplementedError

def format_text(obj, width, **kwargs):
    """
    Has the same signature as `textwrap.fill()`, except:

    - `width` is a required argument.
    - A `truncate_width` argument can be specified.  Some formatters might use 
      this to trim content that would otherwise extend beyond the given width.

    Note that the `width` argument can be `math.inf`.

    - Guaranteed to return string.  Return value will not be further modified.

    - Strings are treated as paragraphs.
    """

    if not isinstance(obj, str):
        return obj.format_text(width, **kwargs)

    # Trim trailing whitespace.  This prevents `textwrap.fill()` from turning 
    # 'a \nb' into 'a  b' (note the duplicate space).
    text = re.sub(r'(?m) $', '', obj)
    text = textwrap.dedent(text)

    # This is the only keyword argument allowed to `format_text()` that doesn't 
    # correspond to a `textwrap.fill()` keyword argument.
    kwargs.pop('truncate_width', None)

    return textwrap.fill(
        text, width,
        drop_whitespace=True,
        break_long_words=False,
        **kwargs,
    )

def replace_text(obj, pattern, repl, state=_UNINITIALIZED, **kwargs):
    if state is _UNINITIALIZED: state = {}
    state.setdefault('n', 0)

    if isinstance(obj, str):

        def subn_helper():
            # Adjust the count parameter to account for substitutions that were 
            # made in other calls.  Avoid going into this conditional if the 
            # user explicitly specified `count=0`, because that means to 
            # replace every occurrence of the pattern as per the `re` module 
            # documentation.

            if kwargs.get('count'):
                kwargs['count'] -= state['n']
                if kwargs['count'] <= 0:
                    return obj, 0

            return re.subn(pattern, repl, obj, **kwargs)

        obj_repl, n = subn_helper()
        state['n'] += n
        return obj_repl

    else:
        obj.replace_text(pattern, repl, state=state, **kwargs)
        return obj


def _align_indents_if_possible(kwargs):
    # If the initial indent contains any newlines, we only care about the 
    # length of the last line.  This comes up when making a definition list 
    # where with a prefix parameter that starts each definition on the line 
    # below the key, e.g. '{}:\n  '.
    initial_indent = kwargs.get('initial_indent', '')
    initial_indent_last_line = initial_indent.split('\n')[-1]
    subsequent_indent = kwargs.get('subsequent_indent', '')

    diff = len(subsequent_indent) - len(initial_indent_last_line)

    if diff > 0:
        kwargs['initial_indent'] = initial_indent + (diff * ' ')
        return True
    else:
        return diff == 0


