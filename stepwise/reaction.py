#!/usr/bin/env python3

import re
import math
import autoprop
import functools
from pathlib import Path
from inform import plural, warn
from more_itertools import one, only
from .quantity import Quantity
from .table import tabulate
from .errors import *

# Solvent handling
# ================
# - Having solvent be an attribute of Reaction ensures that there is only ever 
#   one solvent.
#
# - Right now, you have to set the solvent before declaring all the reagents, 
#   because you can't turn a reagent into a solvent once it's been declared.  
#   That's kinda obnoxious, but it also kinda makes sense: what's the meaning 
#   of the volume of a reagent that's been turned into a solvent?

@autoprop
class MasterMix:

    def __init__(self, reaction=None):
        if isinstance(reaction, str):
            reaction = Reaction.from_text(reaction)
        if isinstance(reaction, dict):
            reaction = Reaction.from_cols(reaction)

        self.reaction = reaction or Reaction()
        self.num_reactions = 1
        self.extra_fraction = 0.1
        self.extra_reactions = 0
        self.extra_volume = 0
        self.extra_min_volume = 0  # Minimum volume of any reagent.
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

    def __getstate__(self):
        return vars(self)

    def __setstate__(self, state):
        vars(self).update(state)

    @classmethod
    def from_text(cls, text):
        return cls(Reaction.from_text(text))

    @classmethod
    def from_cols(cls, cols):
        return cls(Reaction.from_cols(cols))

    def iter_master_mix_reagents(self):
        yield from [x for x in self if x.master_mix]

    def get_master_mix_volume(self):
        v = 0
        for reagent in self.iter_master_mix_reagents():
            reagent.require_volume()
            v += reagent.volume
        return v

    def get_extra_percent(self):
        return 100 * self.extra_fraction

    def set_extra_percent(self, percent):
        self.extra_fraction = percent / 100

    def get_scale(self):
        self.require_volumes()
        min_volume = min(
                (x.volume for x in self.iter_master_mix_reagents()),
                default=None,
        )
        return max((
            self.num_reactions * (1 + self.extra_fraction),
            self.num_reactions + self.extra_reactions,
            self.num_reactions + self.extra_volume / self.volume,
            self.extra_min_volume / min_volume if min_volume else 0,
        ))

    def show(self):
        show_master_mix = not any([
                # Nothing in the master mix:
                not any(self.iter_master_mix_reagents()),

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

        header = cols(
                "Reagent",
                "Stock",
                "Volume",
                scale_header(),
        )
        rows = [
                cols(
                    x.name,
                    x.stock_conc or '',
                    f'{x.volume:.2f}',
                    f'{x.volume * self.scale:.2f}' if x.master_mix else '',
                )
                for x in self

                # Leave out reagents that round to 0 volume.
                if f'{abs(x.volume.value):.2f}' != '0.00'
        ]
        footer = None if not self.show_totals else cols(
                '',
                '',
                f'{self.volume:.2f}',
                f'{self.master_mix_volume:.2f}',
        )
        align = cols(*'<>>>')

        table = tabulate(rows, header, footer, align=align)

        if show_master_mix and self.show_totals:
            table += '/rxn'

        return table

    def format_text(self, width):
        # Don't wrap the table, because that would make it unreadable.
        return self.show()

    def replace_text(self, pattern, repl, **kwargs):
        from .protocol import replace_text
        # Only make substitutions in the reagent names.
        for reagent in self:
            reagent.name = replace_text(pattern, repl, reagent.name, **kwargs)


@autoprop
class Reaction:

    def __init__(self):
        self._reagents = {}
        self._volume = None
        self._solvent = 'water'

    def __repr__(self):
        reagents = ', '.join(f'{x.name!r}' for x in self)
        return f'{self.__class__.__name__}({reagents})'

    def __iter__(self):
        yield from self.iter_reagents()

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
        return self.add_reagent(key)

    def __delitem__(self, key):
        if key in self._reagents:
            del self._reagents[key]
        if key == self._solvent:
            self._solvent = None

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
        lines = text.rstrip().splitlines()

        if len(lines) < 3:
            raise UsageError(f"reagent table has {plural(lines):# line/s}, but needs at least 3 (i.e. header, underline, first reagent).")
        if not re.fullmatch(r'[-=\s]+', lines[1]):
            raise UsageError(f"the 2nd line of the reagent table must be an underline (e.g. '===' or '---'), not {lines[1]!r}.")

        column_slices = [
                slice(x.start(), x.end())
                for x in re.finditer('[-=]+', lines[1])
        ]
        def split_columns(line):
            return tuple(line[x].strip() for x in column_slices)

        header = split_columns(lines[0])
        reagents = [split_columns(x) for x in lines[2:]]  # list of tuples

        cols = {
                k: row
                for k, row in zip(header, zip(*reagents))
        }
        return cls.from_cols(cols)

    @classmethod
    def from_cols(cls, cols):
        """
        Define a reaction from a dictionary.

        The dictionary must have the following keys:

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

        # Use consistent column names:

        column_aliases = {
                'volume': {
                    'volume',
                    'Volume',
                },
                'reagent': {
                    'reagent',
                    'Reagent',
                },
                'stock_conc': {
                    'stock_conc',
                    'Stock Conc',
                    'Stock',
                },
                'master_mix': {
                    'master_mix',
                    'Master Mix',
                    'MM?',
                },
        }
        given_keys = set(cols.keys())

        for k_std, aliases in column_aliases.items():
            k_given = only(
                    (k_match := aliases & given_keys),
                    too_long=UsageError(f"multiple {k_std!r} columns found: {', '.join(repr(x) for x in sorted(k_match))}"),
            )
            if k_given:
                cols[k_std] = cols.pop(k_given)

        # Make sure the table makes sense:

        # - Make sure all the required columns are present.
        # - Unexpected columns are allowed.  Maybe the user wanted to annotate 
        #   the reaction with comments or product numbers or something.
        # - Make sure all the columns have the same number of rows.
        # - Make sure there is at least one row.
        # - Fill in any missing optional columns with default values.
        # - Make sure every reagent is named.
        # - Make sure every reagent has a volume.
        
        def required_column(key):
            if key not in cols:
                raise UsageError(f"no {key!r} column found")

        required_column('reagent')
        required_column('stock_conc')
        required_column('volume')

        num_rows = one(
                x := {len(v) for v in cols.values()},
                too_short=AssertionError,
                too_long=UsageError(f"columns have different numbers of rows: {', '.join(map(str, x))}"),
        )
        if num_rows == 0:
            raise UsageError("reaction must have at least one reagent.")

        def optional_column(key, default):
            if key not in cols:
                cols[key] = num_rows * [default]
        
        optional_column('master_mix', False)

        if not all(cols['reagent']):
            raise UsageError("some reagents are missing names.")
        if not all(cols['volume']):
            raise UsageError("some reagents are missing volumes.")

        # Configure the reaction:

        rxn = cls()
        del rxn.solvent

        def parse_bool(x):
            if x in ('yes', 'y', 'x', 1):
                return True
            if x in ('no', 'n', '', 0):
                return False
            raise UsageError(f"expected 'yes' or 'no', got '{x}'")

        for i in range(num_rows):
            is_solvent = cols['volume'][i].startswith('to')

            if is_solvent:
                if rxn.solvent:
                    raise UsageError("multiple solvents specified: {rxn.solvent!r}, {cols['reagent'][i]!r}")

                # Have to set the solvent before adding the reagent, because 
                # reagents can't be turned into solvents.
                rxn.solvent = cols['reagent'][i]
                rxn.volume = cols['volume'][i][2:]

            reagent = rxn.add_reagent(cols['reagent'][i])
            reagent.master_mix = parse_bool(cols['master_mix'][i])

            if (x := cols['stock_conc'][i]):
                reagent.stock_conc = x
            if not is_solvent:
                reagent.volume = cols['volume'][i]

        return rxn

    def iter_reagents(self):
        # Yield the solvent before any of the other reagents, unless the 
        # solvent has been explicitly added to the reaction.
        if self._solvent is not None:
            if self._solvent not in self._reagents:
                yield Solvent(self)

        yield from sorted(
                self._reagents.values(),
                key=lambda x: math.inf if x.order is None else x.order
        )

    def iter_non_solvent_reagents(self):
        for reagent in self:
            if reagent.key != self._solvent:
                yield reagent

    def get_volume(self):
        if self._solvent:
            return self._volume
        else:
            volume = 0
            for reagent in self:
                reagent.require_volume()
                volume += reagent.volume
            return volume

    def set_volume(self, volume):
        self.require_solvent()
        self._volume = Quantity.from_anything(volume)

    def get_free_volume(self):
        return self.get_free_volume_excluding()

    def get_free_volume_excluding(self, *keys):
        self.require_volume()
        v = self.volume

        for reagent in self.iter_non_solvent_reagents():
            if reagent.key not in keys:
                reagent.require_volume()
                v -= reagent.volume

        return v

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

    def del_solvent(self):
        self.solvent = None

    def add_reagent(self, key):
        if key not in self._reagents:
            if key == self._solvent:
                self._reagents[key] = Solvent(self)
            else:
                self._reagents[key] = Reagent(self, key)

        return self._reagents[key]

    @property
    def hold_ratios(self):
        return self._HoldRatios(self)

    def fix_volumes(self, donor, acceptor=None):
        """
        Make sure that all of the reagents fit in the reaction (i.e. that there 
        are no negative volumes) by transferring volume from the donor reagent 
        to the acceptor reagent, if necessary.

        Note that the volume of the donor reagent itself may be negative after 
        this method completes.  In some cases it may make sense to call this 
        method multiple times with different pairs of donors and acceptors.
        """
        if acceptor is None:
            acceptor = self.solvent

        self.require_reagent(donor)
        self.require_reagent(acceptor)

        donor_reagent = self[donor]
        acceptor_reagent = self[acceptor]

        if acceptor_reagent.volume < 0:
            donor_volume = donor_reagent.volume
            if donor != self.solvent:
                donor_reagent.volume += acceptor_reagent.volume
            if acceptor != self.solvent:
                acceptor_reagent.volume -= acceptor_reagent.volume
            warn(f"reagent volumes exceed reaction volume, reducing '{donor_reagent.name}' from {donor_volume} to {donor_reagent.volume} to compensate.")

    def require_reagent(self, key):
        if key not in self._reagents:
            raise ValueError(f"no '{key}` reagent in the reaction")

    def require_volume(self):
        if self._solvent and self._volume is None:
            raise ValueError(f"no reaction volume specified")

    def require_volumes(self):
        self.require_volume()
        for reagent in self:
            if reagent is not self._reagents.get(self._solvent):
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

            if self.reaction._solvent:
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

    def del_volume(self, volume):
        self._volume = None

    def get_conc(self):
        self.require_volume()
        self.require_stock_conc()
        self._reaction.require_volume()

        ratio = self._volume / self._reaction.volume
        return self._stock_conc * ratio

    def get_stock_conc(self):
        return self._stock_conc

    def set_stock_conc(self, stock_conc):
        try:
            self._stock_conc = Quantity.from_anything(stock_conc)
        except ValueError:
            self._stock_conc = stock_conc

    def del_stock_conc(self):
        self._stock_conc = None

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
        if not isinstance(self.stock_conc, Quantity):
            raise ValueError(f"stock concentration specified for '{self.name}' cannot be interpreted as a value with a unit")

    @autoprop
    class _HoldConc:
        """
        Change the volume or stock concentration of the reagent without 
        changing its final concentration.
        
        The equation below gives the relation between the stock concentration 
        :math:`C` of the reagent, the volume :math:`v` of the reagent, the 
        concentration :math:`c` of the reagent in the reaction, and the volume 
        :math:`V` of the whole reaction:

        .. math::

            C v = c V

        We can only set :math:`C` and :math:`v` directly.  If we wish to set 
        either without changing :math:`c`, we must use the following equations:

        .. math::

            c = \frac{C v}{V}

            \frac{C_1 v_1}{V} = \frac{C_2 v_2}{V}

            C_2 = \frac{C_1 v_1}{v_2}

            v_2 = \frac{C_1 v_1}{C_2}

        Note that the volume :math:`v_1` and stock concentration :math:`C_1` of 
        the reagent must already be specified in order for these equations to 
        be applied.
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
        :math:`C` of the reagent, the volume :math:`v` of the reagent, the 
        concentration :math:`c` of the reagent in the reaction, and the volume 
        :math:`V` of the whole reaction:

        .. math::

            C v = c V

        We can only set :math:`C` and :math:`v` directly, and in this case we 
        want to hold :math:`v` constant.  If we wish to set :math:`c` to a 
        particular value, we must set :math:`C` according to:

        .. math::

            C = \frac{c V}{v}

        Note that the volumes of the reagent and the whole reaction must 
        already be specified in order for the stock concentration to be set in 
        this manner.
        """

        def __init__(self, reagent):
            self.reagent = reagent

        def get_conc(self):
            return self.reagent.conc

        def set_conc(self, conc):
            self.reagent.require_volume()
            self.reagent.reaction.require_volume()

            c = Quantity.from_anything(conc)
            v_rxn = self.reagent.reaction.volume
            v = self.reagent.volume

            self.reagent.stock_conc = c * (v_rxn / v)

        def get_stock_conc(self):
            return self.reagent.stock_conc

        def set_stock_conc(self, stock_conc):
            self.reagent.stock_conc = Quantity.from_anything(stock_conc)

    @autoprop
    class _HoldStockConc:
        """
        Change the volume or concentration of the reagent without changing its 
        stock concentration.
        
        The equation below gives the relation between the stock concentration 
        :math:`C` of the reagent, the volume :math:`v` of the reagent, the 
        concentration :math:`c` of the reagent in the reaction, and the volume 
        :math:`V` of the whole reaction:

        .. math::

            C v = c V

        We can only set :math:`C` and :math:`v` directly, and in this case we 
        want to hold :math:`C` constant.  If we wish to set :math:`c` to a 
        particular value, we must set :math:`v` according to:

        .. math::

            v = \frac{c V}{C}

        Note that the stock concentration of the reagent and the volume of the 
        whole reaction must already be specified in order for the volume to be 
        set in this manner.
        """

        def __init__(self, reagent):
            self.reagent = reagent

        def get_volume(self):
            return self.reagent.volume

        def set_volume(self, volume):
            self.reagent.volume = Quantity.from_anything(volume)

        def get_conc(self):
            return self.reagent.conc

        def set_conc(self, conc):
            self.reagent.require_stock_conc()
            self.reagent.reaction.require_volume()

            c = Quantity.from_anything(conc)
            v_rxn = self.reagent.reaction.volume
            s = self.reagent.stock_conc

            self.reagent.volume = v_rxn * (c / s)

@autoprop
class Solvent:

    def __init__(self, reaction):
        self._reaction = reaction
        self._name = None
        self._stock_conc = None
        self.master_mix = True
        self.order = None

    def __repr__(self):
        reaction_id = str(id(self._reaction))[-4:]
        return f'Solvent(reaction={reaction_id}, name={self.name!r})'

    def get_key(self):
        return self._reaction.solvent

    def set_key(self, key):
        self._reaction.solvent = key

    def get_name(self):
        return self._name or self.key

    def set_name(self, name):
        self._name = name

    def get_volume(self):
        return self._reaction.free_volume

    def set_volume(self, volume):
        raise NotImplementedError("cannot directly set solvent volume, set the reaction volume instead.")

    def get_stock_conc(self):
        return self._stock_conc

    def set_stock_conc(self, stock_conc):
        self._stock_conc = Quantity.from_anything(stock_conc)

    def require_volume(self):
        self._reaction.require_volume()

