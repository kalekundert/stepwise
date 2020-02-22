#!/usr/bin/env python3

import re
import math
import autoprop
import functools
import pandas as pd
from operator import lt, le, eq, ne, ge, gt, add, sub, mul, truediv, floordiv
from pathlib import Path
from collections.abc import Iterable
from nonstdlib import plural
from more_itertools import one
from .utils import *

# Solvent handling
# ================
# - Having solvent be an attribute of Reaction ensures that there is only ever 
#   one solvent.
#
# - Right now, you got to set the solvent before declaring all the reagents, 
#   cuz you can't make a reagent a solvent once it's there.  That's kinda 
#   obnoxious.

@autoprop
class MasterMix:

    @classmethod
    def from_text(cls, *args, **kwargs):
        return cls(Reaction.from_text(*args, **kwargs))

    @classmethod
    def from_csv(cls, *args, **kwargs):
        return cls(Reaction.from_csv(*args, **kwargs))

    @classmethod
    def from_tsv(cls, *args, **kwargs):
        return cls(Reaction.from_tsv(*args, **kwargs))

    @classmethod
    def from_excel(cls, *args, **kwargs):
        return cls(Reaction.from_excel(*args, **kwargs))

    @classmethod
    def from_pandas(cls, *args, **kwargs):
        return cls(Reaction.from_pandas(*args, **kwargs))


    def __init__(self, reaction=None):
        if isinstance(reaction, (str, Path, pd.DataFrame)):
            raise TypeError(
                    f"expected a Reaction, got a {type(reaction)}.\n\nDid you mean to call {self.__class__.__qualname__}.from_text()")

        self.reaction = reaction or Reaction()
        self.num_reactions = 1
        self.extra_fraction = 0.1
        self.extra_reactions = 0
        self.extra_min_volume = 0
        self.show_1x = True
        self.show_master_mix = None
        self.show_totals = True

    def __repr__(self):
        return self.reaction.__repr__.__func__(self)

    def __str__(self):
        return self.show()

    def __iter__(self):
        return self.reaction.__iter__()

    def __contains__(self, key):
        return self.reaction.__contains__(key)

    def __len__(self):
        return self.reaction.__len__()

    def __getitem__(self, key):
        return self.reaction.__getitem__(key)

    def __delitem__(self, key):
        return self.reaction.__delitem__(key)

    def __getattr__(self, attr):
        # Note that `__getattr__()` isn't used to lookup dunder methods, so 
        # methods like `__getitem__()` need to be explicitly defined.
        #
        # See Section 3.3.10 of the python docs.
        try:
            return getattr(self.reaction, attr)
        except AttributeError as err:
            raise AttributeError(str(err).replace(
                self.reaction.__class__.__name__,
                self.__class__.__name__,
                1,
            ))

    def __setattr__(self, attr, value):
        # We need to check if the constructor is finished without triggering 
        # `__getattr__()`, which would result in infinite recursion.
        if 'reaction' in self.__dict__:
            if hasattr(self.reaction, attr):
                return setattr(self.reaction, attr, value)

        return super().__setattr__(attr, value)

    def get_master_mix_reagents(self):
        yield from [x for x in self if x.master_mix]

    def get_master_mix_volume(self):
        return sum(x.volume for x in self.master_mix_reagents)

    def get_extra_percent(self):
        return 100 * self.extra_fraction

    def set_extra_percent(self, percent):
        self.extra_fraction = percent / 100

    def get_scale(self):
        self.require_volumes()
        min_volume = min(
                (x.volume for x in self.master_mix_reagents),
                default=None,
        )
        return max((
            self.num_reactions * (1 + self.extra_fraction),
            self.num_reactions + self.extra_reactions,
            self.extra_min_volume / min_volume if min_volume is not None else 0,
        ))

    def show(self):
        show_master_mix = not any([
                # Nothing in the master mix:
                not any(self.master_mix_reagents),

                # Only one reaction:
                self.num_reactions == 1 and self.show_master_mix == None,  

                # Column explicitly turned off:
                self.show_master_mix == False,
        ])

        def cols(*cols):
            """
            Eliminate columns the user doesn't want to see.
            """
            cols = list(cols)

            if not show_master_mix:
                del cols[3]
            if not self.show_1x:
                del cols[2]
            return cols

        def scale_header():
            strip_0 = lambda x: x.rstrip('0').rstrip('.')
            scale_str_1 = strip_0(f"{self.scale:.1f}")
            scale_str_5 = strip_0(f"{self.scale:.5f}")
            prefix = '' if scale_str_1 == scale_str_5 else '≈'
            return f'{prefix}{scale_str_1}x'

        # Figure out how big the table should be.

        column_titles = cols(
                "Reagent",
                "Stock",
                "Volume",
                scale_header(),
        )
        column_footers = cols(
                '',
                '',
                f'{self.volume:.2f}',
                f'{sum(x.volume for x in self.master_mix_reagents):.2f}',
        )
        column_getters = cols(
                lambda x: x.name,
                lambda x: x.stock_conc or '',
                lambda x: f'{x.volume:.2f}',
                lambda x: f'{x.volume * self.scale:.2f}' if x.master_mix else '',
        )
        column_widths = [
                max(map(
                    lambda x: len(str(x)),
                    [title, footer] + [getter(x) for x in self]
                ))
                for title, footer, getter in 
                    zip(column_titles, column_footers, column_getters)
        ]
        column_alignments = '<>>>'
        row_template = '  '.join(
                '{{!s:{}{}}}'.format(column_alignments[i], column_widths[i])
                for i in range(len(column_titles))
        )

        # Assemble the table
        rule = '─' * (sum(column_widths) + 2 * len(column_widths) - 2)
        rows = [
            row_template.format(*column_titles),
            rule,
        ] + [
            row_template.format(
                *[getter(reagent) for getter in column_getters])
            for reagent in self.reaction if reagent.volume
        ]
        if self.show_totals and (self.show_1x or show_master_mix):
            rows += [
                rule,
                row_template.format(*column_footers),
            ]
        table = '\n'.join(rows)
        if show_master_mix and self.show_totals:
            table += '/rxn'

        return table

@autoprop
class Reaction:

    @classmethod
    def from_text(cls, text):
        """
        Define a reaction using an ASCII-style table.

        Here is an example table for a ligation reaction::

            Reagent           Stock Conc    Volume  Master Mix
            ================  ==========  ========  ==========
            water                          6.75 μL         yes
            T4 ligase buffer         10x   1.00 μL         yes
            T4 PNK               10 U/μL   0.25 μL         yes
            T4 DNA ligase       400 U/μL   0.25 μL         yes
            DpnI                 20 U/μL   0.25 μL         yes
            PCR product         50 ng/μL   1.50 μL

        The first three columns are required, the fourth is optional.  The 
        column headers must exactly match the following:

        - "Reagent"
        - "Stock" or "Stock Conc"
        - "Volume"
        - "Master Mix" or "MM?"

        Extra columns will be ignored.  The columns are delineated by looking 
        for breaks of at least 2 spaces in the underline below the header.  
        Either '=' or '-' can be used for the underline.  The values in the 
        "Stock Conc" and "Volume" columns must have units.  The values in the 
        "Master Mix" column must be either "yes", "no", or "" (which means 
        "no").
        """
        lines = text.strip().splitlines()

        if len(lines) < 3:
            raise UsageError(f"reagent table has {plural(lines):? line/s}, but needs at least 3 (i.e. header, underline, first reagent).")
        if not re.match(r'[-=\s]+', lines[1]):
            raise UsageError(f"the 2nd line of the reagent table must be an underline (e.g. '===' or '---'), not {lines[1]!r}.")

        column_slices = [
                slice(x.start(), x.end())
                for x in re.finditer('[-=]+', lines[1])
        ]
        def split_columns(line):
            return tuple(line[x].strip() for x in column_slices)

        header = split_columns(lines[0])
        reagents = [split_columns(x) for x in lines[2:]]

        df = pd.DataFrame.from_records(reagents, columns=header)
        return cls.from_pandas(df)

    @classmethod
    def from_csv(cls, path_or_buffer, *args, **kwargs):
        df = pd.read_csv(path_or_buffer, *args, **kwargs)
        return cls.from_pandas(df)

    @classmethod
    def from_tsv(cls, path_or_buffer, *args, **kwargs):
        df = pd.read_csv(path_or_buffer, sep='\t', *args, **kwargs)
        return cls.from_pandas(df)

    @classmethod
    def from_excel(cls, path_or_buffer, *args, **kwargs):
        df = pd.read_excel(path_or_buffer, *args, **kwargs)
        return cls.from_pandas(df)

    @classmethod
    def from_pandas(cls, df):
        """
        Define a reaction from a pandas data frame.

        The data frame must have the following columns:

        - "Reagent"
        - "Stock" or "Stock Conc"
        - "Volume"
        - "Master Mix" or "MM?"

        The values in the "Reagent" column must be strings.  The values in the 
        "Stock Conc" and "Volume" columns must be strings containing a number 
        and a unit, i.e. compatible with `Quantity.from_string()`.  The values 
        in the "Master Mix" column can be either booleans or the strings "yes", 
        "y", "no", or "n".
        """
        rxn = cls()

        # Use consistent column names:

        df = df.rename(
                columns={
                    'Stock': 'Stock Conc',
                    'MM?': 'Master Mix',
                },
        )

        # Use empty strings to denote missing values:

        df = df.fillna('')

        # Make sure the table makes sense:

        # - Make sure all the required columns are present.
        # - Fill in any missing optional columns with default values.
        # - Unexpected columns are allowed.  Maybe the user wanted to annotate 
        #   the reaction with comments or product numbers or something.
        # - Make sure there is at least one row.
        # - Make sure every reagent is named.
        # - Make sure every reagent has a volume.

        def required_column(df, name):
            if name not in df.columns:
                raise UsageError(f"no {name!r} column found.")

        def optional_column(df, name, default):
            if name not in df.columns:
                df[name] = default
        
        required_column(df, 'Reagent')
        required_column(df, 'Stock Conc')
        required_column(df, 'Volume')
        optional_column(df, 'Master Mix', False)

        if len(df) == 0:
            raise UsageError("reaction must have at least one reagent.")
        if (df['Reagent'] == '').any():
            raise UsageError("some reagents are missing names.")
        if (df['Volume'] == '').any():
            raise UsageError("some reagents are missing volumes.")

        # Configure the solvent:

        is_solvent = df['Volume'].str.strip().str.startswith('to')
        i, solvent_row = one(
                df[is_solvent].iterrows(),
                UsageError("no solvent found.\nUse the 'to <total volume>' syntax in the 'Volume' column to specify the solvent."),
                UsageError("multiple solvents specified."),
        )

        rxn.solvent = solvent_row['Reagent']
        rxn.volume = solvent_row['Volume'][2:]

        # Configure all the other reagents:

        def parse_bool(x):
            if x in ('yes', 'y', 'x', 1):
                return True
            if x in ('no', 'n', '', 0):
                return False
            raise UsageError(f"expected 'yes' or 'no', got '{x}'")

        for i, row in df.iterrows():
            key = row['Reagent']
            non_solvent = ns = (key != rxn.solvent)

            if (x := row['Stock Conc']):    rxn[key].stock_conc = x
            if (x := row['Volume']) and ns: rxn[key].volume = x
            if (x := row['Master Mix']):    rxn[key].master_mix = parse_bool(x)

        return rxn


    def __init__(self):
        self._reagents = {}
        self._volume = None
        self._solvent = 'water'

    def __repr__(self):
        reagents = ', '.join(f'{x.name!r}' for x in self)
        return f'{self.__class__.__name__}({reagents})'

    def __iter__(self):
        if self._solvent is not None:
            if self._solvent not in self._reagents:
                yield Solvent(self)

        yield from sorted(
                self._reagents.values(),
                key=lambda x: math.inf if x.order is None else x.order
        )

    def __contains__(self, key):
        if key in self._reagents:
            return True

        if self._solvent is not None:
            if key == self._solvent:
                return True

        return False

    def __len__(self):
        return len(self._reagents) + (
                self._solvent is not None and
                self._solvent not in self._reagents
        )

    def __getitem__(self, key):
        if key not in self._reagents:
            if key == self._solvent:
                self._reagents[key] = Solvent(self)
            else:
                self._reagents[key] = Reagent(self, key)

        return self._reagents[key]

    def __delitem__(self, key):
        if key in self._reagents:
            del self._reagents[key]
        if key == self._solvent:
            self._solvent = None

    def get_volume(self):
        self.require_solvent()
        return self._volume

    def set_volume(self, volume):
        self._volume = Quantity.from_anything(volume)

    def get_solvent(self):
        return self._solvent

    def set_solvent(self, key):
        old_solvent = self._solvent
        new_solvent = key

        if new_solvent == old_solvent:
            return

        if new_solvent in self._reagents:
            raise ValueError(f"'{new_solvent}' is already a reagent.")

        if old_solvent in self._reagents:
            if new_solvent is not None:
                self._reagents[new_solvent] = self._reagents[old_solvent]
            del self._reagents[old_solvent]

        # Don't need to instantiate the solvent here.  It'll get instantiated 
        # when someone tries to access it; see `__getitem__()`.
        self._solvent = new_solvent

    @property
    def hold_ratios(self):
        return self._HoldRatios(self)

    def require_volume(self):
        if self._volume is None:
            raise ValueError(f"no reaction volume specified")

    def require_volumes(self):
        self.require_volume()
        for reagent in self:
            if reagent is not self[self.solvent]:
                reagent.require_volume()

    def require_solvent(self):
        if self._solvent is None:
            raise ValueError(f"no solvent specified")

    @autoprop
    class _HoldRatios:
        """
        Change the volume of the reaction without changing the relative 
        quantities of any of the reagents.
        """

        def __init__(self, reaction):
            self.reaction = reaction

        def get_volume(self):
            return self.reaction.volume

        def set_volume(self, volume):
            self.reaction.require_volume()

            v1 = self.reaction.volume
            v2 = Quantity.from_anything(volume)

            for reagent in self.reaction:
                if reagent.key != self.reaction.solvent:
                    reagent.require_volume()
                    reagent.volume *= v2 / v1

            self.reaction.volume = v2

@autoprop
class Reagent:

    def __init__(self, reaction, key):
        self._reaction = reaction
        self._reaction._reagents[key] = self

        self._key = key
        self._name = None
        self._volume = None
        self._stock_conc = None

        self.master_mix = False
        self.order = None

    def __repr__(self):
        reaction_id = str(id(self._reaction))[-4:]
        return f'Reagent(reaction={reaction_id}, name={self.name!r})'

    def get_reaction(self):
        return self._reaction

    def get_key(self):
        return self._key

    def set_key(self, key):
        del self.reaction[self._key]
        self._reaction._reagents[key] = self
        self._key = key

    def get_name(self):
        return self._name or self._key

    def set_name(self, name):
        self._name = name

    def get_volume(self):
        return self._volume

    def set_volume(self, volume):
        self._volume = Quantity.from_anything(volume)

    def get_conc(self):
        self.require_volume()
        self.require_stock_conc()
        self._reaction.require_volume()

        ratio = self._volume / self._reaction.volume
        return self._stock_conc * ratio

    def get_stock_conc(self):
        return self._stock_conc

    def set_stock_conc(self, stock_conc):
        self._stock_conc = Quantity.from_anything(stock_conc)

    @property
    def hold_volume(self):
        return self._HoldVolume(self)

    @property
    def hold_conc(self):
        return self._HoldConc(self)

    @property
    def hold_stock_conc(self):
        return self._HoldStockConc(self)

    def require_volume(self):
        if self.volume is None:
            raise ValueError(f"no volume specified for '{self.name}'")

    def require_stock_conc(self):
        if self.stock_conc is None:
            raise ValueError(f"no stock concentration specified for '{self.name}'")

    @autoprop
    class _HoldConc:
        """
        Change the volume or stock concentration of the reagent without 
        changing its final concentration.
        
        The equation below gives the relation between the stock concentration 
        :math:`C` of the reagent, the volume :math:`V` of the reagent, the 
        concentration :math:`c` of the reagent in the reaction, and the volume 
        :math:`v` of the whole reaction:

        .. math::

            C V = c v

        If we wish to change :math:`C` or :math:`V` without changing :math:`c` or :math:`v`:

        .. math::

            C V = c v = k

            C_1 V_1 = C_2 V_2

            C_2 = C_1 \frac{V_1}{V_2}

            V_2 = V_1 \frac{C_1}{C_2}
        """

        def __init__(self, reagent):
            self.reagent = reagent

        def get_volume(self):
            return self.reagent.volume

        def set_volume(self, volume):
            self.reagent.require_volume()
            self.reagent.require_stock_conc()

            v1 = self.volume
            v2 = Quantity.from_anything(volume)
            c1 = self.stock_conc
            c2 = c1 * (v1 / v2)

            self.reagent.volume = v2
            self.reagent.stock_conc = c2

        def get_stock_conc(self):
            return self.reagent.stock_conc

        def set_stock_conc(self, stock_conc):
            self.reagent.require_volume()
            self.reagent.require_stock_conc()

            c1 = self.stock_conc
            v1 = self.volume
            c2 = Quantity.from_anything(stock_conc)
            v2 = v1 * (c1 / c2)

            self.reagent.volume = v2
            self.reagent.stock_conc = c2

    @autoprop
    class _HoldVolume:
        """
        Change the final or stock concentration of the reagent without 
        changing its volume.
        
        The equation below gives the relation between the stock concentration 
        :math:`C` of the reagent, the volume :math:`V` of the reagent, the 
        concentration :math:`c` of the reagent in the reaction, and the volume 
        :math:`v` of the whole reaction:

        .. math::

            C * V = c * v

        If we wish to change :math:`C` or :math:`c` without changing :math:`V` or :math:`v`:

        .. math::

            C / c = v / V = k

            C_1 / c_1 = C_2 / c_2

            C_2 = C_1 \frac{c_2}{c_1}

            c_2 = c_1 \frac{C_2}{C_1}
        """

        def __init__(self, reagent):
            self.reagent = reagent

        def get_conc(self):
            return self.reagent.conc

        def set_conc(self, conc):
            self.reagent.require_volume()
            self.reagent.require_stock_conc()

            c1 = self.conc
            s1 = self.stock_conc
            c2 = Quantity.from_anything(conc)
            s2 = s1 * (c2 / c1)

            self.reagent.stock_conc = s2

        def get_stock_conc(self):
            return self.reagent.stock_conc

        def set_stock_conc(self, stock_conc):
            self.reagent.require_volume()
            self.reagent.require_stock_conc()

            s1 = self.stock_conc
            c1 = self.conc
            s2 = Quantity.from_anything(stock_conc)
            c2 = c1 * (s2 / s1)

            self.reagent.stock_conc = s2

    @autoprop
    class _HoldStockConc:
        """
        Change the volume or concentration of the reagent without changing its 
        stock concentration.
        
        The equation below gives the relation between the stock concentration 
        :math:`C` of the reagent, the volume :math:`V` of the reagent, the 
        concentration :math:`c` of the reagent in the reaction, and the volume 
        :math:`v` of the whole reaction:

        .. math::

            C * V = c * v

        If we wish to change :math:`V` or :math:`c` without changing :math:`C` or :math:`v`:

        .. math::

            V / c = v / C = k

            V_1 / c_1 = V_2 / c_2

            V_2 = V_1 \frac{c_2}{c_1}

            c_2 = c_1 \frac{V_2}{V_1}
        """

        def __init__(self, reagent):
            self.reagent = reagent

        def get_volume(self):
            return self.reagent.volume

        def set_volume(self, volume):
            self.reagent.require_volume()
            self.reagent.require_stock_conc()

            v1 = self.volume
            c1 = self.conc
            v2 = Quantity.from_anything(volume)
            c2 = c1 * (v2 / v1)

            self.reagent.volume = v2

        def get_conc(self):
            return self.reagent.conc

        def set_conc(self, conc):
            self.reagent.require_volume()
            self.reagent.require_stock_conc()

            c1 = self.conc
            v1 = self.volume
            c2 = Quantity.from_anything(conc)
            v2 = v1 * (c2 / c1)

            self.reagent.volume = v2

@autoprop
class Solvent:

    def __init__(self, reaction):
        self._reaction = reaction
        self._name = None
        self._stock_conc = None
        self.master_mix = False
        self.order = None

    def get_key(self):
        return self._reaction.solvent

    def set_key(self, key):
        self._reaction.solvent = key

    def get_name(self):
        return self._name or self.key

    def set_name(self, name):
        self._name = name

    def get_volume(self):
        self._reaction.require_volume()
        v = self._reaction.volume

        for reagent in self._reaction:
            if reagent is not self:
                reagent.require_volume()
                v -= reagent.volume

        return v

    def set_volume(self, volume):
        raise NotImplementedError("cannot directly set solvent volume, set the reaction volume instead.")

    def get_stock_conc(self):
        return self._stock_conc

    def set_stock_conc(self, stock_conc):
        self._stock_conc = Quantity.from_anything(stock_conc)

    def require_volume(self):
        self._reaction.require_volume()



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
    QUANTITY_REGEX = fr'^\s*({FLOAT_REGEX})\s*(\S+)$'
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
        self._value = value
        self._unit = unit

    def __repr__(self):
        return f'Quantity({self.value}, {self.unit!r})'

    def __str__(self):
        return self.show()

    def __format__(self, spec):
        return self.show(spec)

    def get_value(self):
        return self._value

    def get_unit(self):
        return self._unit

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
