#!/usr/bin/env python3

import re
import autoprop
import math

from numbers import Number, Real
from operator import *
from collections.abc import Iterable
from inform import did_you_mean

@autoprop
class Quantity(Real):
    """
    Simple class to manage numbers with units.

    - Support basic arithmetic operations that don't change the unit.

    - For arithmetic, units must match exactly.  Metric prefixes are not 
      understood.

    - Immutable
    """
    FLOAT_REGEX = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
    UNIT_REGEX = r'[^\s\d]+'
    QUANTITY_REGEX = fr'^\s*({FLOAT_REGEX})\s*({UNIT_REGEX})\s*$'
    NO_PADDING = '%', 'x'

    @classmethod
    def from_anything(cls, q):
        if q is None:
            return None
        elif isinstance(q, Quantity):
            return q
        elif isinstance(q, str):
            return cls.from_string(q)
        elif isinstance(q, Iterable):
            return cls.from_tuple(q)
        else:
            raise ValueError(f"cannot convert {q!r} to a quantity")

    @classmethod
    def from_string(cls, string):
        if m := re.match(cls.QUANTITY_REGEX, string):
            return cls(float(m.group(1)), m.group(2))
        else:
            raise ValueError(f"{string!r} cannot be interpreted as a value with a unit.")

    @classmethod
    def from_string_or_float(cls, value, default_unit):
        try:
            return cls.from_string(value)
        except (ValueError, TypeError):
            return cls(float(value), default_unit)

    @classmethod
    def from_tuple(cls, tuple):
        if len(tuple) != 2:
            raise ValueError(f"{tuple!r} has {len(tuple)} values, expected 2.")
        return cls(*tuple)


    def __init__(self, value, unit):
        if not isinstance(value, Real):
            value = float(value)

        self._value = value
        self._unit = unit

        if not re.fullmatch(self.UNIT_REGEX, unit):
            raise ValueError(f"not a valid unit: {unit!r}")

        # There are two unicode "micro" characters (one is meant to be the 
        # micro prefix, while the other is meant to be the Greek mu).  Replace 
        # the "mu" with the "micro" to avoid confusion.
        self._unit = unit.replace('\u03bc', 'µ')

    def __repr__(self):
        return f'Quantity({self.value!r}, {self.unit!r})'

    def __str__(self):
        return self.format()

    def __format__(self, spec):
        return self.format(spec)

    def __bool__(self):
        return bool(self.value)

    def __float__(self):
        return self.value

    def get_value(self):
        return self._value

    def get_unit(self):
        return self._unit

    def get_tuple(self):
        return self._value, self._unit

    def format(self, spec=''):
        if not spec and isinstance(self.value, float):
            spec = 'g'
        padding = '' if self.unit in self.NO_PADDING else ' '
        return f'{self.value:{spec}}{padding}{self.unit}'

    def convert_unit(self, new_unit, conversion_factors):
        """
        Arguments:
            new_unit: str
                The unit to convert to.  This unit must be present in the 
                *conversion_factors* argument, or a `ValueError` will be 
                raised.
            conversion_factors: Dict[str,float]
                The keys are the units that can be converted to.  The values 
                are the multipliers needed to make each of these units equal to 
                all of the others. For example, ``dict(g=1, mg=1000)`` 
                indicates that 1000mg equals 1g.

        Returns:
            Quantity:
                A new quantity instance representing the same physical quantity 
                in the given units.

        Examples:

        >>> from stepwise import Quantity
        >>> q = Quantity(2, 'g')
        >>> q.convert_unit('mg', dict(g=1, mg=1000))
        Quantity(2000, 'mg')
        """
        f = conversion_factors

        try:
            new_value = self.value / f[self.unit] * f[new_unit]
        except KeyError as err:
            guess = did_you_mean(str(err), f.keys())
            raise ValueError(f"cannot convert between {self.unit!r} and {new_unit!r}, did you mean: {guess!r}")

        return Quantity(new_value, new_unit)

    def require_matching_unit(self, other):
        if other is None or self.unit != other.unit:
            raise ValueError(f"'{self}' and '{other}' have different units.")


    def _overload_unary_op(f):

        def wrapper(self, *args, **kwargs):
            value = f(self.value, *args, **kwargs)
            return Quantity(value, self.unit)

        return wrapper

    def _overload_binary_op(f, side, quantity, scalar):
        validators = {
                'ok':           lambda self, other: True,
                'error':        lambda self, other: False,
                '0 only':       lambda self, other: other == 0,
                'same unit':    lambda self, other: self.unit == other.unit,
        }
        operators = {
                'left':         lambda a, b: f(a, b),
                'right':        lambda a, b: f(b, a),
        }
        unit_handlers = {
                'keep':         lambda value, unit: Quantity(value, unit),
                'drop':         lambda value, unit: value,
        }

        operator = operators[side]

        def wrapper(self, other):
            try:
                other = self.from_anything(other)
                other_value = other.value
                params = quantity

            except ValueError:
                if isinstance(other, Number):
                    other_value = other
                    params = scalar
                else:
                    return NotImplemented

            except:
                return NotImplemented
            
            if not validators[params['validate']](self, other):
                return NotImplemented

            value = operator(self.value, other_value)
            return unit_handlers[params['unit']](value, self.unit)

        wrapper.__name__ = f'__{"r" if side == "right" else ""}{f.__name__}__'
        wrapper.__doc__ = f.__doc__

        return wrapper

    __pos__ = _overload_unary_op(pos)
    __neg__ = _overload_unary_op(neg)
    __abs__ = _overload_unary_op(abs)
    __ceil__ = _overload_unary_op(math.ceil)
    __floor__ = _overload_unary_op(math.floor)
    __trunc__ = _overload_unary_op(math.trunc)
    __round__ = _overload_unary_op(round)

    __eq__ = _overload_binary_op(
            eq, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __ne__ = _overload_binary_op(
            ne, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __lt__ = _overload_binary_op(
            lt, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __le__ = _overload_binary_op(
            le, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __gt__ = _overload_binary_op(
            gt, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __ge__ = _overload_binary_op(
            ge, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __add__ = _overload_binary_op(
            add, 'left',  
            quantity=dict(validate='same unit', unit='keep'),
            scalar=  dict(validate='0 only',    unit='keep'),
    )
    __radd__ = _overload_binary_op(
            add, 'right', 
            quantity=dict(validate='same unit', unit='keep'),
            scalar=  dict(validate='0 only',    unit='keep'),
    )
    __sub__ = _overload_binary_op(
            sub, 'left',  
            quantity=dict(validate='same unit', unit='keep'),
            scalar=  dict(validate='0 only',    unit='keep'),
    )
    __rsub__ = _overload_binary_op(
            sub, 'right', 
            quantity=dict(validate='same unit', unit='keep'),
            scalar=  dict(validate='0 only',    unit='keep'),
    )
    __mul__ = _overload_binary_op(
            mul, 'left',  
            quantity=dict(validate='error',                ),
            scalar=  dict(validate='ok',        unit='keep'),   
    )
    __rmul__ = _overload_binary_op(
            mul, 'right', 
            quantity=dict(validate='error',                ),
            scalar=  dict(validate='ok',        unit='keep'),   
    )
    __pow__ = _overload_binary_op(
            pow, 'left',  
            quantity=dict(validate='error',                ),
            scalar=  dict(validate='error',                ),   
    )
    __rpow__ = _overload_binary_op(
            pow, 'right', 
            quantity=dict(validate='error',                ),
            scalar=  dict(validate='error',                ),   
    )
    __truediv__ = _overload_binary_op(
            truediv, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='ok',        unit='keep'),   
    )
    __rtruediv__ = _overload_binary_op(
            truediv, 'right', 
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __floordiv__ = _overload_binary_op(
            floordiv, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='ok',        unit='keep'),   
    )
    __rfloordiv__ = _overload_binary_op(
            floordiv, 'right', 
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __mod__ = _overload_binary_op(
            mod, 'left',
            quantity=dict(validate='error'                 ),
            scalar=  dict(validate='error'                 ),
    )
    __rmod__ = _overload_binary_op(
            mod, 'right',
            quantity=dict(validate='error'                 ),
            scalar=  dict(validate='error'                 ),
    )

    del _overload_unary_op
    del _overload_binary_op

Q = Quantity.from_string

