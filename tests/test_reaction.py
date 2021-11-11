#!/usr/bin/env python3

import pytest, re
from io import StringIO
from stepwise import MasterMix, Reaction, Reagent, Solvent, Quantity, Q
from stepwise import UsageError
from param_helpers import *

wx = '8 µL', {
        'w': ('5 µL',  ..., True),
        'x': ('3 µL', '2x', False),
}

def test_reagent_repr():
    rxn = Reaction()
    x = Reagent(rxn, 'x')
    assert re.match(r"Reagent\(reaction=\d{4}, name='x'\)", repr(x))

def test_reagent_key():
    rxn = Reaction()

    x = Reagent(rxn, 'x')
    assert x.key == 'x'
    assert 'x' in rxn
    assert 'y' not in rxn

    x.key = 'y'
    assert x.key == 'y'
    assert 'x' not in rxn
    assert 'y' in rxn

def test_reagent_name():
    rxn = Reaction()

    x = Reagent(rxn, 'x')
    assert x.key == 'x'
    assert x.name == 'x'
    assert 'x' in rxn
    assert 'y' not in rxn

    x.name = 'y'
    assert x.key == 'x'
    assert x.name == 'y'
    assert 'x' in rxn
    assert 'y' not in rxn

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

def test_reagent_volume_implicit_solvent():
    # When iterating through the reagents of a reaction, new solvent objects 
    # can get created on the fly.  This can break code that assumes the 
    # reaction will always return the exact same solvent instance.
    rxn = Reaction()
    rxn.volume = '10 µL'

    for reagent in rxn:
        assert reagent.volume == '10 µL'

def test_is_empty():
    rxn = Reaction()

    rxn['x'].volume = 0, 'µL'
    assert rxn['x'].is_empty()

    rxn['x'].volume = 0.004, 'µL'
    assert rxn['x'].is_empty()

    rxn['x'].volume = 0.005, 'µL'
    assert not rxn['x'].is_empty()

    rxn['x'].volume = 0.04, 'µL'
    assert rxn['x'].is_empty(precision=1)

    rxn['x'].volume = 0.05, 'µL'
    assert not rxn['x'].is_empty(precision=1)

    rxn['x'].volume = 1, 'µL'
    assert not rxn['x'].is_empty()

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
    x = Reagent(rxn, 'x')
    y = Reagent(rxn, 'y')

    # Set stock concentration:
    x.hold_volume.stock_conc = s2
    assert x.stock_conc == s2

    # Set concentration:
    rxn.volume = rxn_volume
    y.volume = v1

    y.hold_volume.conc = c2
    assert y.volume == v1
    assert y.stock_conc == s2
    assert y.conc == c2

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
    x = Reagent(rxn, 'x')
    y = Reagent(rxn, 'y')

    # Set volume:
    x.hold_stock_conc.volume = v2
    assert x.volume == v2

    # Set concentration:
    rxn.volume = rxn_volume
    y.stock_conc = s1
    y.hold_stock_conc.conc = c2
    assert y.volume == v2
    assert y.stock_conc == s1
    assert y.conc == c2

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


def test_solvent_repr():
    rxn = Reaction()
    rxn.solvent = 'w'
    assert re.match(r"Solvent\(reaction=\d{4}, name='w'\)", repr(rxn['w']))

def test_solvent_key():
    rxn = Reaction()
    rxn.solvent = 'w'

    rxn['x']
    w = rxn['w']
    rxn['y']

    assert w.key == 'w'

    # Set the key without changing it.  This shouldn't cause problems:
    rxn.solvent = 'w'

    # Re-key the solvent via the reaction:
    rxn.solvent = 'w2'
    assert 'w' not in rxn
    assert 'w2' in rxn
    assert rxn['w2'] is w
    assert rxn['w2'].key == 'w2'

    # Re-key the solvent via itself:
    w.key = 'w3'
    assert 'w' not in rxn
    assert 'w2' not in rxn
    assert 'w3' in rxn
    assert rxn['w3'] is w
    assert rxn['w3'].key == 'w3'

def test_solvent_name():
    rxn = Reaction()
    rxn.solvent = 'w'

    w = rxn['w']

    assert w.key == 'w'
    assert w.name == 'w'
    assert 'w' in rxn
    assert 'w2' not in rxn

    w.name = 'w2'

    assert w.key == 'w'
    assert w.name == 'w2'
    assert 'w' in rxn
    assert 'w2' not in rxn

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
            (None,   -1, 'w', ['w', 'x', 'y']),
            (  -1, None, 'w', ['w', 'y', 'x']),
            (  -1,   -1, 'w', ['w', 'x', 'y']),
            (  -1,   -2, 'w', ['w', 'y', 'x']),
            (  -2,   -1, 'w', ['w', 'x', 'y']),
            (   1,   -1, 'w', ['w', 'x', 'y']),
            (  -1,    1, 'w', ['w', 'y', 'x']),
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

@parametrize_from_file(
        schema=Schema({
            'volumes_uL': {str: Coerce(float)},
            'expected': [str],
        }),
)
def test_reaction_iter_nonzero(volumes_uL, expected):
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    del rxn['water']

    for k, v in volumes_uL.items():
        rxn[k].volume = v, 'µL'

    assert as_list(rxn.iter_nonzero_reagents()) == expected

def test_reaction_iter_non_solvent():
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    rxn.solvent = None
    assert as_list(rxn.iter_non_solvent_reagents()) == []

    rxn.solvent = 'w'
    assert as_list(rxn.iter_non_solvent_reagents()) == []

    rxn['x']
    assert as_list(rxn.iter_non_solvent_reagents()) == ['x']

def test_reaction_iter_by_flag():
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    rxn.solvent = None
    assert as_list(rxn.iter_reagents_by_flag('a')) == []

    rxn.solvent = 'w'
    assert as_list(rxn.iter_reagents_by_flag('a')) == []
    rxn['w'].flags.add('a')
    assert as_list(rxn.iter_reagents_by_flag('a')) == ['w']
    rxn['w'].flags.remove('a')
    assert as_list(rxn.iter_reagents_by_flag('a')) == []

    rxn['x']
    assert as_list(rxn.iter_reagents_by_flag('a')) == []
    rxn['x'].flags.add('a')
    assert as_list(rxn.iter_reagents_by_flag('a')) == ['x']
    rxn['x'].flags.remove('a')
    assert as_list(rxn.iter_reagents_by_flag('a')) == []

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

def test_reaction_copy_reagent():
    rxn = Reaction()
    rxn['x'].name = 'X'
    rxn['x'].volume = 1, 'µL'
    rxn['x'].stock_conc = 2, 'ng/µL'
    rxn['x'].master_mix = 3
    rxn['x'].flags = {4}
    rxn['x'].catalog_num = 5

    rxn.copy_reagent('x', 'y')

    # Make sure all attributes were copied:
    assert len(rxn) == 3
    assert rxn['y'].name == 'X'
    assert rxn['y'].stock_conc == (2, 'ng/µL')
    assert rxn['y'].master_mix == 3
    assert rxn['y'].flags == {4}
    assert rxn['y'].catalog_num == 5

    # Make sure attributes were deep/shallow copied, as appropriate:

    rxn['x'].flags.add(6)
    rxn['y'].flags.add(7)

    assert rxn['y'].reaction is rxn['x'].reaction
    assert rxn['x'].flags == {4, 6}
    assert rxn['y'].flags == {4, 7}

def test_reaction_copy_reagent_err_solvent():
    rxn = Reaction()
    rxn.solvent = 'w'

    with pytest.raises(UsageError, match="can't copy the solvent"):
        rxn.copy_reagent('w', 'x')

def test_reaction_copy_reagent_err_existing():
    rxn = Reaction()
    rxn['x'].name = 'X'
    rxn['y'].name = 'Y'

    with pytest.raises(UsageError, match="can't overwrite existing reagent"):
        rxn.copy_reagent('x', 'y')

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

def test_reaction_volume_no_solvent():
    rxn = Reaction()
    del rxn.solvent
    assert rxn.volume == 0

    rxn['x'].volume = '2 µL'
    assert rxn.volume == '2 µL'

    rxn['y'].volume = '1 µL'
    assert rxn.volume == '3 µL'

    with pytest.raises(ValueError, match="no solvent specified"):
        rxn.volume = '4 µL'

def test_reaction_free_volume():
    rxn = Reaction()
    rxn.solvent = 'w'
    rxn.volume = '4 µL'
    assert rxn.free_volume == '4 µL'

    rxn['x'].volume = '1 µL'
    assert rxn.free_volume == '3 µL'
    assert rxn.get_free_volume_excluding('x') == '4 µL'

    rxn['y'].volume = '2 µL'
    assert rxn.free_volume == '1 µL'
    assert rxn.get_free_volume_excluding('x') == '2 µL'
    assert rxn.get_free_volume_excluding('y') == '3 µL'
    assert rxn.get_free_volume_excluding('x', 'y') == '4 µL'

    rxn['z'].volume = '1 µL'
    assert rxn.free_volume == '0 µL'

def test_reaction_solvent():
    rxn = Reaction()
    rxn.solvent = 'w'
    assert rxn['w'].master_mix == True
    assert rxn['w'].order == None

    rxn['w'].master_mix = False
    rxn['w'].order = 1
    assert rxn['w'].master_mix == False
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

def test_reaction_hold_ratios_no_solvent():
    rxn = Reaction()
    del rxn.solvent
    rxn['x'].volume = '1 µL'
    rxn['y'].volume = '2 µL'

    assert rxn.volume == '3 µL'

    with pytest.raises(ValueError, match="no solvent"):
        rxn.volume = '6 µL'

    rxn.hold_ratios.volume = '6 µL'
    assert rxn.volume == '6 µL'
    assert rxn['x'].volume == '2 µL'
    assert rxn['y'].volume == '4 µL'

@parametrize_from_file(
        schema=Schema({
            'cols': {str: [str]},
            **with_stepwise.error_or({
                'volume': str,
                'expected': with_python.eval,
            })
        }),
)
def test_reaction_from_cols(cols, volume, expected, error):
    with error:
        rxn = Reaction.from_cols(cols)

        assert len(rxn) == len(expected)
        assert rxn.volume == volume

        for name, attrs in expected.items():
            for attr, value in attrs.items():
                assert getattr(rxn[name], attr) == value

@pytest.mark.parametrize(
        'text,volume,reagents', [(

        # Basic table:
            "Reagent  Stock   Volume  MM?\n"
            "=======  =====  =======  ===\n"
            "w               to 8 µL  yes\n"
            "x           2x     3 µL   no\n"
            ,
            *wx
        ), (

        # Column order:
            "MM?   Volume  Stock  Reagent\n"
            "===  =======  =====  =======\n"
            "yes  to 8 µL         w      \n"
            " no     3 µL     2x  x      \n"
            ,
            *wx
        ), (

        # Empty cell:
            "Reagent  Stock   Volume  MM?\n"
            "=======  =====  =======  ===\n"
            "w               to 8 µL  yes\n"
            "x           2x     3 µL\n"
            ,
            *wx
        )]
)
def test_reaction_from_text(text, volume, reagents):
    rxn = Reaction.from_text(text)

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
            "Reagent  Stock   Volume  MM?\n"
            "~~~~~~~  ~~~~~  ~~~~~~~  ~~~\n"
            "w               to 8 µL  yes\n"
            "x           2x     3 µL   no\n"
            ,
            "not '~~~",
        )]
)
def test_reaction_from_text_raises(text, err):
    with pytest.raises(UsageError, match=err):
        Reaction.from_text(text)

def test_reaction_from_text_flags():
    rxn = Reaction.from_text("""\
            Reagent  Stock   Volume  MM?  Flags
            =======  =====  =======  ===  =====
            w               to 8 µL  yes  a
            x           2x     3 µL   no  a,b
    """)

    assert rxn['w'].flags == {'a'}
    assert rxn['x'].flags == {'a', 'b'}

def test_reaction_from_text_catalog_num():
    rxn = Reaction.from_text("""\
            Reagent  Stock   Volume  MM?  Cat
            =======  =====  =======  ===  ===
            w               to 8 µL  yes
            x           2x     3 µL   no  101
    """)

    assert rxn['w'].catalog_num == ''
    assert rxn['x'].catalog_num == '101'

@parametrize('solvent', ['water', 'acceptor', 'donor'])
@parametrize_from_file(schema=Schema({str: Coerce(int)}))
def test_fix_volumes(solvent, donor_before, acceptor_before, donor_after, acceptor_after):
    rxn = Reaction()
    rxn.solvent = solvent
    rxn.add_reagent('donor')
    rxn.add_reagent('acceptor')

    if solvent != 'donor':
        rxn['donor'].volume = donor_before, 'µL'
    if solvent != 'acceptor':
        rxn['acceptor'].volume = acceptor_before, 'µL'
    if solvent != 'water':
        rxn.volume = donor_before + acceptor_before, 'µL'

    rxn.fix_volumes('donor', 'acceptor')

    assert rxn['donor'].volume == (donor_after, 'µL')
    assert rxn['acceptor'].volume == (acceptor_after, 'µL')

def test_fix_volumes_err():
    # donor doesn't exist
    # acceptor doesn't exist
    pass


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

def test_master_mix_pickle():
    from pickle import loads, dumps

    # Just checking that this doesn't raise.
    loads(dumps(MasterMix()))

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
            dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                                                              expected=11,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.0,                                 expected=10,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.3,                                 expected=13,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                percent=0,                                    expected=10,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                percent=30,                                   expected=13,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                               reactions=0,                   expected=11,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                               reactions=2,                   expected=12,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                                             min_vol='0 µL',  expected=11,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                                             min_vol='30 µL', expected=15,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.0,  reactions=0,  min_vol='0 µL',  expected=10,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.3,  reactions=0,  min_vol='0 µL',  expected=13,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.0,  reactions=2,  min_vol='0 µL',  expected=12,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.3,  reactions=2,  min_vol='0 µL',  expected=13,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.0,  reactions=0,  min_vol='30 µL', expected=15,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.3,  reactions=0,  min_vol='30 µL', expected=15,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.0,  reactions=2,  min_vol='30 µL', expected=15,
            ), dict(
                n=10, vol_x='2 µL', vol_rxn='10 µL',
                fraction=0.3,  reactions=2,  min_vol='30 µL', expected=15,
            ), 
        ]
)
def test_master_mix_scale(params):
    mm = MasterMix()
    mm.num_reactions = params['n']
    mm.solvent = 'w'
    mm.volume = params['vol_rxn']
    mm['x'].volume = params['vol_x']
    mm['w'].master_mix = True
    mm['x'].master_mix = True

    if 'fraction' in params:
        mm.extra_fraction = params['fraction']
        assert mm.extra_percent == pytest.approx(params['fraction'] * 100)
    if 'percent' in params:
        mm.extra_percent = params['percent']
        assert mm.extra_fraction == pytest.approx(params['percent'] / 100)
    if 'reactions' in params:
        mm.extra_reactions = params['reactions']
    if 'min_vol' in params:
        mm.extra_min_volume = params['min_vol']

    assert mm.get_scale() == pytest.approx(params['expected'])

@parametrize_from_file
@pytest.mark.parametrize(
        'format', [
            pytest.param(lambda mm: str(mm), id='str()'),
            pytest.param(lambda mm: mm.format_text(), id='format_text()'),
            pytest.param(lambda mm: mm.format_text(1), id='format_text(1)'),
        ],
)
def test_master_mix_format_text(master_mix, format, expected):
    master_mix = with_stepwise.exec(master_mix)['mm']
    assert format(master_mix) == expected

def test_master_mix_replace_text():
    mm = MasterMix.from_text("""\
Reagent    Stock    Volume  MM?
=========  =====  ========  ===
water             to 10 µL  yes
long name    10x      1 µL  yes
""")

    assert str(mm) == """\
Reagent    Stock    Volume
──────────────────────────
water              9.00 µL
long name    10x   1.00 µL
──────────────────────────
                  10.00 µL"""

    mm.replace_text('long ', '')

    assert str(mm) == """\
Reagent  Stock    Volume
────────────────────────
water            9.00 µL
name       10x   1.00 µL
────────────────────────
                10.00 µL"""

    mm.replace_text('name', 'extra long name')

    assert str(mm) == """\
Reagent          Stock    Volume
────────────────────────────────
water                    9.00 µL
extra long name    10x   1.00 µL
────────────────────────────────
                        10.00 µL"""

