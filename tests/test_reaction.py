#!/usr/bin/env python3

import pytest
from stepwise import *
from param_helpers import *
from reprfunc import ReprBuilder, repr_from_init

# Test that when a reagent is removed from a reaction, it doesn't affect that 
# reaction anymore.

wx = '8 µL', {
        'w': ('5 µL',  ..., True),
        'x': ('3 µL', '2x', False),
}

class ReactionWrapper:

    def __init__(self, **attrs):
        self.attrs = attrs

    def __eq__(self, actual):
        for attr, expected in self.attrs.items():
            if attr == 'reagents':
                self._compare_reagents(actual, expected)
            else:
                assert getattr(actual, attr) == expected

        return True

    def _compare_reagents(self, actual, expected):
        assert len(actual) == len(expected)
        for reagent, attrs in zip(actual, expected):
            for attr, value in attrs.items():
                if attr == 'class':
                    assert isinstance(reagent, value)
                elif attr == 'key':
                    assert getattr(reagent, attr) == value
                    assert actual[value] is reagent
                else:
                    assert getattr(reagent, attr) == value

    __repr__ = repr_from_init

def eval_reaction(x):
    if isinstance(x, str):
        if x.lstrip().startswith('#!/usr/bin/env python'):
            return with_sw.exec(x, get='rxn')
        else:
            return Reaction.from_text(x)

    if isinstance(x, list):
        return Reaction.from_rows(x)
    if isinstance(x, dict):
        return Reaction.from_cols(x)

    raise TypeError(f"expected str, list, or dict, not: {type(x)}")

def eval_reaction_wrapper(x):
    return ReactionWrapper(**with_sw.eval(x))


def test_reagent_key():
    rxn = Reaction()
    x = rxn['x']

    assert x.key == 'x'
    assert 'x' in rxn
    assert 'y' not in rxn

    x.key = 'y'
    assert x.key == 'y'
    assert 'x' not in rxn
    assert 'y' in rxn

def test_reagent_name():
    rxn = Reaction()

    x = rxn['x']
    assert x.key == 'x'
    assert x.name == 'x'
    assert 'x' in rxn
    assert 'y' not in rxn

    x.name = 'y'
    assert x.key == 'x'
    assert x.name == 'y'
    assert 'x' in rxn
    assert 'y' not in rxn

@parametrize_from_file
def test_reagent_volume(given, expected):
    rxn = Reaction()
    x = rxn['x']
    assert x.volume == None

    x.volume = with_sw.eval(given)
    assert x.volume == Q(expected)

@parametrize_from_file(
        schema=[
            cast(volume_uL=float, kwargs=with_py.eval, expected=with_py.eval),
            defaults(kwargs={}),
        ],
)
def test_reagent_is_empty(volume_uL, kwargs, expected):
    rxn = Reaction()
    rxn['x'].volume = volume_uL, 'µL'
    assert rxn['x'].is_empty(**kwargs) == expected

@parametrize_from_file
def test_reagent_stock_conc(given, expected):
    rxn = Reaction()
    x = rxn['x']
    assert x.stock_conc == None

    x.stock_conc = with_sw.eval(given)
    assert x.stock_conc == Q(expected)

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reagent_conc(volume, stock_conc, rxn_volume, expected, error):
    rxn = Reaction()
    rxn['w'].set_as_solvent()
    x = rxn['x']

    if rxn_volume:  rxn.volume = rxn_volume
    if volume:      x.volume = volume
    if stock_conc:  x.stock_conc = stock_conc

    with error:
        assert x.conc == Q(expected)

    if error:
        assert x.conc_or_none is None
    else:
        assert x.conc_or_none == Q(expected)

@parametrize_from_file
def test_reagent_hold_conc(v1, s1, v2, s2):
    rxn = Reaction()
    x = rxn['x']

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
    x = rxn['x']
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

@parametrize_from_file
def test_reagent_hold_volume(rxn_volume, v1, s1, c1, s2, c2):
    rxn = Reaction()
    x = rxn['x']
    y = rxn['y']

    # Set stock concentration:
    x.hold_volume.stock_conc = s2
    assert x.stock_conc == s2

    # Set concentration:
    rxn['w'].volume = To(rxn_volume)
    y.volume = v1

    y.hold_volume.conc = c2
    assert y.volume == v1
    assert y.stock_conc == s2
    assert y.conc == c2

def test_reagent_hold_volume_in_place():
    rxn = Reaction()
    rxn['w'].volume = 'to 10 µL'

    x = rxn['x']
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

@parametrize_from_file
def test_reagent_hold_stock_conc(rxn_volume, s1, v1, c1, v2, c2):
    rxn = Reaction()
    x = rxn['x']
    y = rxn['y']

    # Set volume:
    x.hold_stock_conc.volume = v2
    assert x.volume == v2

    # Set concentration:
    rxn['w'].volume = To(rxn_volume)
    y.stock_conc = s1
    y.hold_stock_conc.conc = c2
    assert y.volume == v2
    assert y.stock_conc == s1
    assert y.conc == c2

def test_reagent_hold_stock_conc_in_place():
    rxn = Reaction()
    rxn['w'].volume = 'to 10 µL'

    x = rxn['x']
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


def test_solvent_key():
    rxn = Reaction()
    rxn['w'].set_as_solvent()
    rxn['x']
    rxn['y']

    w = rxn['w']
    assert w.key == 'w'

    w.key = 'w2'
    assert 'w' not in rxn
    assert 'w2' in rxn
    assert rxn['w2'] is w
    assert rxn['w2'].key == 'w2'

def test_solvent_name():
    rxn = Reaction()
    rxn['w'].set_as_solvent()

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
    rxn['w'].volume = 'to 10 µL'
    assert rxn.volume == '10 µL'
    assert rxn['w'].volume == '10 µL'

    rxn['x'].volume = '1 µL'
    assert rxn.volume == '10 µL'
    assert rxn['w'].volume == '9 µL'

    rxn['x'].volume = '2 µL'
    assert rxn.volume == '10 µL'
    assert rxn['w'].volume == '8 µL'

    rxn['y'].volume = '1 µL'
    assert rxn.volume == '10 µL'
    assert rxn['w'].volume == '7 µL'

    rxn['x'].volume = None
    with pytest.raises(ValueError):
        rxn['w'].volume

def test_solvent_stock_conc():
    rxn = Reaction()
    rxn['w'].set_as_solvent()

    assert rxn['w'].stock_conc is None

def test_solvent_conc():
    rxn = Reaction()
    rxn['w'].set_as_solvent()

    with pytest.raises(NotImplementedError):
        rxn['w'].conc

    assert rxn['w'].conc_or_none is None


@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reaction_setup(reaction, expected, error):
    if error:
        with error:
            with_sw.exec(reaction)

    else:
        if isinstance(expected, list):
            expected = [eval_reaction_wrapper(x) for x in expected]
            actual = list(with_sw.exec(reaction, get='rxns'))
        else:
            expected = eval_reaction_wrapper(expected)
            actual = with_sw.exec(reaction, get='rxn')

        assert actual == expected

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reaction_from_cols(cols, expected, error):
    cols = with_sw.eval(cols)
    expected = eval_reaction_wrapper(expected)
    with error:
        assert Reaction.from_cols(cols) == expected

@parametrize_from_file
def test_reaction_from_rows(rows, expected):
    rows = with_py.eval(rows)
    expected = eval_reaction_wrapper(expected)
    assert Reaction.from_rows(rows) == expected

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reaction_from_text(text, expected, error):
    expected = eval_reaction_wrapper(expected)
    with error:
        assert Reaction.from_text(text) == expected

@parametrize_from_file
def test_reaction_repr(reaction, expected):
    rxn = eval_reaction(reaction)
    assert repr(rxn) == expected

@parametrize_from_file
def test_reaction_eq(a, b, expected):
    a = with_sw.exec(a, get='rxn')
    b = with_sw.exec(b, get='rxn')
    expected = with_py.eval(expected)

    assert (a == b) == expected

def test_reaction_iter():
    as_list = lambda rxn: [x.key for x in rxn]

    # The `__iter__()` method is used by `ReactionWrapper`, and is therefore 
    # tested extensively in other tests.  Here we include just a few simple 
    # tests for good measure.

    rxn = Reaction()
    assert as_list(rxn) == list(rxn.keys()) == []

    rxn['w'].set_as_solvent()
    assert as_list(rxn) == list(rxn.keys()) == ['w']

    rxn['x']
    assert as_list(rxn) == list(rxn.keys()) == ['w', 'x']

@parametrize_from_file
def test_reaction_iter_nonzero(volumes_uL, expected):
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    for k, v in volumes_uL.items():
        rxn[k].volume = float(v), 'µL'

    assert as_list(rxn.iter_nonzero_reagents()) == expected

def test_reaction_iter_nonsolvent():
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    assert as_list(rxn.iter_nonsolvent_reagents()) == []

    rxn['w'].set_as_solvent()
    assert as_list(rxn.iter_nonsolvent_reagents()) == []

    rxn['x']
    assert as_list(rxn.iter_nonsolvent_reagents()) == ['x']

def test_reaction_iter_by_flag():
    as_list = lambda rxn: [x.name for x in rxn]

    rxn = Reaction()
    assert as_list(rxn.iter_reagents_by_flag('a')) == []

    rxn['w'].set_as_solvent()
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

    assert len(rxn) == 0
    assert 'x' not in rxn
    assert 'w' not in rxn

    rxn['x']
    assert len(rxn) == 1
    assert 'x' in rxn
    assert 'w' not in rxn

    rxn['x']
    assert len(rxn) == 1
    assert 'x' in rxn
    assert 'w' not in rxn

    rxn['w'].set_as_solvent()
    assert len(rxn) == 2
    assert 'x' in rxn
    assert 'w' in rxn

    rxn['w']
    assert len(rxn) == 2
    assert 'x' in rxn
    assert 'w' in rxn

@parametrize_from_file(
        schema=with_sw.error_or('expected_uL'),
)
def test_reaction_volume(reaction, expected_uL, error):
    expected = Quantity(float(expected_uL), 'µL')
    with error:
        rxn = with_sw.exec(reaction, get='rxn')
        assert rxn.volume == expected

def test_reaction_free_volume():
    rxn = Reaction()
    rxn['w'].volume = 'to 4 µL'
    assert rxn.free_volume == Q('4 µL')

    rxn['x'].volume = '1 µL'
    assert rxn.free_volume == Q('3 µL')
    assert rxn.get_free_volume_excluding('x') == Q('4 µL')

    rxn['y'].volume = '2 µL'
    assert rxn.free_volume == Q('1 µL')
    assert rxn.get_free_volume_excluding('x') == Q('2 µL')
    assert rxn.get_free_volume_excluding('y') == Q('3 µL')
    assert rxn.get_free_volume_excluding('x', 'y') == Q('4 µL')

    rxn['z'].volume = '1 µL'
    assert rxn.free_volume == Q('0 µL')

@parametrize('solvent', ['water', 'acceptor', 'donor'])
@parametrize_from_file(schema=Schema({str: Coerce(int)}))
def test_reaction_repair_volumes(solvent, donor_before, acceptor_before, donor_after, acceptor_after):
    rxn = Reaction()
    rxn.append_reagent('donor')
    rxn.append_reagent('acceptor')
    rxn[solvent].set_as_solvent()

    if solvent != 'donor':
        rxn['donor'].volume = donor_before, 'µL'
    if solvent != 'acceptor':
        rxn['acceptor'].volume = acceptor_before, 'µL'
    if solvent != 'water':
        rxn.volume = donor_before + acceptor_before, 'µL'

    rxn.repair_volumes('donor', 'acceptor')

    assert rxn['donor'].volume == (donor_after, 'µL')
    assert rxn['acceptor'].volume == (acceptor_after, 'µL')

@pytest.mark.parametrize(
        'v1,r1,v2,r2', [
            ('5 µL', {}, '10 µL', {}),
            ('5 µL', {'x': '1 µL'}, '10 µL', {'x': '2 µL'}),
        ]
)
def test_reaction_hold_ratios(v1, r1, v2, r2):
    rxn = Reaction()
    rxn['w'].volume = To(v1)
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
    rxn['w'].volume = 'to 10 µL'
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
    rxn['x'].volume = '1 µL'
    rxn['y'].volume = '2 µL'

    assert rxn.volume == '3 µL'
    with pytest.raises(ValueError, match="no solvent"):
        rxn.volume = '6 µL'

    rxn.hold_ratios.volume = '6 µL'

    assert rxn.volume == '6 µL'
    assert rxn['x'].volume == '2 µL'
    assert rxn['y'].volume == '4 µL'

def test_reaction_hold_solvent_volume():
    rxn = Reaction()
    rxn['w'].volume = 'to 4 µL'

    assert rxn.volume == '4 µL'
    assert rxn['w'].volume == '4 µL'
    assert rxn['w'].is_held == False

    rxn['x'].volume = '1 µL'

    assert rxn.volume == '4 µL'
    assert rxn['w'].volume == '3 µL'
    assert rxn['w'].is_held == False

    with rxn.hold_solvent_volume():
        assert rxn.volume == '4 µL'
        assert rxn['w'].volume == '3 µL'
        assert rxn['w'].is_held == True

        rxn['x'].volume = '2 µL'

        assert rxn.volume == '5 µL'
        assert rxn['w'].volume == '3 µL'
        assert rxn['w'].is_held == True

        # Make sure the context manager is re-entrant:
        with rxn.hold_solvent_volume():
            assert rxn['w'].is_held == True
        assert rxn['w'].is_held == True

    assert rxn.volume == '5 µL'
    assert rxn['w'].volume == '3 µL'
    assert rxn['w'].is_held == False

    rxn['x'].volume = '1 µL'

    assert rxn.volume == '5 µL'
    assert rxn['w'].volume == '4 µL'
    assert rxn['w'].is_held == False

def test_reaction_hold_solvent_volume_del_solvent():
    rxn = Reaction()
    rxn['w'].volume = 'to 4 µL'
    rxn['x'].volume = '1 µL'
    rxn['y'].volume = '2 µL'

    with rxn.hold_solvent_volume():
        del rxn['w']

    assert rxn.volume == '3 µL'
    assert rxn['x'].volume == '1 µL'
    assert rxn['y'].volume == '2 µL'


@parametrize_from_file(
        schema=[
            cast(kwargs=with_py.eval), 
            defaults(kwargs={}),
        ],
)
def test_format_reaction(reaction, kwargs, expected):
    rxn = eval_reaction(reaction)
    table = format_reaction(rxn, **kwargs)
    assert table.format_text(inf) == expected


def test_master_mix_getattr():
    mm = MasterMix()
    mm['w'].volume = 'to 1 µL'

    assert mm.volume == '1 µL'
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
    mm['w'].set_as_solvent()
    mm.volume = '1 µL'

    assert mm.reaction.volume == '1 µL'
    assert mm.reaction.solvent == 'w'

def test_master_mix_pickle():
    from pickle import loads, dumps

    # Just checking that this doesn't raise.
    loads(dumps(MasterMix()))

def test_master_mix_dunder():
    # Just quickly call all the dunders to make sure they're doing something.  
    # The `test_reaction_...()` tests make sure these methods actually work.
    mm = MasterMix()
    mm['w'].set_as_solvent()

    # `__repr__()`
    assert repr(mm) == "MasterMix(Solvent('w'))"

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
    mm['w'].volume = To(params['vol_rxn'])
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
    master_mix = with_sw.exec(master_mix)['mm']
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


