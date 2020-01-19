#!/usr/bin/env python3

import pytest, re
import pandas as pd
from io import StringIO
from stepwise import MasterMix, Reaction, Reagent, Solvent, Quantity, Q
from stepwise import UserError

wx = 'w', '8 µL', {
        'w': ('5 µL',  ..., True),
        'x': ('3 µL', '2x', False),
}

def test_reagent_repr():
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    assert re.match(r"Reagent\(reaction=\d{4}, name='x'\)", repr(x))

def test_reagent_name():
    rxn = Reaction()

    x = Reagent(rxn, 'x')
    assert x.name == 'x'
    assert 'x' in rxn
    assert 'y' not in rxn

    x.name = 'y'
    assert x.name == 'y'
    assert 'x' not in rxn
    assert 'y' in rxn

@pytest.mark.parametrize(
        'given,expected', [
            (Q('1 µL'), Q('1 µL')),
            ((2, 'µL'), Q('2 µL')),
            (  '3 µL',  Q('3 µL')),
        ]
)
def test_reagent_volume(given, expected):
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    assert x.volume == None

    x.volume = given
    assert x.volume == expected

@pytest.mark.parametrize(
        'given,expected', [
            (Q('1 ng/µL'), Q('1 ng/µL')),
            ((2, 'ng/µL'), Q('2 ng/µL')),
            (  '3 ng/µL',  Q('3 ng/µL')),
        ]
)
def test_reagent_stock_conc(given, expected):
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    assert x.stock_conc == None

    x.stock_conc = given
    assert x.stock_conc == expected

@pytest.mark.parametrize(
        'volume, stock_conc, rxn_volume, expected', [
            ('1 µL', '10 ng/µL', '5 µL', Q('2 ng/µL')),
        ]
)
def test_reagent_conc(volume, stock_conc, rxn_volume, expected):
    rxn = Reaction()
    rxn.volume = rxn_volume

    x = Reagent(rxn, 'x')
    x.volume = volume
    x.stock_conc = stock_conc

    assert x.conc == expected

@pytest.mark.parametrize(
        'volume, stock_conc, rxn_volume, err', [
            (  None, '10 ng/µL', '5 µL', "no volume .* 'Reagent Name'"),
            ('1 µL',       None, '5 µL', "no stock .* 'Reagent Name'"),
            ('1 µL', '10 ng/µL',   None, "no reaction volume specified"),
        ]
)
def test_reagent_conc_raises(volume, stock_conc, rxn_volume, err):
    rxn = Reaction()
    x = Reagent(rxn, 'Reagent Name')

    if rxn_volume: rxn.volume = rxn_volume
    if volume:     x.volume = volume
    if stock_conc: x.stock_conc = stock_conc

    with pytest.raises(ValueError, match=err):
        x.conc

@pytest.mark.parametrize(
        'v1, s1, v2, s2', [
            ('1 µL', '10 ng/µL', '1 µL', '10 ng/µL'),
            ('1 µL', '10 ng/µL', '2 µL', '5 ng/µL'),
        ]
)
def test_reagent_hold_conc(v1, s1, v2, s2):
    rxn = Reaction()
    x = Reagent(rxn, 'x')

    x.volume = v1
    x.stock_conc = s1
    assert x.hold_conc.volume == v1
    assert x.hold_conc.stock_conc == s1

    x.hold_conc.volume = v2
    assert x.volume == v2
    assert x.stock_conc == s2

    x.volume = v1
    x.stock_conc = s1
    x.hold_conc.stock_conc = s2
    assert x.volume == v2
    assert x.stock_conc == s2

def test_reagent_hold_conc_in_place():
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    x.volume = '2 µL'
    x.stock_conc = '10 ng/µL'

    x.hold_conc.volume += '2 µL'
    assert x.stock_conc == '5 ng/µL'
    x.hold_conc.volume -= '2 µL'
    assert x.stock_conc == '10 ng/µL'
    x.hold_conc.volume *= 2
    assert x.stock_conc == '5 ng/µL'
    x.hold_conc.volume /= 2
    assert x.stock_conc == '10 ng/µL'

    x.hold_conc.stock_conc += '10 ng/µL'
    assert x.volume == '1 µL'
    x.hold_conc.stock_conc -= '10 ng/µL'
    assert x.volume == '2 µL'
    x.hold_conc.stock_conc *= 2
    assert x.volume == '1 µL'
    x.hold_conc.stock_conc /= 2
    assert x.volume == '2 µL'

@pytest.mark.parametrize(
        'rxn_volume, v1, s1, c1, s2, c2', [
            ('10 µL', '1 µL',  '10 ng/µL', '1 ng/µL',  '10 ng/µL', '1 ng/µL'),
            ('10 µL', '1 µL',  '10 ng/µL', '1 ng/µL',  '20 ng/µL', '2 ng/µL'),
        ]
)
def test_reagent_hold_volume(rxn_volume, v1, s1, c1, s2, c2):
    rxn = Reaction()
    rxn.volume = rxn_volume
    x = Reagent(rxn, 'x')

    # Set stock concentration:
    x.volume = v1
    x.stock_conc = s1
    assert x.conc == x.hold_volume.conc == c1
    assert x.hold_volume.stock_conc == s1

    x.hold_volume.stock_conc = s2
    assert x.volume == v1
    assert x.stock_conc == s2
    assert x.conc == c2

    # Set concentration:
    x.volume = v1
    x.stock_conc = s1

    x.hold_volume.conc = c2
    assert x.volume == v1
    assert x.stock_conc == s2
    assert x.conc == c2

def test_reagent_hold_volume_in_place():
    rxn = Reaction()
    rxn.volume = '10 µL'

    x = Reagent(rxn, 'x')
    x.volume = '1 µL'
    x.stock_conc = '10 ng/µL'
    assert x.conc == '1 ng/µL'

    x.hold_volume.conc += '1 ng/µL'
    assert x.stock_conc == '20 ng/µL'
    x.hold_volume.conc -= '1 ng/µL'
    assert x.stock_conc == '10 ng/µL'
    x.hold_volume.conc *= 2
    assert x.stock_conc == '20 ng/µL'
    x.hold_volume.conc /= 2
    assert x.stock_conc == '10 ng/µL'

    x.hold_volume.stock_conc += '10 ng/µL'
    assert x.conc == '2 ng/µL'
    x.hold_volume.stock_conc -= '10 ng/µL'
    assert x.conc == '1 ng/µL'
    x.hold_volume.stock_conc *= 2
    assert x.conc == '2 ng/µL'
    x.hold_volume.stock_conc /= 2
    assert x.conc == '1 ng/µL'

@pytest.mark.parametrize(
        'rxn_volume, s1, v1, c1, v2, c2', [
            ('10 µL', '10 ng/µL',  '1 µL', '1 ng/µL',  '1 µL', '1 ng/µL'),
            ('10 µL', '10 ng/µL',  '1 µL', '1 ng/µL',  '2 µL', '2 ng/µL'),
        ]
)
def test_reagent_hold_stock_conc(rxn_volume, s1, v1, c1, v2, c2):
    rxn = Reaction()
    rxn.volume = rxn_volume
    x = Reagent(rxn, 'x')

    # Set volume:
    x.volume = v1
    x.stock_conc = s1
    assert x.conc == x.hold_stock_conc.conc == c1
    assert x.hold_stock_conc.volume == v1

    x.hold_stock_conc.volume = v2
    assert x.volume == v2
    assert x.stock_conc == s1
    assert x.conc == c2

    # Set concentration:
    x.volume = v1
    x.stock_conc = s1
    x.hold_stock_conc.conc = c2
    assert x.volume == v2
    assert x.stock_conc == s1
    assert x.conc == c2

def test_reagent_hold_stock_conc_in_place():
    rxn = Reaction()
    rxn.volume = '10 µL'

    x = Reagent(rxn, 'x')
    x.volume = '1 µL'
    x.stock_conc = '10 ng/µL'
    assert x.conc == '1 ng/µL'

    x.hold_stock_conc.volume += '1 µL'
    assert x.conc == '2 ng/µL'
    x.hold_stock_conc.volume -= '1 µL'
    assert x.conc == '1 ng/µL'
    x.hold_stock_conc.volume *= 2
    assert x.conc == '2 ng/µL'
    x.hold_stock_conc.volume /= 2
    assert x.conc == '1 ng/µL'

    x.hold_stock_conc.conc += '1 ng/µL'
    assert x.volume == '2 µL'
    x.hold_stock_conc.conc -= '1 ng/µL'
    assert x.volume == '1 µL'
    x.hold_stock_conc.conc *= 2
    assert x.volume == '2 µL'
    x.hold_stock_conc.conc /= 2
    assert x.volume == '1 µL'

def test_reagent_master_mix():
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    assert not x.master_mix

    x.master_mix = True
    assert x.master_mix

    x.master_mix = False
    assert not x.master_mix

def test_reagent_order():
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    assert x.order == None

    x.order = 1
    assert x.order == 1


def test_solvent_name():
    rxn = Reaction()
    rxn.solvent = 'w'

    rxn['x']
    w = rxn['w']
    rxn['y']

    assert w.name == 'w'

    # Set the name without changing it.  This shouldn't cause problems:
    rxn.solvent = 'w'

    # Rename the solvent via the reaction:
    rxn.solvent = 'w2'
    assert 'w' not in rxn
    assert 'w2' in rxn
    assert rxn['w2'] is w
    assert rxn['w2'].name == 'w2'

    # Rename the solvent via itself:
    w.name = 'w3'
    assert 'w' not in rxn
    assert 'w2' not in rxn
    assert 'w3' in rxn
    assert rxn['w3'] is w
    assert rxn['w3'].name == 'w3'

def test_solvent_volume():
    rxn = Reaction()
    rxn.solvent = 'w'
    rxn.volume = '10 µL'

    rxn['x'].volume = '1 µL'
    assert rxn['w'].volume == '9 µL'

    rxn['x'].volume = '2 µL'
    assert rxn['w'].volume == '8 µL'

    rxn['y'].volume = '1 µL'
    assert rxn['w'].volume == '7 µL'

    rxn['x'].volume = None
    with pytest.raises(ValueError):
        rxn['w'].volume

def test_solvent_unset():
    rxn = Reaction()
    rxn.solvent = 'w'
    assert len(rxn) == 1

    rxn.solvent = None
    assert len(rxn) == 0


def test_reaction_repr():
    rxn = Reaction()
    rxn.solvent = None
    assert repr(rxn) == "Reaction()"

    rxn.solvent = 'w'
    assert repr(rxn) == "Reaction('w')"

    rxn['x']
    assert repr(rxn) == "Reaction('w', 'x')"

    rxn['y']
    assert repr(rxn) == "Reaction('w', 'x', 'y')"

    rxn['w']
    assert repr(rxn) == "Reaction('x', 'y', 'w')"

def test_reaction_iter():
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    rxn.solvent = None
    assert as_list(rxn) == []

    rxn.solvent = 'w'
    assert as_list(rxn) == ['w']

    rxn['x']
    assert as_list(rxn) == ['w', 'x']

    rxn['y']
    assert as_list(rxn) == ['w', 'x', 'y']

    rxn['w']
    assert as_list(rxn) == ['x', 'y', 'w']

@pytest.mark.parametrize(
        'x,y,solvent,expected', [
            (None, None, 'w', ['w', 'x', 'y']),
            (None,    1, 'w', ['w', 'y', 'x']),
            (   1, None, 'w', ['w', 'x', 'y']),
            (   1,    1, 'w', ['w', 'x', 'y']),
            (   1,    2, 'w', ['w', 'x', 'y']),
            (   2,    1, 'w', ['w', 'y', 'x']),
        ]
)
def test_reaction_iter_sorting(x, y, solvent, expected):
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    rxn.solvent = solvent
    rxn['x'].order = x
    rxn['y'].order = y
    assert as_list(rxn) == expected

def test_reaction_iter_sorting_solvent():
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    rxn.solvent = 'w'
    rxn['x']
    assert as_list(rxn) == ['w', 'x']

    rxn = Reaction()
    rxn.solvent = 'w'
    rxn['w']
    rxn['x']
    assert as_list(rxn) == ['w', 'x']

    rxn = Reaction()
    rxn.solvent = 'w'
    rxn['x']
    rxn['w']
    assert as_list(rxn) == ['x', 'w']

    rxn = Reaction()
    rxn.solvent = 'w'
    rxn['x'].order = 2
    rxn['w'].order = 1
    assert as_list(rxn) == ['w', 'x']

    rxn = Reaction()
    rxn.solvent = 'w'
    rxn['w'].order = 2
    rxn['x'].order = 1
    assert as_list(rxn) == ['x', 'w']

def test_reaction_len_contains():
    rxn = Reaction()
    rxn.solvent = None

    assert len(rxn) == 0
    assert 'x' not in rxn
    assert 'y' not in rxn
    assert 'w' not in rxn

    rxn['x']
    assert len(rxn) == 1
    assert 'x' in rxn
    assert 'y' not in rxn
    assert 'w' not in rxn

    rxn['y']
    assert len(rxn) == 2
    assert 'x' in rxn
    assert 'y' in rxn
    assert 'w' not in rxn

    rxn.solvent = 'w'
    assert len(rxn) == 3
    assert 'x' in rxn
    assert 'y' in rxn
    assert 'w' in rxn

    rxn['w']
    assert len(rxn) == 3
    assert 'x' in rxn
    assert 'y' in rxn
    assert 'w' in rxn

def test_reaction_getitem():
    rxn = Reaction()
    assert isinstance(rxn['x'], Reagent)
    assert rxn['x'] is rxn['x']
    assert rxn['x'].name == 'x'

    rxn.solvent = 'w'
    assert isinstance(rxn['w'], Solvent)
    assert rxn['w'] is rxn['w']
    assert rxn['w'].name == rxn.solvent == 'w'

def test_reaction_delitem():
    rxn = Reaction()
    rxn.solvent = 'w'

    rxn['x']
    assert 'x' in rxn
    assert 'w' in rxn

    del rxn['x']
    assert 'x' not in rxn

    del rxn['w']
    assert 'w' not in rxn
    assert rxn.solvent == None

@pytest.mark.parametrize(
        'given,expected', [
            (Q('1 µL'), Q('1 µL')),
            ((2, 'µL'), Q('2 µL')),
            (  '3 µL',  Q('3 µL')),
        ]
)
def test_reaction_volume(given, expected):
    rxn = Reaction()
    assert rxn.volume == None

    rxn.volume = given
    assert rxn.volume == expected

def test_reaction_volume_raises():
    rxn = Reaction()
    rxn.volume  # doesn't raise

    rxn.solvent = None
    with pytest.raises(ValueError, match="no solvent specified"):
        rxn.volume  # raises

def test_reaction_solvent():
    rxn = Reaction()
    rxn.solvent = 'w'
    assert rxn['w'].master_mix == False
    assert rxn['w'].order == None

    rxn['w'].master_mix = True
    rxn['w'].order = 1
    assert rxn['w'].master_mix == True
    assert rxn['w'].order == 1

@pytest.mark.parametrize(
        'v1,r1,v2,r2', [
            ('5 µL', {}, '10 µL', {}),
            ('5 µL', {'x': '1 µL'}, '10 µL', {'x': '2 µL'}),
        ]
)
def test_reaction_hold_ratios(v1, r1, v2, r2):
    rxn = Reaction()
    rxn.volume = v1
    for k, v in r1.items():
        rxn[k].volume = v

    # Set the volume without scaling the reagents:
    rxn.volume = v2
    assert rxn.volume == v2
    assert rxn.hold_ratios.volume == v2
    for k, v in r1.items():
        assert rxn[k].volume == v

    # Set the volume and scale the reagents:
    rxn.volume = v1
    rxn.hold_ratios.volume = v2
    assert rxn.volume == v2
    assert rxn.hold_ratios.volume == v2
    for k, v in r2.items():
        assert rxn[k].volume == v

def test_reaction_hold_ratios_in_place():
    rxn = Reaction()
    rxn.volume = '10 µL'
    rxn['x'].volume = '2 µL'

    rxn.hold_ratios.volume += '5 µL'
    assert rxn.volume == '15 µL'
    assert rxn['x'].volume == '3 µL'

    rxn.hold_ratios.volume -= '5 µL'
    assert rxn.volume == '10 µL'
    assert rxn['x'].volume == '2 µL'

    rxn.hold_ratios.volume *= 2
    assert rxn.volume == '20 µL'
    assert rxn['x'].volume == '4 µL'

    rxn.hold_ratios.volume /= 2
    assert rxn.volume == '10 µL'
    assert rxn['x'].volume == '2 µL'
@pytest.mark.parametrize(
        'csv,solvent,volume,reagents', [(

        # Solvent only
            "Reagent,Stock,Volume,MM?\n"
            "w,,5 µL,yes\n"
            ,
                'w', '5 µL', {
                    'w': ('5 µL', ..., True),
                },
        ), (

        # Reagent only:
            "Reagent,Stock,Volume,MM?\n"
            "x,2x,3 µL,no\n"
            , 
                'w', None, {
                    'w': (   ...,  ...,   ...),
                    'x': ('3 µL', '2x', False),
                },
        ), (

        # Solvent and reagent:
            "Reagent,Stock,Volume,MM?\n"
            "w,,5 µL,yes\n"
            "x,2x,3 µL,no\n"
            ,
            *wx,
        ), (

        # Column aliases:
            "Reagent,Stock Conc,Volume,MM?\n"
            "w,,5 µL,yes\n"
            "x,2x,3 µL,no\n"
            ,
            *wx,
        ), (
            "Reagent,Stock,Volume,Master Mix\n"
            "w,,5 µL,yes\n"
            "x,2x,3 µL,no\n"
            ,
            *wx,
        ), (

        # Out-of-order columns:
            "Reagent,Volume,Stock,MM?\n"
            "w,5 µL,,yes\n"
            "x,3 µL,2x,no\n"
            ,
            *wx
        ), (

        # Extra columns:
            "Reagent,Stock,Volume,MM?,Note\n"
            "w,,5 µL,yes,lorem ipsum\n"
            "x,2x,3 µL,no\n"
            ,
            *wx,
        ), (

        # Optional columns:
            "Reagent,Stock,Volume\n"
            "w,,5 µL\n"
            "x,2x,3 µL\n"
            ,
                'w', '8 µL', {
                    'w': ('5 µL',  ..., False),
                    'x': ('3 µL', '2x', False),
                }
        ), (

        # Undefined values:
            "Reagent,Stock Conc,Volume,MM?\n"
            "w,,,yes\n"
            "x,2x,3 µL,no\n"
            ,
                'w', None, {
                    'w': (   ...,  ..., True),
                    'x': ('3 µL', '2x', False),
                }
        ), (
            "Reagent,Stock,Volume,MM?\n"
            "w,,5 µL,yes\n"
            "x,,3 µL,no\n"
            ,
                'w', '8 µL', {
                    'w': ('5 µL',  ..., True),
                    'x': ('3 µL', None, False),
                }
        ), (
            "Reagent,Stock,Volume,MM?\n"
            "w,,5 µL,yes\n"
            "x,2x,,no\n"
            ,
                'w', None, {
                    # The solvent loses its volume because the volume of the 
                    # reaction isn't defined.
                    'w': (   ...,  ..., True),
                    'x': (  None, '2x', False),
                }
        ), (
            "Reagent,Stock,Volume,MM?\n"
            "w,,5 µL,\n"
            "x,2x,3 µL,no\n"
            ,
                'w', '8 µL', {
                    'w': ('5 µL',  ..., False),
                    'x': ('3 µL', '2x', False),
                }
        )]
)
def test_reaction_from_csv(csv, solvent, volume, reagents):
    rxn = Reaction.from_csv(StringIO(csv), solvent)

    assert len(rxn) == len(reagents)
    assert rxn.volume == volume

    for name, expected in reagents.items():
        volume, stock_conc, master_mix = expected
        if volume != ...:     assert rxn[name].volume == volume
        if stock_conc != ...: assert rxn[name].stock_conc == stock_conc
        if master_mix != ...: assert rxn[name].master_mix == master_mix

@pytest.mark.parametrize(
        'csv,solvent,err', [(
            "Reagent,Stock,Volume,MM?",
            'w',
            "at least one reagent",
        ), (
            "Reagent,Stock,Volume,MM?\n,10x,1 µL,yes",
            'w',
            "missing names",
        ), (
            "Stock,Volume,MM?\n10x,1 µL,yes",
            'w',
            "no 'Reagent' column",
        ), (
            "Reagent,Volume,MM?\nx,1 µL,yes",
            'w',
            "no 'Stock Conc' column",
        ), (
            "Reagent,Stock,MM?\nx,10x,yes",
            'w',
            "no 'Volume' column",
        ), (
            "Reagent,Stock,Volume,MM?\nw,10x,1 µL,yes",
            'w',
            "stock conc.* 'w'",
        ), (
            "Reagent,Stock,Volume,MM?\nx,10x,1 µL,maybe",
            'w',
            "expected 'yes' or 'no', got 'maybe'",
        )]
)
def test_reaction_from_csv_raises(csv, solvent, err):
    with pytest.raises(UserError, match=err):
        Reaction.from_csv(StringIO(csv), solvent)

@pytest.mark.parametrize(
        'text,solvent,volume,reagents', [(

        # Solvent only
            "Reagent  Stock  Volume  MM?\n"
            "=======  =====  ======  ===\n"
            "w                 5 µL  yes\n"
            "x           2x    3 µL   no\n"
            ,
            *wx
        )]
)
def test_reaction_from_text(text, solvent, volume, reagents):
    rxn = Reaction.from_text(text, solvent)

    assert len(rxn) == len(reagents)
    assert rxn.volume == volume

    for name, expected in reagents.items():
        volume, stock_conc, master_mix = expected
        if volume != ...:     assert rxn[name].volume == volume
        if stock_conc != ...: assert rxn[name].stock_conc == stock_conc
        if master_mix != ...: assert rxn[name].master_mix == master_mix

@pytest.mark.parametrize(
        'text,err', [(

        # Not enough lines:
            ""
            ,
            "has 0 lines",
        ), (
            ""
            "Reagent  Stock  Volume  MM?\n"
            ,
            "has 1 line",
        ), (
            ""
            "Reagent  Stock  Volume  MM?\n"
            "=======  =====  ======  ===\n"
            ,
            "has 2 lines",
        ), (

        # Malformed underline:
            ""
            "Reagent  Stock  Volume  MM?\n"
            "~~~~~~~  ~~~~~  ~~~~~~  ~~~\n"
            "w                 5 µL  yes\n"
            "x           2x    3 µL   no\n"
            ,
            "not '~~~",
        )]
)
def test_reaction_from_text_raises(text, err):
    with pytest.raises(UserError, match=err):
        Reaction.from_text(text)


def test_master_mix_getattr():
    mm = MasterMix()

    mm.reaction.volume = '1 µL'
    assert mm.volume == '1 µL'

    mm.reaction.solvent = 'w'
    assert mm.solvent == 'w'

    # Not testing `hold_ratios` because it makes a new object every time.

def test_master_mix_getattr_raises():
    mm = MasterMix()

    with pytest.raises(AttributeError, match="'MasterMix' object has no attribute 'undefined'"):
        mm.undefined

    # Try to trick to code that munges the error message.
    with pytest.raises(AttributeError, match="'MasterMix' object has no attribute 'Reaction'"):
        mm.Reaction

def test_master_mix_setattr():
    mm = MasterMix()

    mm.volume = '1 µL'
    assert mm.reaction.volume == '1 µL'

    mm.solvent = 'w'
    assert mm.reaction.solvent == 'w'

def test_master_mix_dunder():
    # Just quickly call all the dunders to make sure they're doing something.  
    # The `test_reaction_...()` tests make sure these methods actually work.
    mm = MasterMix()
    mm.solvent = 'w'

    # `__repr__()`
    assert repr(mm) == "MasterMix('w')"

    # `__getitem__()`
    mm['x'].volume = '1 µL'
    assert mm.reaction['x'].volume == '1 µL'

    # `__iter__()`
    for reagent, expected in zip(mm, ['w', 'x']):
        assert reagent.name == expected

    # `__contains__()`
    assert 'w' in mm
    assert 'x' in mm
    assert 'y' not in mm

    # `__len__()`
    assert len(mm) == 2

    # `__delitem__()`
    del mm['x']
    assert len(mm) == 1

@pytest.mark.parametrize(
        'params', [
            dict(n=10, fraction=0.1,  reactions=0,  expected=11),
            dict(n=10, fraction=0.0,  reactions=2,  expected=12),
            dict(n=10, fraction=0.1,  reactions=2,  expected=12),
            dict(n=10, fraction=0.3,  reactions=2,  expected=13),

            dict(n=10, percent=10,    reactions=0,  expected=11),
            dict(n=10, percent=0,     reactions=2,  expected=12),
            dict(n=10, percent=10,    reactions=2,  expected=12),
            dict(n=10, percent=30,    reactions=2,  expected=13),
        ]
)
def test_master_mix_extra(params):
    mm = MasterMix()
    mm.num_reactions = params['n']

    if 'fraction' in params:
        mm.extra_fraction = params['fraction']
        assert mm.extra_percent == pytest.approx(params['fraction'] * 100)
    if 'percent' in params:
        mm.extra_percent = params['percent']
        assert mm.extra_fraction == pytest.approx(params['percent'] / 100)
    if 'reactions' in params:
        mm.extra_reactions = params['reactions']

    assert mm.extra_factor == pytest.approx(params['expected'])

def test_master_mix_show():
    mm = MasterMix.from_text("""\
Reagent  Stock  Volume  MM?
=======  =====  ======  ===
water             7 µL  yes
buffer     10x    1 µL  yes
enzyme      5x    2 µL   no
""")

    mm.num_reactions = 1
    assert str(mm) == """\
Reagent  Stock    Volume
────────────────────────
water            7.00 µL
buffer     10x   1.00 µL
enzyme      5x   2.00 µL
────────────────────────
                10.00 µL"""

    mm.num_reactions = 2
    mm.extra_fraction = 0
    mm.extra_reactions = 0
    assert str(mm) == """\
Reagent  Stock    Volume        2x
──────────────────────────────────
water            7.00 µL  14.00 µL
buffer     10x   1.00 µL   2.00 µL
enzyme      5x   2.00 µL          
──────────────────────────────────
                10.00 µL   8.00 µL/rxn"""

    mm.show_master_mix = False
    mm.show_1x = True
    mm.show_totals = True
    assert str(mm) == """\
Reagent  Stock    Volume
────────────────────────
water            7.00 µL
buffer     10x   1.00 µL
enzyme      5x   2.00 µL
────────────────────────
                10.00 µL"""

    mm.show_master_mix = True
    mm.show_1x = False
    mm.show_totals = True
    assert str(mm) == """\
Reagent  Stock        2x
────────────────────────
water           14.00 µL
buffer     10x   2.00 µL
enzyme      5x          
────────────────────────
                 8.00 µL/rxn"""

    mm.show_master_mix = True
    mm.show_1x = True
    mm.show_totals = False
    assert str(mm) == """\
Reagent  Stock    Volume        2x
──────────────────────────────────
water            7.00 µL  14.00 µL
buffer     10x   1.00 µL   2.00 µL
enzyme      5x   2.00 µL          """

