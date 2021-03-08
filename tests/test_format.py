#!/usr/bin/env python3

import stepwise

from stepwise import ol, ul, pl, pre, NO_WRAP
from math import inf
from utils import *

@parametrize('pre', [stepwise.preformatted, stepwise.pre])
@parametrize_via_toml('test_format.toml')
def test_preformatted_format_text(pre, obj, width, expected):
    obj = eval(obj)
    assert pre(obj).format_text(width) == expected

@parametrize('pre', [stepwise.preformatted, stepwise.pre])
@parametrize_via_toml('test_format.toml')
def test_preformatted_replace_text(pre, obj, pattern, repl, expected):
    obj = eval(obj)
    expected = eval(expected)

    x = pre(obj)
    x.replace_text(pattern, repl)
    assert x.content == expected

@parametrize('ul', [stepwise.unordered_list, stepwise.ul])
@parametrize_via_toml('test_format.toml')
def test_unordered_list_format_text(ul, items, prefix, br, width, expected):
    items = map(eval, items)

    x = ul(*items, prefix=prefix, br=br)
    assert x.format_text(width) == expected

@parametrize('ol', [stepwise.ordered_list, stepwise.ol])
@parametrize_via_toml('test_format.toml')
def test_ordered_list_format_text(ol, items, start, indices, prefix, br, width, expected):
    items = map(eval, items)

    x = ol(
            *items,
            start=start,
            indices=indices,
            prefix=prefix,
            br=br,
    )
    assert x.format_text(width) == expected

@parametrize('pl', [stepwise.paragraph_list, stepwise.pl])
@parametrize_via_toml('test_format.toml')
def test_paragraph_list_format_text(pl, items, width, expected):
    items = map(eval, items)
    assert pl(*items).format_text(width) == expected

def test_list_operators():
    x = stepwise.List()
    assert len(x) == 0
    assert list(x) == []
    assert list(reversed(x)) == []

    x += "a"
    assert len(x) == 1
    assert list(x) == ["a"]
    assert list(reversed(x)) == ["a"]
    assert x == stepwise.List("a")
    assert x[-1] == "a"

    x += "b"
    assert len(x) == 2
    assert list(x) == ["a", "b"]
    assert list(reversed(x)) == ["b", "a"]
    assert x == stepwise.List("a", "b")
    assert x[-1] == "b"

    x += None
    assert len(x) == 2
    assert list(x) == ["a", "b"]
    assert list(reversed(x)) == ["b", "a"]
    assert x == stepwise.List("a", "b")
    assert x == stepwise.List("a", None, "b")
    assert x[-1] == None

@parametrize_via_toml('test_format.toml')
def test_list_replace_text(items, pattern, repl, expected):
    l = stepwise.List(*items)
    l.replace_text(pattern, repl)
    assert l.items == expected


@parametrize_via_toml('test_format.toml')
def test_format_text(obj, width, expected):
    obj = eval(obj)
    width = eval_width(width)
    expected = eval(expected)

    assert stepwise.format_text(obj, width) == expected

@parametrize_via_toml('test_format.toml')
def test_format_list_item(obj, width, prefix, expected):
    obj = eval(obj)
    expected = eval(expected)

    assert stepwise.format_list_item(obj, width, prefix) == expected

@parametrize_via_toml('test_format.toml')
def test_replace_text(obj, pattern, repl, reverse, count, expected, n):
    obj = eval(obj)
    expected = eval(expected)
    info = {}

    obj_repl = stepwise.replace_text(
            obj, pattern, repl,
            reverse=reverse,
            count=count,
            info=info,
    )
    assert obj_repl == expected
    assert info['n'] == n


def eval_width(w):
    return eval(w) if isinstance(w, str) else w
