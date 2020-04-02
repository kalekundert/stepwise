#!/usr/bin/env python3

import pytest, arrow
import subprocess as subp
from pytest import raises
from stepwise import Protocol, ProtocolIO, ParseError
from utils import *

parse = Protocol.parse
merge = Protocol.merge

class MergeParams(Params):
    args = 'inputs, output'

    params_empty = [
            ####################################
            ([
                Protocol(),
            ],
                Protocol(),
            ),
            ####################################
            ([
                Protocol(),
                Protocol(),
            ],
                Protocol(),
            ),
            ####################################
    ]
    params_dates = [
            ####################################
            ([
                Protocol(
                    date=arrow.get(1988, 11, 8),
                ),
            ],
                Protocol(
                    date=arrow.get(1988, 11, 8),
                ),
            ),
            ####################################
            ([
                Protocol(
                    date=arrow.get(1988, 11, 8),
                ),
                Protocol(
                    date=arrow.get(1989, 9, 19),
                ),
            ],
                Protocol(
                    date=arrow.get(1989, 9, 19),
                ),
            ),
            ####################################
            ([
                Protocol(),
                Protocol(
                    date=arrow.get(1988, 11, 8),
                ),
            ],
                Protocol(
                    date=arrow.get(1988, 11, 8),
                ),
            ),
    ]
    params_commands = [
            ####################################
            ([
                Protocol(
                    commands=['command-1']
                ),
            ],
                Protocol(
                    commands=['command-1']
                ),
            ),
            ####################################
            ([
                Protocol(),
                Protocol(
                    commands=['command-1']
                ),
            ],
                Protocol(
                    commands=['command-1']
                ),
            ),
            ####################################
            ([
                Protocol(
                    commands=['command-1']
                ),
                Protocol(
                    commands=['command-2']
                ),
            ],
                Protocol(
                    commands=['command-1', 'command-2']
                ),
            ),
            ####################################
            ([
                Protocol(
                    commands=['command-1', 'command-2']
                ),
                Protocol(
                    commands=['command-3', 'command-4']
                ),
            ],
                Protocol(
                    commands=['command-1', 'command-2', 'command-3', 'command-4']
                ),
            ),
    ]
    params_steps = [
            ####################################
            ([
                Protocol(
                    steps=['Step 1'],
                ),
            ],
                Protocol(
                    steps=['Step 1'],
                ),
            ),
            ####################################
            ([
                'Step 1'
            ],
                Protocol(
                    steps=['Step 1'],
                ),
            ),
            ####################################
            ([
                Protocol(),
                Protocol(
                    steps=['Step 1'],
                ),
            ],
                Protocol(
                    steps=['Step 1'],
                ),
            ),
            ####################################
            ([
                Protocol(),
                'Step 1',
            ],
                Protocol(
                    steps=['Step 1'],
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step 1'],
                ),
                Protocol(
                    steps=['Step 2'],
                ),
            ],
                Protocol(
                    steps=['Step 1', 'Step 2'],
                ),
            ),
            ####################################
            ([
                'Step 1',
                'Step 2',
            ],
                Protocol(
                    steps=['Step 1', 'Step 2'],
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step 1', 'Step 2'],
                ),
                Protocol(
                    steps=['Step 3', 'Step 4'],
                ),
            ],
                Protocol(
                    steps=['Step 1', 'Step 2', 'Step 3', 'Step 4'],
                ),
            ),
            ####################################
            ([
                ['Step 1', 'Step 2'],
                ['Step 3', 'Step 4'],
            ],
                Protocol(
                    steps=['Step 1', 'Step 2', 'Step 3', 'Step 4'],
                ),
            ),
    ]
    params_footnotes = [
            ####################################
            ([
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Footnote A'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Footnote A'},
                ),
            ),
            ####################################
            ([
                Protocol(),
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Footnote A'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Footnote A'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Footnote A'},
                ),
                Protocol(
                    steps=['Step B'],
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B'],
                    footnotes={1: 'Footnote A'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A'],
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Footnote B'},
                ),
            ],
                Protocol(
                    steps=['Step A', 'Step B [1]'],
                    footnotes={1: 'Footnote B'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Footnote A'},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Footnote B'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [2]'],
                    footnotes={1: 'Footnote A', 2: 'Footnote B'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [2]'],
                    footnotes={2: 'Footnote A'},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Footnote B'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [2]'],
                    footnotes={1: 'Footnote A', 2: 'Footnote B'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1]', 'Step B [2]'],
                    footnotes={1: 'Footnote A', 2: 'Footnote B'},
                ),
                Protocol(
                    steps=['Step C [1]', 'Step D [2]'],
                    footnotes={1: 'Footnote C', 2: 'Footnote D'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [2]', 'Step C [3]', 'Step D [4]'],
                    footnotes={1: 'Footnote A', 2: 'Footnote B',
                               3: 'Footnote C', 4: 'Footnote D'},
                ),
            ),
    ]
    params_footnotes_shared = [
            ####################################
            ([
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Same footnote'},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [1]'],
                    footnotes={1: 'Same footnote'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [2]'],
                    footnotes={2: 'Same footnote'},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [1]'],
                    footnotes={1: 'Same footnote'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: 'Same footnote'},
                ),
                Protocol(
                    steps=['Step B [2]'],
                    footnotes={2: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [1]'],
                    footnotes={1: 'Same footnote'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [2]'],
                    footnotes={2: 'Same footnote'},
                ),
                Protocol(
                    steps=['Step B [2]'],
                    footnotes={2: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [1]'],
                    footnotes={1: 'Same footnote'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1] [2]',],
                    footnotes={1: 'Footnote 1', 2: 'Same footnote'},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1] [2]', 'Step B [2]'],
                    footnotes={1: 'Footnote 1', 2: 'Same footnote'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1] [2]',],
                    footnotes={1: 'Footnote 1', 2: 'Same footnote'},
                ),
                Protocol(
                    steps=['Step B [2]'],
                    footnotes={2: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1] [2]', 'Step B [2]'],
                    footnotes={1: 'Footnote 1', 2: 'Same footnote'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1] [2]',],
                    footnotes={1: 'Same footnote', 2: 'Footnote 2'},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1] [2]', 'Step B [1]'],
                    footnotes={1: 'Same footnote', 2: 'Footnote 2'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1] [2]',],
                    footnotes={1: 'Same footnote', 2: 'Footnote 2'},
                ),
                Protocol(
                    steps=['Step B [2]'],
                    footnotes={2: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1] [2]', 'Step B [1]'],
                    footnotes={1: 'Same footnote', 2: 'Footnote 2'},
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1] [2]',],
                    footnotes={1: 'Same footnote', 2: 'Footnote 2'},
                ),
                Protocol(
                    steps=['Step B [1] [2]'],
                    footnotes={1: 'Footnote 1', 2: 'Same footnote'},
                ),
            ],
                Protocol(
                    steps=['Step A [1] [2]', 'Step B [3] [1]'],
                    footnotes={1: 'Same footnote', 2: 'Footnote 2', 3: 'Footnote 1'}
                ),
            ),
            ####################################
            ([
                Protocol(
                    steps=['Step A [1] [2]',],
                    footnotes={1: 'Same footnote X', 2: 'Same footnote Y'},
                ),
                Protocol(
                    steps=['Step B [1] [2]'],
                    footnotes={1: 'Same footnote Y', 2: 'Same footnote Z'},
                ),
                Protocol(
                    steps=['Step C [1] [2]'],
                    footnotes={1: 'Same footnote Z', 2: 'Same footnote X'},
                ),
            ],
                Protocol(
                    steps=['Step A [1] [2]', 'Step B [2] [3]', 'Step C [3] [1]'],
                    footnotes={1: 'Same footnote X', 2: 'Same footnote Y', 3: 'Same footnote Z'}
                ),
            ),
            ####################################
    ]
    params_typecasts = [
            ####################################
            ([
                Protocol(steps=['Step 1']),
                'Step 2',
            ],
                Protocol(steps=['Step 1', 'Step 2']),
            ),
            ####################################
            ([
                Protocol(steps=['Step 1']),
                ['Step 2', 'Step 3'],
            ],
                Protocol(steps=['Step 1', 'Step 2', 'Step 3']),
            ),
            ####################################
            ([
                Protocol(steps=['Step 1']),
                ProtocolIO(
                    protocol=Protocol(steps=['Step 2']),
                    errors=0,
                )
            ],
                Protocol(
                    steps=['Step 1', 'Step 2'],
                ),
            ),
            ####################################
            ([
                Protocol(steps=['Step 1']),
                ProtocolIO(
                    protocol='Error',
                    errors=1,
                )
            ],
                Protocol(
                    steps=['Step 1'],
                ),
            ),
            ####################################
    ]

def test_repr():
    p = Protocol()
    assert repr(p) == 'Protocol(date=None, commands=[], steps=[], footnotes={})'

@MergeParams.parametrize
def test_merge(inputs, output):
    merged = merge(*inputs)
    assert merged.date == output.date
    assert merged.commands == output.commands
    assert merged.steps == output.steps
    assert merged.footnotes == output.footnotes

def test_merge_err():
    with raises(ParseError, match="cannot interpret 42 as a protocol"):
        Protocol.merge(42)

def test_append():
    a = Protocol(
            date=arrow.get(1988, 11, 8),
            commands=['command-1'],
            steps=['Step 1'],
            footnotes={1: 'Footnote A'},
    )
    b = Protocol(
            date=arrow.get(1989, 9, 19),
            commands=['command-2'],
            steps=['Step 2'],
            footnotes={1: 'Footnote B'},
    )
    a.append(b)

    assert a.date == arrow.get(1989, 9, 19)
    assert a.commands == ['command-1', 'command-2']
    assert a.steps == ['Step 1', 'Step 2']
    assert a.footnotes == {1: 'Footnote A', 2: 'Footnote B'}

def test_prepend():
    a = Protocol(
            date=arrow.get(1988, 11, 8),
            commands=['command-1'],
            steps=['Step 1'],
            footnotes={1: 'Footnote A'},
    )
    b = Protocol(
            date=arrow.get(1989, 9, 19),
            commands=['command-2'],
            steps=['Step 2'],
            footnotes={1: 'Footnote B'},
    )
    b.prepend(a)

    assert b.date == arrow.get(1989, 9, 19)
    assert b.commands == ['command-1', 'command-2']
    assert b.steps == ['Step 1', 'Step 2']
    assert b.footnotes == {1: 'Footnote A', 2: 'Footnote B'}

def test_add():
    p1 = Protocol(steps=["Step 1"])
    p2 = Protocol(steps=["Step 2"])
    p3 = p1 + p2

    assert p1.steps == ["Step 1"]
    assert p2.steps == ["Step 2"]
    assert p3.steps == ["Step 1", "Step 2"]

def test_iadd():
    p = Protocol()
    assert p.steps == []

    p += "Step 1"
    assert p.steps == ["Step 1"]

    # Do it again just to make sure the first addition didn't put the protocol 
    # into some kind of broken state.
    p += "Step 2"
    assert p.steps == ["Step 1", "Step 2"]

    p += ["Step 3", "Step 4"]
    assert p.steps == ["Step 1", "Step 2", "Step 3", "Step 4"]

    p += Protocol(steps=["Step 5"], footnotes={1: "Footnote 1"})
    assert p.steps == ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
    assert p.footnotes == {1: "Footnote 1"}

@parametrize_via_toml('test_protocol.toml')
def test_renumber_footnotes(new_ids, steps_before, footnotes_before, steps_after, footnotes_after):

    if isinstance(new_ids, dict):
        new_ids = int_keys(new_ids)
    if isinstance(new_ids, str) and new_ids.startswith('lambda'):
        new_ids = eval(new_ids)

    p = Protocol()
    p.steps = steps_before
    p.footnotes = int_keys(footnotes_before)
    p.renumber_footnotes(new_ids)
    assert p.steps == steps_after
    assert p.footnotes == int_keys(footnotes_after)

@parametrize_via_toml('test_protocol.toml')
def test_prune_footnotes(steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = int_keys(footnotes_before)
    p.prune_footnotes()
    assert p.steps == steps_after
    assert p.footnotes == int_keys(footnotes_after)

@parametrize_via_toml('test_protocol.toml')
def test_clear_footnotes(steps_before, steps_after, footnotes_before):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = int_keys(footnotes_before)
    p.clear_footnotes()
    assert p.steps == steps_after
    assert p.footnotes == {}

@parametrize_via_toml('test_protocol.toml')
def test_pick_slug(date, commands, expected):
    date = None if date is False else arrow.get(date)
    p = Protocol(date=date, commands=commands)
    assert p.pick_slug() == expected


def test_show_empty():
    p = Protocol()
    assert p.show() == ''

@parametrize_via_toml('test_protocol.toml')
def test_show_date(date, expected):
    p = Protocol()
    p.date = arrow.get(date)
    assert p.show() == expected.rstrip()

@parametrize_via_toml('test_protocol.toml')
def test_show_commands(commands, expected):
    p = Protocol()
    p.commands = commands
    assert p.show() == expected.rstrip()

@parametrize_via_toml('test_protocol.toml')
def test_show_steps(steps, expected):
    p = Protocol()
    p.steps = steps
    assert p.show() == expected.rstrip()

@parametrize_via_toml('test_protocol.toml')
def test_show_footnotes(footnotes, expected):
    p = Protocol()
    p.footnotes = int_keys(footnotes)
    assert p.show() == expected.rstrip()

def test_show_everything():
    """
    Just make sure the spacing between all the elements looks right.
    """
    p = Protocol()
    p.date = arrow.get(1988, 11, 8)
    p.commands = ['sw cmd-1', 'sw cmd-2']
    p.steps = ['Step 1', 'Step 2']
    p.footnotes = {1: 'Footnote 1', 2: 'Footnote 2'}
    assert p.show() == str(p)
    assert p.show() == """\
November 8, 1988

$ sw cmd-1
$ sw cmd-2

1. Step 1

2. Step 2

Notes:
[1] Footnote 1

[2] Footnote 2"""


@parametrize_via_toml('test_protocol.toml')
def test_parse_empty(text):
    p = parse(text)
    assert p.date == None
    assert p.commands == []
    assert p.steps == []
    assert p.footnotes == {}

@parametrize_via_toml('test_protocol.toml')
def test_parse_date(text, date):
    p = parse(text)
    assert p.date == arrow.get(date)

@parametrize_via_toml('test_protocol.toml')
def test_parse_commands(text, commands):
    p = parse(text)
    assert p.commands == commands

@parametrize_via_toml('test_protocol.toml')
def test_parse_commands_err(text, err):
    with raises(ParseError, match=err):
        parse(text)

@parametrize_via_toml('test_protocol.toml')
def test_parse_steps(text, steps):
    p = parse(text)
    assert p.steps == steps

@parametrize_via_toml('test_protocol.toml')
def test_parse_steps_err(err, text):
    with pytest.raises(ParseError, match=err):
        parse(text)

@parametrize_via_toml('test_protocol.toml')
def test_parse_footnotes(text, footnotes):
    p = parse(text)
    assert p.footnotes == int_keys(footnotes)

@parametrize_via_toml('test_protocol.toml')
def test_parse_footnotes_err(err, text):
    with pytest.raises(ParseError, match=err):
        parse(text)

def test_parse_everything():
    from io import StringIO

    s = """\
November 8, 1988

$ sw pcr
$ sw kld

- Step 1

- Step 2

Notes:
[1] Footnote 1

[2] Footnote 2
"""
    inputs = [
            s,
            StringIO(s),
            s.splitlines(),
    ]
    for input in inputs:
        p = parse(input)
        assert p.date == arrow.get(1988, 11, 8)
        assert p.commands == ['sw pcr', 'sw kld' ]
        assert p.steps == ['Step 1', 'Step 2']
        assert p.footnotes == {1: 'Footnote 1', 2: 'Footnote 2'}

def test_parse_err():
    with raises(ParseError, match="not <class 'int'>"):
        parse(1)


def int_keys(d):
    return {int(k): v for k, v in d.items()}
