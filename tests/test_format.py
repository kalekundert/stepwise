#!/usr/bin/env python3

import stepwise
from stepwise import ol, ul, pl, dl, pre, table, MasterMix
from utils import *

@parametrize_via_toml('test_format.toml')
def test_format_text(obj, width, expected, kwargs):
    assert stepwise.format_text(eval(obj), width, **kwargs) == expected

@parametrize_via_toml('test_format.toml')
def test_replace_text(obj, pattern, repl, count, expected, n):
    obj = eval(obj)
    expected = eval(expected)
    state = {}

    obj_repl = stepwise.replace_text(
            obj, pattern, repl,
            count=count,
            state=state,
    )
    assert obj_repl == expected
    assert state['n'] == n

def test_list_operators():
    x = stepwise.List()
    assert len(x) == 0
    assert list(x) == []
    assert list(reversed(x)) == []

    x += 'a'
    assert len(x) == 1
    assert list(x) == ['a']
    assert list(reversed(x)) == ['a']
    assert x == stepwise.List('a')
    assert x != stepwise.List('x')
    assert x[-1] == 'a'

    x += 'b'
    assert len(x) == 2
    assert list(x) == ['a', 'b']
    assert list(reversed(x)) == ['b', 'a']
    assert x == stepwise.List('a', 'b')
    assert x != stepwise.List('x', 'x')
    assert x[-1] == 'b'

    x[-1] = 'c'
    assert len(x) == 2
    assert list(x) == ['a', 'c']
    assert list(reversed(x)) == ['c', 'a']
    assert x == stepwise.List('a', 'c')
    assert x != stepwise.List('x', 'x')
    assert x[-1] == 'c'

def test_dl_operators():
    x = dl()
    assert len(x) == 0
    assert list(x) == []

    x += ('a', 'b')
    assert len(x) == 1
    assert list(x) == [('a', 'b')]
    assert x == dl(('a', 'b'))
    assert x != dl(('a', 'x'))
    assert x != dl(('x', 'b'))
    assert x[-1] == ('a', 'b')
    assert x['a'] == 'b'

    x['c'] = 'd'
    assert len(x) == 2
    assert list(x) == [('a', 'b'), ('c', 'd')]
    assert x == dl(('a', 'b'), ('c', 'd'))
    assert x != dl(('a', 'x'), ('c', 'd'))
    assert x != dl(('x', 'b'), ('c', 'd'))
    assert x != dl(('a', 'b'), ('x', 'd'))
    assert x != dl(('a', 'b'), ('c', 'x'))
    assert x[-1] == ('c', 'd')
    assert x['a'] == 'b'
    assert x['c'] == 'd'

    x['c'] = 'e'
    assert len(x) == 2
    assert list(x) == [('a', 'b'), ('c', 'e')]
    assert x == dl(('a', 'b'), ('c', 'e'))
    assert x != dl(('a', 'x'), ('c', 'e'))
    assert x != dl(('x', 'b'), ('c', 'e'))
    assert x != dl(('a', 'b'), ('x', 'e'))
    assert x != dl(('a', 'b'), ('c', 'x'))
    assert x[-1] == ('c', 'e')
    assert x['a'] == 'b'
    assert x['c'] == 'e'

def test_table_operators():
    x = stepwise.table([[]])
    assert x == stepwise.table([[]])
    assert x != stepwise.table([['x']])
    assert x != stepwise.table([[]], header=['x'])
    assert x != stepwise.table([[]], footer=['x'])

    x.rows = [['a']]
    assert x == stepwise.table([['a']])
    assert x != stepwise.table([['x']])
    assert x != stepwise.table([['a']], header=['x'])
    assert x != stepwise.table([['a']], footer=['x'])

    x.header = ['b']
    assert x == stepwise.table([['a']], header=['b'])
    assert x != stepwise.table([['x']], header=['b'])
    assert x != stepwise.table([['a']], header=['x'])
    assert x != stepwise.table([['a']], header=['b'], footer=['x'])

    x.footer = ['c']
    assert x == stepwise.table([['a']], header=['b'], footer=['c'])
    assert x != stepwise.table([['x']], header=['b'], footer=['c'])
    assert x != stepwise.table([['a']], header=['x'], footer=['c'])
    assert x != stepwise.table([['a']], header=['b'], footer=['x'])

def test_pre_operators():
    x = stepwise.pre('a')
    assert x == stepwise.pre('a')
    assert x != stepwise.pre('x')
    assert x != 'a'

@parametrize_via_toml('test_format.toml')
def test_step_from_str(step, delim, wrap, expected):
    assert stepwise.step_from_str(step, delim, wrap=wrap) == eval(expected)

@parametrize_via_toml('test_format.toml')
def test_split_by_delim_count(str, delim, count, expected):
    assert stepwise.split_by_delim_count(str,delim, count) == expected

@parametrize(
        'given,kwargs,expected', [
            ([],         dict(),           ''),
            ([1],        dict(),           '1'),
            ([1,2],      dict(),           '1 and 2'),
            ([1,2,3],    dict(),           '1, 2, and 3'),
            ([1,2,3,4],  dict(),           '1, 2, 3, and 4'),

            ([],         dict(conj='or'),  ''),
            ([1],        dict(conj='or'),  '1'),
            ([1,2],      dict(conj='or'),  '1 or 2'),
            ([1,2,3],    dict(conj='or'),  '1, 2, or 3'),
            ([1,2,3,4],  dict(conj='or'),  '1, 2, 3, or 4'),
        ]
)
def test_oxford_comma(given, kwargs, expected):
    assert stepwise.oxford_comma(given, **kwargs) == expected
