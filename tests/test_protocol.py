#!/usr/bin/env python3

import pytest, arrow, stepwise
import subprocess as subp
from pytest import raises
from stepwise import Protocol, ProtocolIO, ParseError
from stepwise import pl, ul, ol, dl, pre, table
from math import inf
from param_helpers import *

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
                pl('Step 1')
            ],
                Protocol(
                    steps=[pl('Step 1')],
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
            ####################################
            ([
                Protocol(),
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: pre('Footnote A')},
                ),
            ],
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: pre('Footnote A')},
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
            ([
                Protocol(
                    steps=['Step A [1]'],
                    footnotes={1: pre('Same footnote')},
                ),
                Protocol(
                    steps=['Step B [1]'],
                    footnotes={1: pre('Same footnote')},
                ),
            ],
                Protocol(
                    steps=['Step A [1]', 'Step B [1]'],
                    footnotes={1: pre('Same footnote')}
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

def test_protocol_repr():
    p = Protocol()
    assert repr(p) == 'Protocol(date=None, commands=[], steps=[], footnotes={})'

@MergeParams.parametrize
def test_protocol_merge(inputs, output):
    merged = merge(*inputs)
    assert merged.date == output.date
    assert merged.commands == output.commands
    assert merged.steps == output.steps
    assert merged.footnotes == output.footnotes

def test_protocol_merge_err():
    with raises(ParseError, match="cannot interpret 42 as a protocol"):
        Protocol.merge(42)

def test_protocol_append():
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

def test_protocol_prepend():
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

def test_protocol_add():
    p1 = Protocol(steps=["Step 1"])
    p2 = Protocol(steps=["Step 2"])
    p3 = p1 + p2

    assert p1.steps == ["Step 1"]
    assert p2.steps == ["Step 2"]
    assert p3.steps == ["Step 1", "Step 2"]

def test_protocol_iadd():
    # The core functionality is tested by `test_protocol_merge()`; this just 
    # needs to make sure the `+=` syntax works.

    p = Protocol()
    assert p.steps == []

    p += "A"
    assert p.steps == ["A"]
    assert p[-1] == "A"

    # Do it again just to make sure the first addition didn't put the protocol 
    # into some kind of broken state.
    p += "B"
    assert p.steps == ["A", "B"]
    assert p[-1] == "B"

    p += ["C", "D"]
    assert p.steps == ["A", "B", "C", "D"]
    assert p[-1] == "D"

    p += pl("E")
    assert p.steps == ["A", "B", "C", "D", pl("E")]
    assert p[-1] == pl("E")

    p += [pl("F"), pl("G")]
    assert p.steps == ["A", "B", "C", "D", pl("E"), pl("F"), pl("G")]
    assert p[-1] == pl("G")

    p += Protocol(steps=["H"], footnotes={1: "h"})
    assert p.steps == ["A", "B", "C", "D", pl("E"), pl("F"), pl("G"), "H"]
    assert p.footnotes == {1: "h"}
    assert p[-1] == "H"

@parametrize_from_file(schema=Schema({str: eval_stepwise}))
def test_protocol_add_footnotes(footnotes_new, footnotes_before, footnotes_after, formatted_ids):
    p = Protocol()
    p.footnotes = footnotes_before

    assert p.add_footnotes(*footnotes_new) == formatted_ids
    assert p.footnotes == footnotes_after

@parametrize_from_file(
    schema=Schema({
        'steps_before': eval_stepwise,
        'footnotes_before': eval_stepwise,
        'footnotes_new': eval_stepwise,
        Optional('pattern', default='(?=[.:])'): str,
        **error_or({
            'steps_after': eval_stepwise,
            'footnotes_after': eval_stepwise,
        }),
    }),
)
def test_protocol_insert_footnotes(steps_before, footnotes_before, footnotes_new, pattern, steps_after, footnotes_after, error):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before

    with error:
        p.insert_footnotes(*footnotes_new, pattern=pattern)

        assert p.steps == steps_after
        assert p.footnotes == footnotes_after

@parametrize_from_file(schema=Schema({str: eval_stepwise}))
def test_protocol_renumber_footnotes(new_ids, steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before
    p.renumber_footnotes(new_ids)

    assert p.steps == steps_after
    assert p.footnotes == footnotes_after

@parametrize_from_file(schema=Schema({str: eval_stepwise}))
def test_protocol_merge_footnotes(steps_before, steps_after):
    p = Protocol()
    p.steps = steps_before
    p.merge_footnotes()
    assert p.steps == steps_after

@parametrize_from_file(schema=Schema({str: eval_stepwise}))
def test_protocol_prune_footnotes(steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before
    p.prune_footnotes()

    assert p.steps == steps_after
    assert p.footnotes == footnotes_after

@parametrize_from_file(schema=Schema({str: eval_stepwise}))
def test_protocol_clear_footnotes(steps_before, steps_after, footnotes_before):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before
    p.clear_footnotes()

    assert p.steps == steps_after
    assert p.footnotes == {}

@parametrize_from_file(
        schema=Schema({
            Optional('date', default=None): Or(None, arrow.get),
            Optional('commands', default=[]): [str],
            'expected': str,
        }),
)
def test_protocol_pick_slug(date, commands, expected):
    p = Protocol(date=date, commands=commands)
    assert p.pick_slug() == expected


def test_protocol_format_text_empty():
    p = Protocol()
    assert p.format_text(inf) == ''

@parametrize_from_file
def test_protocol_format_date(date, expected):
    p = Protocol()
    p.date = arrow.get(date)
    assert p.format_text(inf) == expected.rstrip()

@parametrize_from_file
def test_protocol_format_commands(commands, expected):
    p = Protocol()
    p.commands = commands
    assert p.format_text(inf) == expected.rstrip()

@parametrize_from_file(
        schema=Schema({
            'steps': eval_stepwise,
            'expected': str,
        }),
)
def test_protocol_format_steps(steps, expected):
    p = Protocol()
    p.steps = steps
    assert p.format_text(inf) == expected.rstrip()

@parametrize_from_file(
        schema=Schema({
            'footnotes': eval_stepwise,
            'expected': str,
        }),
)
def test_protocol_format_footnotes(footnotes, expected):
    p = Protocol()
    p.footnotes = footnotes
    assert p.format_text(inf) == expected.rstrip()

def test_protocol_format_everything():
    """
    Just make sure the spacing between all the elements looks right.
    """
    p = Protocol()
    p.date = arrow.get(1988, 11, 8)
    p.commands = ['sw cmd-1', 'sw cmd-2']
    p.steps = ['Step 1', 'Step 2']
    p.footnotes = {1: 'Footnote 1', 2: 'Footnote 2'}
    assert p.format_text(inf) == """\
November 8, 1988

$ sw cmd-1
$ sw cmd-2

1. Step 1

2. Step 2

Notes:
[1] Footnote 1

[2] Footnote 2"""


@parametrize_from_file
def test_protocol_parse_empty(text):
    p = parse(text)
    assert p.date == None
    assert p.commands == []
    assert p.steps == []
    assert p.footnotes == {}

@parametrize_from_file
def test_protocol_parse_date(text, date):
    p = parse(text)
    assert p.date == arrow.get(date)

@parametrize_from_file(
        schema=Schema({
            'text': str,
            **error_or({
                'commands': [str],
            }),
        }),
)
def test_protocol_parse_commands(text, commands, error):
    with error:
        p = parse(text)
        assert p.commands == commands

@parametrize_from_file(
        schema=Schema({
            'text': str,
            **error_or({
                'steps': [str],
            }),
        }),
)
def test_protocol_parse_steps(text, steps, error):
    with error:
        p = parse(text)
        assert p.steps == [pre(x) for x in steps]

@parametrize_from_file(
        schema=Schema({
            'text': str,
            **error_or({
                'footnotes': empty_ok({Coerce(int): str}),
            }),
        }),
)
def test_protocol_parse_footnotes(text, footnotes, error):
    with error:
        p = parse(text)
        assert p.footnotes == {k: pre(v) for k, v in footnotes.items()}

def test_protocol_parse_everything():
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
        assert p.steps == [pre('Step 1'), pre('Step 2')]
        assert p.footnotes == {1: pre('Footnote 1'), 2: pre('Footnote 2')}

def test_protocol_parse_err():
    with raises(ParseError, match="not <class 'int'>"):
        parse(1)

