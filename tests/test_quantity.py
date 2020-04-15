#!/usr/bin/env python3

import pytest
from stepwise import Quantity, Q
from operator import *

@pytest.mark.parametrize(
        'value,unit,err', [
            (None, 'ng', TypeError),
            ('', 'ng', ValueError),
            (Quantity(1, 'ng'), 'ng', TypeError),
            (1, None, TypeError),
            (1, '', ValueError),
            (1, Quantity(1, 'ng'), TypeError),
])
def test_init_raises(value, unit, err):
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

def test_bool():
    assert not Quantity(0, 'ng')
    assert Quantity(1, 'ng')
    assert Quantity(1e-100, 'ng')

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
def test_from_string_raises(given):
    with pytest.raises(ValueError, match=given):
        Quantity.from_string(given)

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
def test_from_tuple_raises(given):
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
def test_from_anything_raises(given, err):
    with pytest.raises(ValueError, match=err):
        Quantity.from_anything(given)

@pytest.mark.parametrize(
        'op,left,right,expected', [
            (eq,       Q('1 ng'), Q('1 ng'),       True),
            (eq,       Q('1 ng'), Q('2 ng'),      False),
            (eq,       Q('1 ng'),   '1 ng' ,       True),
            (eq,       Q('1 ng'),   '2 ng' ,      False),
            (eq,       Q('0 ng'),    0     ,       True),
            (eq,       Q('1 ng'),    0     ,      False),

            (add,      Q('1 ng'), Q('2 ng'),  Q('3 ng')),
            (add,      Q('1 ng'),   '2 ng' ,  Q('3 ng')),
            (add,        '1 ng' , Q('2 ng'),  Q('3 ng')),
            (add,      Q('1 ng'),    0     ,  Q('1 ng')),
            (add,         0     , Q('2 ng'),  Q('2 ng')),

            (sub,      Q('3 ng'), Q('2 ng'),  Q('1 ng')),
            (sub,      Q('3 ng'),   '2 ng' ,  Q('1 ng')),
            (sub,        '3 ng' , Q('2 ng'),  Q('1 ng')),
            (sub,      Q('1 ng'),    0     ,  Q('1 ng')),
            (sub,         0     , Q('2 ng'), Q('-2 ng')),

            (mul,      Q('2 ng'),    3     ,  Q('6 ng')),
            (mul,         2     , Q('3 ng'),  Q('6 ng')),

            (truediv,  Q('6 ng'),    3     ,  Q('2 ng')),
            (truediv,  Q('6 ng'), Q('3 ng'),     2     ),
            (truediv,  Q('6 ng'),   '3 ng' ,     2     ),
            (truediv,    '6 ng' , Q('3 ng'),     2     ),
            (truediv,     0     , Q('3 ng'),     0     ),

            (floordiv, Q('6 ng'),    4     ,  Q('1 ng')),
            (floordiv, Q('6 ng'), Q('4 ng'),     1     ),
            (floordiv, Q('6 ng'),   '4 ng' ,     1     ),
            (floordiv,   '6 ng' , Q('4 ng'),     1     ),
            (floordiv,    0     , Q('4 ng'),     0     ),
])
def test_operators(op, left, right, expected):
    assert op(left, right) == expected

@pytest.mark.parametrize(
        'op,left,right,match', [
            (add,      Q('1 ng'),    2     , "cannot add '1 ng' and '2'"),
            (add,         1     , Q('2 ng'), "cannot add '1' and '2 ng'"),

            (sub,      Q('3 ng'),    2     , "cannot sub '3 ng' and '2'"),
            (sub,         3     , Q('2 ng'), "cannot sub '3' and '2 ng'"),

            (mul,      Q('2 ng'), Q('3 ng'), "cannot mul '2 ng' and '3 ng'"),

            (truediv,     6     , Q('3 ng'), "cannot truediv '6' and '3 ng'"),

            (floordiv,    6     , Q('4 ng'), "cannot floordiv '6' and '4 ng'"),
])
def test_operators_raise(op, left, right, match):
    with pytest.raises(ValueError, match=match):
        op(left, right)

