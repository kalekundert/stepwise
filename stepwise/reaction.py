#!/usr/bin/env python3

import re
import math
import autoprop
import functools
import pandas as pd
from operator import add, sub, mul, truediv, floordiv
from collections.abc import Iterable
from nonstdlib import plural
from . import UserError

@autoprop
class MasterMix:

    @classmethod
    def from_text(cls, text):
        return cls(Reaction.from_text(text))

    @classmethod
    def from_csv(cls, csv):
        return cls(Reaction.from_csv(csv))

    @classmethod
    def from_tsv(cls, tsv):
        return cls(Reaction.from_tsv(tsv))

    @classmethod
    def from_excel(cls, excel):
        return cls(Reaction.from_excel(excel))

    @classmethod
    def from_pandas(cls, pandas):
        return cls(Reaction.from_pandas(pandas))


    def __init__(self, reaction=None):
        self.reaction = reaction or Reaction()
        self.num_reactions = 1
        self.extra_fraction = 0.1
        self.extra_reactions = 0
        self.show_1x = True
        self.show_master_mix = None
        self.show_totals = True

    def __repr__(self):
        return self.reaction.__repr__.__func__(self)

    def __str__(self):
        return self.show()

    def __iter__(self):
        return self.reaction.__iter__()

    def __contains__(self, name):
        return self.reaction.__contains__(name)

    def __len__(self):
        return self.reaction.__len__()

    def __getitem__(self, name):
        return self.reaction.__getitem__(name)

    def __delitem__(self, name):
        return self.reaction.__delitem__(name)

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

    def get_extra_percent(self):
        return 100 * self.extra_fraction

    def set_extra_percent(self, percent):
        self.extra_fraction = percent / 100

    def get_extra_factor(self):
        return max((
            self.num_reactions * (1 + self.extra_fraction),
            self.num_reactions + self.extra_reactions,
        ))

    def show(self):

        show_master_mix = not any([
                # Nothing in the master mix:
                not any(x.master_mix for x in self),

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
            scale_str = f"{self.extra_factor:.1g}"
            print(scale_str)
            print(str(self.extra_factor))
            prefix = '' if scale_str == str(self.extra_factor) else '≈'
            return f'{prefix}{scale_str}x'

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
                f'{sum((x.volume for x in self.reaction if x.master_mix)):.2f}',
        )
        column_getters = cols(
                lambda x: x.name,
                lambda x: x.stock_conc if isinstance(x, Reagent) else '',
                lambda x: f'{x.volume:.2f}',
                lambda x: f'{x.volume * self.extra_factor:.2f}' if x.master_mix else '',
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
    def from_text(cls, text, solvent='water'):
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
            raise UserError(f"reagent table has {plural(lines):? line/s}, but needs at least 3 (i.e. header, underline, first reagent).")
        if not re.match(r'[-=\s]+', lines[1]):
            raise UserError(f"the 2nd line of the reagent table must be an underline (e.g. '===' or '---'), not {lines[1]!r}.")

        column_slices = [
                slice(x.start(), x.end())
                for x in re.finditer('[-=]+', lines[1])
        ]
        def split_columns(line):
            return tuple(line[x].strip() for x in column_slices)

        header = split_columns(lines[0])
        reagents = [split_columns(x) for x in lines[2:]]

        df = pd.DataFrame.from_records(reagents, columns=header)
        return cls.from_pandas(df, solvent)

    @classmethod
    def from_csv(cls, path_or_buffer, solvent='water', *args, **kwargs):
        df = pd.read_csv(path_or_buffer, *args, **kwargs)
        return cls.from_pandas(df, solvent)

    @classmethod
    def from_tsv(cls, path_or_buffer, solvent='water', *args, **kwargs):
        df = pd.read_csv(path_or_buffer, sep='\t', *args, **kwargs)
        return cls.from_pandas(df, solvent)

    @classmethod
    def from_excel(cls, path_or_buffer, solvent='water', *args, **kwargs):
        df = pd.read_excel(path_or_buffer, *args, **kwargs)
        return cls.from_pandas(df, solvent)

    @classmethod
    def from_pandas(cls, df, solvent='water'):
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
        rxn.solvent = solvent

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
        #
        # - Make sure all the required columns are present.
        # - Fill in any missing optional columns with default values.
        # - Unexpected columns are allowed.  Maybe the user wanted to annotate 
        #   the reaction with comments or product numbers or something.
        # - Make sure there is at least one row.
        # - Make sure every reagent is named.
        # - Make sure one of the reagents is the solvent.

        def required_column(df, name):
            if name not in df.columns:
                raise UserError(f"no {name!r} column found.")

        def optional_column(df, name, default):
            if name not in df.columns:
                df[name] = default
        
        required_column(df, 'Reagent')
        required_column(df, 'Stock Conc')
        required_column(df, 'Volume')
        optional_column(df, 'Master Mix', False)

        if len(df) == 0:
            raise UserError("reaction must have at least one reagent.")
        if '' in list(df['Reagent']):
            raise UserError("some reagents are missing names.")

        # Find the volume of the reaction.
        #
        # - Don't set a volume for the whole reaction if any of the reagents 
        #   have undefined volumes.

        have_volumes = all(x != '' for x in df['Volume'])
        have_solvent = solvent in set(df['Reagent'])

        if have_volumes and have_solvent:
            rxn.volume = sum(
                    Quantity.from_string(x)
                    for x in df['Volume']
            )

        # Define all the reagents:

        def parse_bool(x):
            if x in ('yes', 'y', 'x', 1):
                return True
            if x in ('no', 'n', '', 0):
                return False
            raise UserError(f"expected 'yes' or 'no', got '{x}'")

        for i, row in df.iterrows():
            name = row['Reagent']
            non_solvent = ns = (name != solvent)

            if row['Stock Conc'] and (name == solvent):
                raise UserError(f"stock concentration {row['Stock Conc']!r} specified for solvent {name!r}")

            if (x := row['Stock Conc']):    rxn[name].stock_conc = x
            if (x := row['Volume']) and ns: rxn[name].volume = x
            if (x := row['Master Mix']):    rxn[name].master_mix = parse_bool(x)

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

    def __contains__(self, name):
        if name in self._reagents:
            return True

        if self._solvent is not None:
            if name == self._solvent:
                return True

        return False

    def __len__(self):
        return len(self._reagents) + (
                self._solvent is not None and
                self._solvent not in self._reagents
        )

    def __getitem__(self, name):
        if name not in self._reagents:
            if name == self._solvent:
                self._reagents[name] = Solvent(self)
            else:
                self._reagents[name] = Reagent(self, name)

        return self._reagents[name]

    def __delitem__(self, name):
        if name in self._reagents:
            del self._reagents[name]
        if name == self._solvent:
            self._solvent = None

    def get_volume(self):
        self.require_solvent()
        return self._volume

    def set_volume(self, volume):
        self._volume = Quantity.from_anything(volume)

    def get_solvent(self):
        return self._solvent

    def set_solvent(self, name):
        old_solvent = self._solvent
        new_solvent = name

        if new_solvent == old_solvent:
            return

        if new_solvent in self._reagents:
            raise ValueError(f"'{new_solvent}' is already a reagent.")

        if old_solvent in self._reagents:
            if new_solvent is not None:
                self._reagents[new_solvent] = self._reagents[old_solvent]
            del self._reagents[old_solvent]

        self._solvent = new_solvent

    @property
    def hold_ratios(self):
        return self._HoldRatios(self)

    def require_volume(self):
        if self._volume is None:
            raise ValueError(f"no reaction volume specified")

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
                if reagent.name != self.reaction.solvent:
                    reagent.require_volume()
                    reagent.volume *= v2 / v1

            self.reaction.volume = v2

@autoprop
class Reagent:

    def __init__(self, reaction, name):
        self._reaction = reaction
        self._reaction._reagents[name] = self

        self._name = name
        self._volume = None
        self._stock_conc = None

        self.master_mix = False
        self.order = None

    def __repr__(self):
        reaction_id = str(id(self._reaction))[-4:]
        return f'Reagent(reaction={reaction_id}, name={self.name!r})'

    def get_reaction(self):
        return self._reaction

    def get_name(self):
        return self._name

    def set_name(self, name):
        del self.reaction[self._name]
        self._reaction._reagents[name] = self
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
        self.master_mix = False
        self.order = None

    def get_name(self):
        return self._reaction.solvent

    def set_name(self, name):
        self._reaction.solvent = name

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
    QUANTITY_REGEX = fr'^({FLOAT_REGEX})\s*(\S+)$'
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
            raise ValueError(f"'{string}' cannot be interpreted as a value with a unit.")

    @classmethod
    def from_tuple(cls, tuple):
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

    def __eq__(self, other):
        other = Quantity.from_anything(other)
        return (self.value == other.value and self.unit == other.unit)

    def get_value(self):
        return self._value

    def get_unit(self):
        return self._unit

    def show(self, format='g'):
        padding = '' if self.unit in self.NO_PADDING else ' '
        return f'{self.value:{format}}{padding}{self.unit}'

    def require_matching_unit(self, other):
        if self.unit != other.unit:
            raise ValueError(f"'{self}' and '{other}' have different units.")


    def _overload_operator(f, side, quantity='err', scalar='err'):

        def get_quantity_keep_unit(self, other):
            self.require_matching_unit(other)
            return other.value, self.unit

        def get_quantity_drop_unit(self, other):
            self.require_matching_unit(other)
            return other.value, None

        def get_quantity_err(self, other):
            raise ValueError(f"cannot {f.__name__} '{self}' and '{other}'")

        def get_scalar(self, other):
            return other, self.unit

        def get_scalar_zero_only(self, other):
            f = get_scalar if other == 0 else get_scalar_err
            return f(self, other)
            
        def get_scalar_err(self, other):
            raise ValueError(f"cannot {f.__name__} '{self}' and '{other}'")


        def quantity_or_scalar(value, unit):
            return value if unit is None else Quantity(value, unit)

        def op_left_side(self, k, unit):
            return quantity_or_scalar(f(self.value, k), unit)

        def op_right_side(self, k, unit):
            return quantity_or_scalar(f(k, self.value), unit)

        quantity_getters = {
                'keep unit':    get_quantity_keep_unit,
                'drop unit':    get_quantity_drop_unit,
                'err':          get_quantity_err,
        }
        scalar_getters = {
                'ok':           get_scalar,
                '0 only':       get_scalar_zero_only,
                'err':          get_scalar_err,
        }
        operators = {
                'right':        op_right_side,
                'left':         op_left_side,
        }
        operator = operators[side]

        def wrapper(self, other):
            if isinstance(other, (int, float)):
                getter = scalar_getters[scalar]
            else:
                other = self.from_anything(other)
                getter = quantity_getters[quantity]

            k, unit = getter(self, other)
            return operator(self, k, unit)

        return wrapper

    __add__  = _overload_operator(add, 'left',  quantity='keep unit', scalar='0 only')
    __radd__ = _overload_operator(add, 'right', quantity='keep unit', scalar='0 only')

    __sub__  = _overload_operator(sub, 'left',  quantity='keep unit', scalar='0 only')
    __rsub__ = _overload_operator(sub, 'right', quantity='keep unit', scalar='0 only')

    __mul__  = _overload_operator(mul, 'left',  scalar='ok')
    __rmul__ = _overload_operator(mul, 'right', scalar='ok')

    __truediv__   = _overload_operator(truediv,  'left', quantity='drop unit', scalar='ok')
    __rtruediv__  = _overload_operator(truediv,  'right', quantity='drop unit', scalar='err')
    __floordiv__  = _overload_operator(floordiv, 'left', quantity='drop unit', scalar='ok')
    __rfloordiv__ = _overload_operator(floordiv, 'right', quantity='drop unit', scalar='err')

    del _overload_operator

Q = Quantity.from_string
