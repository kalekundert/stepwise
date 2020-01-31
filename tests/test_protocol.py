#!/usr/bin/env python3

import pytest, arrow
from pytest import raises
from stepwise import parse, merge, Protocol, ParseError

def test_repr():
    p = Protocol()
    assert repr(p) == 'Protocol(date=None, commands=[], steps=[], footnotes={})'

@pytest.mark.parametrize(
        'input,steps', [
            ("Step 1",                   ["Step 1"]),
            (["Step 1", "Step 2"],       ["Step 1", "Step 2"]),
            (Protocol(steps=["Step 1"]), ["Step 1"]),
        ]
)
def test_from_anything(input, steps):
    p = Protocol.from_anything(input)
    assert p.steps == steps

@pytest.mark.parametrize(
        'inputs,output', [

            ####################################
            # Empty
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
            # Dates
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

            ####################################
            # Commands
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

            ####################################
            # Steps
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

            ####################################
            # Footnotes
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
        ]
)
def test_merge(inputs, output):
    merged = merge(*inputs)
    assert merged.date == output.date
    assert merged.commands == output.commands
    assert merged.steps == output.steps
    assert merged.footnotes == output.footnotes

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

@pytest.mark.parametrize(
        'start,steps_before,footnotes_before,steps_after,footnotes_after', [(
            1,
            [], {},
            [], {},
        ), (
            1,
            ['[1]'], {1: 'Footnote 1'},
            ['[1]'], {1: 'Footnote 1'},
        ), (
            2,
            ['[1]'], {1: 'Footnote 1'},
            ['[2]'], {2: 'Footnote 1'},
        ), (
            1,
            ['[2]'], {2: 'Footnote 1'},
            ['[1]'], {1: 'Footnote 1'},
        ), (
            2,
            ['[2]'], {2: 'Footnote 1'},
            ['[2]'], {2: 'Footnote 1'},
        ), (
            1,
            ['[1] [3]'], {1: 'Footnote 1', 3: 'Footnote 3'},
            ['[1] [2]'], {1: 'Footnote 1', 2: 'Footnote 3'},
        ), (
            2,
            ['[1] [3]'], {1: 'Footnote 1', 3: 'Footnote 3'},
            ['[2] [3]'], {2: 'Footnote 1', 3: 'Footnote 3'},
        ), (
            3,
            ['[1] [3]'], {1: 'Footnote 1', 3: 'Footnote 3'},
            ['[3] [4]'], {3: 'Footnote 1', 4: 'Footnote 3'},
        ), (
            1,
            ['[2] [3]'], {2: 'Footnote 2', 3: 'Footnote 3'},
            ['[1] [2]'], {1: 'Footnote 2', 2: 'Footnote 3'},
        ), (
            1,
            ['[3] [1]'], {1: 'Footnote 1', 3: 'Footnote 3'},
            ['[2] [1]'], {1: 'Footnote 1', 2: 'Footnote 3'},
        ), (
            1,
            ['[1,2]'], {1: 'Footnote 1', 2: 'Footnote 2'},
            ['[1,2]'], {1: 'Footnote 1', 2: 'Footnote 2'},
        ), (
            2,
            ['[1,2]'], {1: 'Footnote 1', 2: 'Footnote 2'},
            ['[2,3]'], {2: 'Footnote 1', 3: 'Footnote 2'},
        ), (
            1,
            ['[1-3]'], {1: 'Footnote 1', 2: 'Footnote 2', 3: 'Footnote 3'},
            ['[1-3]'], {1: 'Footnote 1', 2: 'Footnote 2', 3: 'Footnote 3'},
        ), (
            2,
            ['[1-3]'], {1: 'Footnote 1', 2: 'Footnote 2', 3: 'Footnote 3'},
            ['[2-4]'], {2: 'Footnote 1', 3: 'Footnote 2', 4: 'Footnote 3'},
        ), (
            1,
            ['[1,2,3]'], {1: 'Footnote 1', 2: 'Footnote 2', 3: 'Footnote 3'},
            ['[1-3]'],   {1: 'Footnote 1', 2: 'Footnote 2', 3: 'Footnote 3'},
        )]
)
def test_renumber_footnotes(start, steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before
    p.renumber_footnotes(start=start)
    assert p.steps == steps_after
    assert p.footnotes == footnotes_after

@pytest.mark.parametrize(
        'steps_before,footnotes_before,steps_after,footnotes_after', [(
            [], {},
            [], {},
        ), (
            ['[1]'], {1: 'Footnote 1'},
            ['[1]'], {1: 'Footnote 1'},
        ), (
            ['[1]'], {1: 'Footnote 1', 2: 'Footnote 2'},
            ['[1]'], {1: 'Footnote 1'},
        ), (
            ['[2]'], {1: 'Footnote 1', 2: 'Footnote 2'},
            ['[1]'], {1: 'Footnote 2'},
        )]
)
def test_prune_footnotes(steps_before, footnotes_before, steps_after, footnotes_after):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before
    p.prune_footnotes()
    assert p.steps == steps_after
    assert p.footnotes == footnotes_after

@pytest.mark.parametrize(
        'steps_before,steps_after,footnotes_before', [(
            [], [], {},
        ), (
            ['Step [1]:'],   ['Step:'], {1: 'Footnote 1'},
        ), (
            ['Step [1,2]:'], ['Step:'], {1: 'Footnote 1', 2: 'Footnote 2'},
        ), (
            ['Step [1-3]:'], ['Step:'], {1: 'Footnote 1', 2: 'Footnote 2', 3: 'Footnote 3'},
        ), (
            ['Some [1] idea.'], ['Some idea.'], {1: 'Footnote 1'},
        )]
)
def test_clear_footnotes(steps_before, steps_after, footnotes_before):
    p = Protocol()
    p.steps = steps_before
    p.footnotes = footnotes_before
    p.clear_footnotes()
    assert p.steps == steps_after
    assert p.footnotes == {}

@pytest.mark.parametrize(
        'date, commands, expected', [(
            None,
            [],
            'protocol',
        ), (
            None,
            ['command1 args'],
            'command1',
        ), (
            None,
            ['file1.txt'],
            'file1',
        ), (
            None,
            ['command1 args', 'file2.txt'],
            'command1_file2',
        ), (
            arrow.get(1988, 11, 8),
            [],
            '19881108',
        ), (
            arrow.get(1988, 11, 8),
            ['command1 args'],
            '19881108_command1',
        ), (
            arrow.get(1988, 11, 8),
            ['file1.txt'],
            '19881108_file1',
        ), (
            arrow.get(1988, 11, 8),
            ['command1 args', 'file2.txt'],
            '19881108_command1_file2',
        )]
)
def test_pick_slug(date, commands, expected):
    p = Protocol(date=date, commands=commands)
    assert p.pick_slug() == expected


def test_show_empty():
    p = Protocol()
    assert p.show() == ''

def test_show_date():
    p = Protocol()
    p.date = arrow.get(1988, 11, 8)
    assert p.show() == """\
November 8, 1988
"""

def test_show_commands():
    p = Protocol()
    p.commands.append('sw pcr')
    assert p.show() == """\
$ sw pcr
"""

    p.commands.append('sw kld')
    assert p.show() == """\
$ sw pcr
$ sw kld
"""

def test_show_steps():
    p = Protocol()
    p.steps.append('Step 1\nLine break')
    assert p.show() == """\
1. Step 1
   Line break
"""

    p.steps.append('Step 2\nAnother line break')
    assert p.show() == """\
1. Step 1
   Line break

2. Step 2
   Another line break
"""

    p.steps = ['A\nB' for _ in range(10)]
    assert p.show() == """\
 1. A
    B

 2. A
    B

 3. A
    B

 4. A
    B

 5. A
    B

 6. A
    B

 7. A
    B

 8. A
    B

 9. A
    B

10. A
    B
"""

@pytest.mark.parametrize(
        'footnotes,expected', [({
################
1: "Footnote 1",
}, """\
Note:
[1] Footnote 1
"""), ({
################
1: "Footnote 1",
2: "Footnote 2",
}, """\
Notes:
[1] Footnote 1

[2] Footnote 2
"""), ({
################
1: "Footnote 1\nLine wrap",
}, """\
Note:
[1] Footnote 1
    Line wrap
"""), ({
################
1: "Footnote 1\nLine wrap",
2: "Footnote 2\nAnother line wrap",
}, """\
Notes:
[1] Footnote 1
    Line wrap

[2] Footnote 2
    Another line wrap
"""), ({
################
1: "Footnote 1\nLine wrap",
10: "Footnote 10\nAnother line wrap",
}, """\
Notes:
 [1] Footnote 1
     Line wrap

[10] Footnote 10
     Another line wrap
""")
])
def test_show_footnotes(footnotes, expected):
    p = Protocol()
    p.footnotes = footnotes
    assert p.show() == expected

def test_show_everything():
    """
    Just make sure the spacing between all the elements looks right.
    """
    p = Protocol()
    p.date = arrow.get(1988, 11, 8)
    p.commands = ['sw pcr', 'sw kld']
    p.steps = ['Step 1', 'Step 2']
    p.footnotes = {1: 'Footnote 1', 2: 'Footnote 2'}
    assert p.show() == str(p)
    assert p.show() == """\
November 8, 1988

$ sw pcr
$ sw kld

1. Step 1

2. Step 2

Notes:
[1] Footnote 1

[2] Footnote 2
"""


@pytest.mark.parametrize(
        "text", [
            "",
            "\n",
            " \n ",
])
def test_parse_empty(text):
    p = parse(text)
    assert p.date == None
    assert p.commands == []
    assert p.steps == []
    assert p.footnotes == {}

@pytest.mark.parametrize(
        "date,text", [(

arrow.get(1988, 11, 8),
"""\
November 8, 1988
"""
), (

arrow.get(1988, 11, 8),
"""\

November 8, 1988
"""
), (

arrow.get(1988, 11, 8),
"""\
November 8, 1988

"""
)])
def test_parse_date(text, date):
    p = parse(text)
    assert p.date == date

@pytest.mark.parametrize(
        "commands,text", [(

['sw pcr'],
"""\
$ sw pcr
"""
), (

['sw pcr'],
"""\

$ sw pcr
"""
), (

['sw pcr'],
"""\
$ sw pcr

"""
), (

['sw pcr', 'sw kld'],
"""\
$ sw pcr
$ sw kld
"""
), (

['sw pcr', 'sw kld'],
"""\
$ sw pcr

$ sw kld
"""
)])
def test_parse_commands(text, commands):
    p = parse(text)
    assert p.commands == commands

@pytest.mark.parametrize(
        "err, text", [(

"expected a step",
"""\
$ sw pcr
unexpected text
"""
)])
def test_parse_commands_err(text, err):
    with raises(ParseError, match=err):
        parse(text)

@pytest.mark.parametrize(
        "steps,text", [(

['Step 1'],
"""\
- Step 1
"""
), (

['Step 1'],
"""\

- Step 1
"""
), (

['Step 1'],
"""\
- Step 1

"""
), (

['Step 1\nLine wrap'],
"""\
- Step 1
  Line wrap
"""
), (

['Step 1\n\nBlank line'],
"""\
- Step 1

  Blank line
"""
), (

['Step 1\n  Indented line'],
"""\
- Step 1
    Indented line
"""
), (

['Step 1\n- Substep 1'],
"""\
- Step 1
  - Substep 1
"""
), (

['Step 1', 'Step 2'],
"""\
- Step 1
- Step 2
"""
), (

['Step 1', 'Step 2'],
"""\
- Step 1

- Step 2
"""
), (

['Step 1'],
"""\
1. Step 1
"""
), (

['Step 1', 'Step 2'],
"""\
1. Step 1
2. Step 2
"""
), (

['Step 1', 'Step 2'],
"""\
 1. Step 1
 2. Step 2
"""
)])
def test_parse_steps(text, steps):
    p = parse(text)
    assert p.steps == steps

@pytest.mark.parametrize(
        'err,text', [(

"expected a step",
"""\
- Step 1
unexpected text
"""
), (

"expected a step",
"""\
  Fake line wrap
"""
)])
def test_parse_steps_err(err, text):
    with pytest.raises(ParseError, match=err):
        parse(text)

@pytest.mark.parametrize(
        'footnotes,text', [(

{},
"""\
Notes:
"""
), (

{1: 'Footnote 1'},
"""\
Notes:
[1] Footnote 1
"""
), (

{1: 'Footnote 1'},
"""\
Notes:

[1] Footnote 1
"""
), (

{1: 'Footnote 1'},
"""\
Notes:
[1] Footnote 1

"""
), (

{1: 'Footnote 1\nLine wrap'},
"""\
Notes:
[1] Footnote 1
    Line wrap
"""
), (

{1: 'Footnote 1\n  Indented line'},
"""\
Notes:
[1] Footnote 1
      Indented line
"""
), (

{1: 'Footnote 1\n\nBlank line'},
"""\
Notes:
[1] Footnote 1

    Blank line
"""
), (

{1: 'Footnote 1', 2: 'Footnote 2'},
"""\
Notes:
[1] Footnote 1
[2] Footnote 2
"""
), (

{1: 'Footnote 1', 2: 'Footnote 2'},
"""\
Notes:
[1] Footnote 1

[2] Footnote 2
"""
)])
def test_parse_footnotes(text, footnotes):
    p = parse(text)
    assert p.footnotes == footnotes

@pytest.mark.parametrize(
        'err,text', [(

"expected a footnote",
"""\
Notes:
unexpected text
"""
), (

"expected a footnote",
"""\
Notes:
[1] Footnote 1
unexpected text
"""
), (

"expected a footnote",
"""\
Notes:
   Fake line wrap
"""
), (

r"unknown footnote \[1\]",
"""\
- Step 1 [1]
"""
), (

r"unknown footnote \[2\]",
"""\
- Step 1 [2]

Footnotes:
[1] Footnote
"""
), (

r"unknown footnote \[2\]",
"""\
- Step 1 [1,2]

Footnotes:
[1] Footnote
"""
), (

r"unknown footnotes \[2,3\]",
"""\
- Step 1 [1-3]

Footnotes:
[1] Footnote
"""
)])
def test_parse_footnotes_err(err, text):
    with pytest.raises(ParseError, match=err):
        parse(text)

def test_parse_everything():
    p = parse("""\
November 8, 1988

$ sw pcr
$ sw kld

- Step 1

- Step 2

Notes:
[1] Footnote 1

[2] Footnote 2
""")
    assert p.date == arrow.get(1988, 11, 8)
    assert p.commands == ['sw pcr', 'sw kld' ]
    assert p.steps == ['Step 1', 'Step 2']
    assert p.footnotes == {1: 'Footnote 1', 2: 'Footnote 2'}



