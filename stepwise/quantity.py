#!/usr/bin/env python3

import re
import autoprop
from operator import lt, le, eq, ne, ge, gt, add, sub, mul, truediv, floordiv
from collections.abc import Iterable

@autoprop
class Quantity:
    """
    Simple class to manage numbers with units.

    - Support basic arithmetic operations that don't change the unit.

    - For arithmetic, units must match exactly.  Metric prefixes are not 
      understood.

    - Immutable
    """
    FLOAT_REGEX = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
    UNIT_REGEX = r'[^\s\d]+'
    QUANTITY_REGEX = fr'^\s*({FLOAT_REGEX})\s*({UNIT_REGEX})$'
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
    def from_tuple(cls, tuple):
        if len(tuple) != 2:
            raise ValueError(f"{tuple!r} has {len(tuple)} values, expected 2.")
        return cls(*tuple)


    def __init__(self, value, unit):
        self._value = float(value)
        self._unit = unit

        if not re.fullmatch(self.UNIT_REGEX, unit):
            raise ValueError(f"not a valid unit: {unit!r}")

        # There are two unicode "micro" characters (one is meant to be the 
        # micro prefix, while the other is meant to be the Greek mu).  Replace 
        # the "mu" with the "micro" to avoid confusion.
        self._unit = unit.replace('\u03bc', 'µ')

    def __repr__(self):
        return f'Quantity({self.value:g}, {self.unit!r})'

    def __str__(self):
        return self.show()

    def __format__(self, spec):
        return self.show(spec)

    def __bool__(self):
        return bool(self.value)

    def get_value(self):
        return self._value

    def get_unit(self):
        return self._unit

    def get_tuple(self):
        return self._value, self._unit

    def show(self, format=''):
        padding = '' if self.unit in self.NO_PADDING else ' '
        return f'{self.value:{format or "g"}}{padding}{self.unit}'

    def require_matching_unit(self, other):
        if other is None or self.unit != other.unit:
            raise ValueError(f"'{self}' and '{other}' have different units.")


    def _overload_binary_op(f, side, quantity, scalar):

        def validate_quantity_same_unit(self, other):
            self.require_matching_unit(other)
            return True

        def validate_scalar_zero_only(self, other):
            return other == 0

        validators = {
                'ok':           lambda self, other: True,
                'error':        lambda self, other: False,
                '0 only':       validate_scalar_zero_only,
                'same unit':    validate_quantity_same_unit,
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
            if isinstance(other, (int, float)):
                other_value = other
                params = scalar
            else:
                other = self.from_anything(other)
                other_value = other.value
                params = quantity

            if not validators[params['validate']](self, other):
                operands = {
                        'left': f"'{self}' and '{other}'",
                        'right': f"'{other}' and '{self}'",
                }
                raise ValueError(f"cannot {f.__name__} {operands[side]}")

            value = operator(self.value, other_value)
            return unit_handlers[params['unit']](value, self.unit)

        return wrapper

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
    __ge__ = _overload_binary_op(
            ge, 'left',  
            quantity=dict(validate='same unit', unit='drop'),
            scalar=  dict(validate='0 only',    unit='drop'),
    )
    __gt__ = _overload_binary_op(
            gt, 'left',  
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

    del _overload_binary_op

Q = Quantity.from_string

