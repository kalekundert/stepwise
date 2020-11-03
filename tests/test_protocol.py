#!/usr/bin/env python3

import pytest, arrow, stepwise
import subprocess as subp
from pytest import raises
from unittest.mock import Mock
from stepwise import Protocol, Step, Footnote, ProtocolIO, ParseError
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
    p = Protocol()
    assert p.steps == []

    p += "Step 1"
    assert p.steps == ["Step 1"]
    assert p.s == p.step == "Step 1"

    # Do it again just to make sure the first addition didn't put the protocol 
    # into some kind of broken state.
    p += "Step 2"
    assert p.steps == ["Step 1", "Step 2"]
    assert p.s == p.step == "Step 2"

    p += ["Step 3", "Step 4"]
    assert p.steps == ["Step 1", "Step 2", "Step 3", "Step 4"]
    assert p.s == p.step == "Step 4"

    p += Protocol(steps=["Step 5"], footnotes={1: "Footnote 1"})
    assert p.steps == ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
    assert p.footnotes == {1: "Footnote 1"}
    assert p.s == p.step == "Step 5"

@parametrize_via_toml('test_protocol.toml')
def test_protocol_renumber_footnotes(new_ids, steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = eval_steps(steps_before)
    p.footnotes = eval_footnotes(footnotes_before)
    p.renumber_footnotes(eval(new_ids))

    assert p.steps == eval_steps(steps_after)
    assert p.footnotes == eval_footnotes(footnotes_after)

@parametrize_via_toml('test_protocol.toml')
def test_protocol_prune_footnotes(steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = eval_steps(steps_before)
    p.footnotes = eval_footnotes(footnotes_before)
    p.prune_footnotes()

    assert p.steps == eval_steps(steps_after)
    assert p.footnotes == eval_footnotes(footnotes_after)

@parametrize_via_toml('test_protocol.toml')
def test_protocol_clear_footnotes(steps_before, steps_after, footnotes_before):
    p = Protocol()
    p.steps = eval_steps(steps_before)
    p.footnotes = eval_footnotes(footnotes_before)
    p.clear_footnotes()

    assert p.steps == eval_steps(steps_after)
    assert p.footnotes == {}

@parametrize_via_toml('test_protocol.toml')
def test_protocol_pick_slug(date, commands, expected):
    date = None if date is False else arrow.get(date)
    p = Protocol(date=date, commands=commands)
    assert p.pick_slug() == expected


def test_protocol_show_empty():
    p = Protocol()
    assert p.show() == ''

@parametrize_via_toml('test_protocol.toml')
def test_protocol_show_date(date, expected):
    p = Protocol()
    p.date = arrow.get(date)
    assert p.show() == expected.rstrip()

@parametrize_via_toml('test_protocol.toml')
def test_protocol_show_commands(commands, expected):
    p = Protocol()
    p.commands = commands
    assert p.show() == expected.rstrip()

@parametrize_via_toml('test_protocol.toml')
def test_protocol_show_steps(steps, expected):
    p = Protocol()
    p.steps = eval_steps(steps)
    assert p.show() == expected.rstrip()

@parametrize_via_toml('test_protocol.toml')
def test_protocol_show_footnotes(footnotes, expected):
    p = Protocol()
    p.footnotes = eval_footnotes(footnotes)
    assert p.show() == expected.rstrip()

def test_protocol_show_everything():
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
def test_protocol_parse_empty(text):
    p = parse(text)
    assert p.date == None
    assert p.commands == []
    assert p.steps == []
    assert p.footnotes == {}

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_date(text, date):
    p = parse(text)
    assert p.date == arrow.get(date)

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_commands(text, commands):
    p = parse(text)
    assert p.commands == commands

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_commands_err(text, err):
    with raises(ParseError, match=err):
        parse(text)

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_steps(text, steps):
    p = parse(text)
    assert p.steps == steps

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_steps_err(err, text):
    with pytest.raises(ParseError, match=err):
        parse(text)

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_footnotes(text, footnotes):
    p = parse(text)
    assert p.footnotes == int_keys(footnotes)

@parametrize_via_toml('test_protocol.toml')
def test_protocol_parse_footnotes_err(err, text):
    with pytest.raises(ParseError, match=err):
        parse(text)

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
        assert p.steps == ['Step 1', 'Step 2']
        assert p.footnotes == {1: 'Footnote 1', 2: 'Footnote 2'}

def test_protocol_parse_err():
    with raises(ParseError, match="not <class 'int'>"):
        parse(1)


def test_step_iadd():
    s = Step("Paragraph 1")
    assert s.paragraphs == ["Paragraph 1"]
    assert s.substeps == []

    s.body += "Paragraph 2"
    assert s.paragraphs == ["Paragraph 1", "Paragraph 2"]
    assert s.substeps == []

    s += "Substep 1"
    assert s.paragraphs == ["Paragraph 1", "Paragraph 2"]
    assert s.substeps == ["Substep 1"]

    s += "Substep 2"
    assert s.paragraphs == ["Paragraph 1", "Paragraph 2"]
    assert s.substeps == ["Substep 1", "Substep 2"]

@parametrize_via_toml('test_protocol.toml')
def test_step_format_text(paragraphs, substeps, width, wrap, expected):
    s = Step()
    s.paragraphs = [eval(x) for x in paragraphs]
    s.substeps = [eval(x) for x in substeps]
    s.wrap = wrap
    assert s.format_text(width) == expected

@parametrize_via_toml('test_protocol.toml')
def test_step_replace_text(paragraphs, substeps, pattern, repl, expected):
    from math import inf

    s = Step()
    s.paragraphs = [eval(x) for x in paragraphs]
    s.substeps = [eval(x) for x in substeps]

    s.replace_text(pattern, repl)

    assert s.format_text(inf) == expected


@parametrize_via_toml('test_protocol.toml')
def test_footnote_format_text(note, width, expected):
    assert Footnote(note).format_text(width) == expected


@parametrize_via_toml('test_protocol.toml')
def test_format_text_str(str, width, wrap_str, expected):
    assert expected == stepwise.format_text(
            str,
            width,
            wrap_str=wrap_str,
    )

def test_format_text_obj():

    class Interface:
        def format_text(self, width):
            pass

    obj = Mock(spec_set=Interface)
    wrapped = obj.format_text.return_value = Mock()
    width = 10

    assert stepwise.format_text(obj, width) is wrapped
    assert obj.format_text.called == 1
    assert obj.format_text.call_args == ((width,), {})

@parametrize_via_toml('test_protocol.toml')
def test_format_list_item_str(str, width, wrap_str, expected):
    assert stepwise.format_list_item(str, width, wrap_str=wrap_str) == expected

def test_format_list_item_obj():

    class Interface:
        def format_text(self, width):
            pass

    obj = Mock(spec_set=Interface)
    wrapped = obj.format_text.return_value = "lorem ipsum"
    width = 10

    assert stepwise.format_list_item(obj, width) == "- lorem ipsum"
    assert obj.format_text.called == 1
    assert obj.format_text.call_args == ((width - 2,), {})

@parametrize_via_toml('test_protocol.toml')
def test_replace_text_str(str, pattern, repl, expected):
    assert stepwise.replace_text(pattern, repl, str) == expected

def test_replace_text_obj():

    class Interface:
        def replace_text(self, pattern, repl):
            pass

    obj = Mock(spec_set=Interface)

    assert stepwise.replace_text('pattern', 'repl', obj) is obj
    assert obj.replace_text.called == 1
    assert obj.replace_text.call_args == (('pattern', 'repl'), {})


def eval_steps(steps):
    return [eval(x) for x in steps]

def eval_footnotes(footnotes):
    return {int(k): eval(v) for k, v in footnotes.items()}

def int_keys(d):
    return {int(k): v for k, v in d.items()}
