#!/usr/bin/env python3

import pytest
from stepwise import Quantity, Q
from math import *
from operator import *

@pytest.mark.parametrize(
        'value,unit,err', [
            (None, 'ng', TypeError),
            ('', 'ng', ValueError),
            (1, None, TypeError),
            (1, '', ValueError),
            (1, Quantity(1, 'ng'), TypeError),
])
def test_init_err(value, unit, err):
    with pytest.raises(err):
        Quantity(value, unit)

@pytest.mark.parametrize(
        'given,expected', [
            (Quantity(1, 'ng'), "Quantity(1, 'ng')"),
            (Quantity(1, '%'),  "Quantity(1, '%')"),
])
def test_repr(given, expected):
    assert repr(given) == expected

@pytest.mark.parametrize(
        'given,expected', [
            (Quantity(1, 'ng'), '1 ng'),
            (Quantity(1, '%'),    '1%'),
])
def test_str(given, expected):
    assert str(given) == expected

def test_format():
    q = Q('1 ng')
    assert f'{q}' == '1 ng'
    assert f'{q:g}' == '1 ng'
    assert f'{q:.2f}' == '1.00 ng'

def test_value():
    q = Quantity(1, 'ng')
    assert q.value == 1

    # Quantities are immutable.
    with pytest.raises(AttributeError):
        q.value = 2

def test_unit():
    q = Quantity(1, 'ng')
    assert q.unit == 'ng'

    # Normalize unicode micro signs.
    q = Quantity(1, '\u03bcL')  # GREEK SMALL LETTER MU
    assert q.unit == '\u00b5L'  # MICRO SIGN

    # Quantities are immutable.
    with pytest.raises(AttributeError):
        q.unit = 'µL'

def test_convert_unit():
    f = {
            'g': 1,
            'mg': 1e3,
    }

    assert Q('1 g').convert_unit('mg', f) == Q('1000 mg')
    assert Q('2000 mg').convert_unit('g', f) == Q('2 g')

def test_convert_unit_err():
    f = {
            'g': 1,
            'mg': 1e3,
    }

    with pytest.raises(ValueError, match="cannot convert between 'g' and 'mL', did you mean: 'mg'"):
        Q('1 g').convert_unit('mL', f)

def test_require_matching_unit():
    q1 = Quantity(1, 'ng')
    q2 = Quantity(2, 'ng')
    q3 = Quantity(1, 'µL')

    q1.require_matching_unit(q2)
    with pytest.raises(ValueError):
        q1.require_matching_unit(q3)

@pytest.mark.parametrize(
        'given,expected', [
            # Values
            (   '1 ng', Quantity(1, 'ng')),
            (  '-1 ng', Quantity(-1, 'ng')),
            (  '+1 ng', Quantity(1, 'ng')),
            ( '1.0 ng', Quantity(1, 'ng')),
            ('-1.0 ng', Quantity(-1, 'ng')),
            ('+1.0 ng', Quantity(1, 'ng')),
            (  '.1 ng', Quantity(0.1, 'ng')),
            ( '-.1 ng', Quantity(-0.1, 'ng')),
            ( '+.1 ng', Quantity(0.1, 'ng')),

            # Units
            (   '1 ng', Quantity(1, 'ng')),
            (   '1 µL', Quantity(1, 'µL')),
            (     '1%', Quantity(1, '%')),

            # Misc
            ( ' 1 ng ', Quantity(1, 'ng')),
])
def test_from_string(given, expected):
    assert Quantity.from_string(given) == expected

@pytest.mark.parametrize(
        'given', [
            '1',
            '10',
            'ng',
            '1 ng µL',
])
def test_from_string_err(given):
    with pytest.raises(ValueError, match=given):
        Quantity.from_string(given)

@pytest.mark.parametrize(
        'value,default_unit,expected', [
            (   '1 nM', 'ng/µL', Quantity(1, 'nM')),
            ('1 ng/µL', 'ng/µL', Quantity(1, 'ng/µL')),
            (      '1', 'ng/µL', Quantity(1, 'ng/µL')),
            (    '1.0', 'ng/µL', Quantity(1, 'ng/µL')),
            (       1 , 'ng/µL', Quantity(1, 'ng/µL')),
            (     1.0 , 'ng/µL', Quantity(1, 'ng/µL')),
])
def test_from_string_or_float(value, default_unit, expected):
    assert Quantity.from_string_or_float(value, default_unit) == expected

@pytest.mark.parametrize(
        'given,expected', [
            ((1, 'ng'), Quantity(1, 'ng')),
            ((1, 'µL'), Quantity(1, 'µL')),
            ((1, '%'),  Quantity(1, '%')),
            (('1', 'ng'), Quantity(1, 'ng')),
])
def test_from_tuple(given, expected):
    assert Quantity.from_tuple(given) == expected

@pytest.mark.parametrize(
        'given', [
            (),
            (1,),
            ('ng'),
            (1, 'ng', None),
])
def test_from_tuple_err(given):
    with pytest.raises(ValueError, match=str(given)):
        Quantity.from_tuple(given)

@pytest.mark.parametrize(
        'given,expected', [
            (None,              None             ),
            (Quantity(1, 'ng'), Quantity(1, 'ng')),
            ('1 ng',            Quantity(1, 'ng')),
            ((1, 'ng'),         Quantity(1, 'ng')),
])
def test_from_anything(given, expected):
    assert Quantity.from_anything(given) == expected

@pytest.mark.parametrize(
        'given,err', [
            (1, "cannot convert 1"),
])
def test_from_anything_err(given, err):
    with pytest.raises(ValueError, match=err):
        Quantity.from_anything(given)

@pytest.mark.parametrize(
        'op,given,expected', [
            (bool,   Q('0 ng'),     False),
            (bool,   Q('1 ng'),     True),

            (float,  Q('1 ng'),     1.0),

            (pos,    Q('1 ng'),     Q('1 ng')),
            (pos,    Q('-1 ng'),    Q('-1 ng')),

            (neg,    Q('1 ng'),     Q('-1 ng')),
            (neg,    Q('-1 ng'),    Q('1 ng')),

            (abs,    Q('1 ng'),     Q('1 ng')),
            (abs,    Q('0 ng'),     Q('0 ng')),
            (abs,    Q('-1 ng'),    Q('1 ng')),

            (ceil,   Q('1.5 ng'),   Q('2.0 ng')),
            (ceil,   Q('-1.5 ng'),  Q('-1.0 ng')),

            (floor,  Q('1.5 ng'),   Q('1.0 ng')),
            (floor,  Q('-1.5 ng'),  Q('-2.0 ng')),

            (trunc,  Q('1.5 ng'),   Q('1 ng')),
            (trunc,  Q('-1.5 ng'),  Q('-1 ng')),

            (round,  Q('1.6 ng'),   Q('2.0 ng')),
            (round,  Q('1.4 ng'),   Q('1.0 ng')),
    ],
)
def test_unary_operators(op, given, expected):
    assert op(given) == expected

@pytest.mark.parametrize(
        'op,left,right,expected', [
            (eq,        Q('1 ng'),  Q('1 ng'),       True),
            (eq,        Q('1 ng'),  Q('2 ng'),      False),
            (eq,        Q('1 ng'),    '1 ng' ,       True),
            (eq,        Q('1 ng'),    '2 ng' ,      False),
            (eq,        Q('0 ng'),     0     ,       True),
            (eq,        Q('1 ng'),     0     ,      False),

            (ne,        Q('1 ng'),  Q('1 ng'),      False),
            (ne,        Q('1 ng'),  Q('2 ng'),       True),
            (ne,        Q('1 ng'),    '1 ng' ,      False),
            (ne,        Q('1 ng'),    '2 ng' ,       True),
            (ne,        Q('0 ng'),     0     ,      False),
            (ne,        Q('1 ng'),     0     ,       True),

            # For incompatible types, `__eq__()` and `__ne__()` fallback to an 
            # identity comparison (instead of raising `TypeError`), see:
            # https://stackoverflow.com/questions/40780004/returning-notimplemented-from-eq
            (eq,        Q('1 ng'),  Q('2 µL'),      False),
            (ne,        Q('1 ng'),  Q('2 µL'),       True),
            (eq,        Q('1 ng'),       None,      False),
            (ne,        Q('1 ng'),       None,       True),

            (lt,        Q('2 ng'),  Q('1 ng'),      False),
            (lt,        Q('2 ng'),  Q('2 ng'),      False),
            (lt,        Q('2 ng'),  Q('3 ng'),       True),
            (lt,        Q('2 ng'),    '1 ng' ,      False),
            (lt,        Q('2 ng'),    '2 ng' ,      False),
            (lt,        Q('2 ng'),    '3 ng' ,       True),
            (lt,        Q('1 ng'),     0     ,      False),
            (lt,        Q('0 ng'),     0     ,      False),
            (lt,       Q('-1 ng'),     0     ,       True),

            (le,        Q('2 ng'),  Q('1 ng'),      False),
            (le,        Q('2 ng'),  Q('2 ng'),       True),
            (le,        Q('2 ng'),  Q('3 ng'),       True),
            (le,        Q('2 ng'),    '1 ng' ,      False),
            (le,        Q('2 ng'),    '2 ng' ,       True),
            (le,        Q('2 ng'),    '3 ng' ,       True),
            (le,        Q('1 ng'),     0     ,      False),
            (le,        Q('0 ng'),     0     ,       True),
            (le,       Q('-1 ng'),     0     ,       True),

            (gt,        Q('2 ng'),  Q('1 ng'),       True),
            (gt,        Q('2 ng'),  Q('2 ng'),      False),
            (gt,        Q('2 ng'),  Q('3 ng'),      False),
            (gt,        Q('2 ng'),    '1 ng' ,       True),
            (gt,        Q('2 ng'),    '2 ng' ,      False),
            (gt,        Q('2 ng'),    '3 ng' ,      False),
            (gt,        Q('1 ng'),     0     ,       True),
            (gt,        Q('0 ng'),     0     ,      False),
            (gt,       Q('-1 ng'),     0     ,      False),

            (ge,        Q('2 ng'),  Q('1 ng'),       True),
            (ge,        Q('2 ng'),  Q('2 ng'),       True),
            (ge,        Q('2 ng'),  Q('3 ng'),      False),
            (ge,        Q('2 ng'),    '1 ng' ,       True),
            (ge,        Q('2 ng'),    '2 ng' ,       True),
            (ge,        Q('2 ng'),    '3 ng' ,      False),
            (ge,        Q('1 ng'),     0     ,       True),
            (ge,        Q('0 ng'),     0     ,       True),
            (ge,       Q('-1 ng'),     0     ,      False),

            (add,       Q('1 ng'),  Q('2 ng'),  Q('3 ng')),
            (add,       Q('1 ng'),    '2 ng' ,  Q('3 ng')),
            (add,         '1 ng' ,  Q('2 ng'),  Q('3 ng')),
            (add,       Q('1 ng'),     0     ,  Q('1 ng')),
            (add,          0     ,  Q('2 ng'),  Q('2 ng')),

            (sub,       Q('3 ng'),  Q('2 ng'),  Q('1 ng')),
            (sub,       Q('3 ng'),    '2 ng' ,  Q('1 ng')),
            (sub,         '3 ng' ,  Q('2 ng'),  Q('1 ng')),
            (sub,       Q('1 ng'),     0     ,  Q('1 ng')),
            (sub,          0     ,  Q('2 ng'), Q('-2 ng')),

            (mul,       Q('2 ng'),     3     ,  Q('6 ng')),
            (mul,          2     ,  Q('3 ng'),  Q('6 ng')),

            (truediv,   Q('6 ng'),     3     ,  Q('2 ng')),
            (truediv,   Q('6 ng'),  Q('3 ng'),     2     ),
            (truediv,   Q('6 ng'),    '3 ng' ,     2     ),
            (truediv,     '6 ng' ,  Q('3 ng'),     2     ),
            (truediv,      0     ,  Q('3 ng'),     0     ),

            (floordiv,  Q('6 ng'),     4     ,  Q('1 ng')),
            (floordiv,  Q('6 ng'),  Q('4 ng'),     1     ),
            (floordiv,  Q('6 ng'),    '4 ng' ,     1     ),
            (floordiv,    '6 ng' ,  Q('4 ng'),     1     ),
            (floordiv,     0     ,  Q('4 ng'),     0     ),
])
def test_binary_operators(op, left, right, expected):
    assert op(left, right) == expected

@pytest.mark.parametrize(
        'op,left,right', [
            (lt,       Q('1 ng'), Q('2 µL')),
            (le,       Q('1 ng'), Q('2 µL')),
            (gt,       Q('1 ng'), Q('2 µL')),
            (ge,       Q('1 ng'), Q('2 µL')),

            (add,      Q('1 ng'),    2     ),
            (add,         1     , Q('2 ng')),
            (add,      Q('1 ng'), Q('2 µL')),

            (sub,      Q('3 ng'),    2     ),
            (sub,         3     , Q('2 ng')),
            (sub,      Q('3 ng'), Q('2 µL')),

            (mul,      Q('2 ng'), Q('3 ng')),
            (mul,      Q('2 ng'), Q('3 µL')),

            (pow,      Q('2 ng'),    2     ),
            (pow,         2     , Q('2 ng')),
            (pow,      Q('2 ng'), Q('2 ng')),

            (truediv,     6     , Q('3 ng')),
            (truediv,  Q('6 ng'), Q('3 µL')),

            (floordiv,    6     , Q('4 ng')),
            (truediv,  Q('6 ng'), Q('4 µL')),

            (mod,      Q('2 ng'),    2     ),
            (mod,         2     , Q('2 ng')),
            (mod,      Q('2 ng'), Q('2 ng')),
])
def test_binary_operators_err(op, left, right):
    with pytest.raises(TypeError):
        op(left, right)

def test_approx():
    # Have to specify an absolute tolerance, because the default absolute 
    # tolerance is a float, and floats can't be compared to quantities.
    assert Q('1.005 ng') == pytest.approx(Q('1 ng'), abs=Q('0.01 ng'))
    assert Q('1.05 ng')  != pytest.approx(Q('1 ng'), abs=Q('0.01 ng'))

