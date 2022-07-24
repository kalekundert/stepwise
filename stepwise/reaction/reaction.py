import re
import autoprop
import byoc

from copy import deepcopy
from inform import plural, warn
from more_itertools import one, only, always_iterable
from reprfunc import ReprBuilder, repr_from_init
from dataclasses import dataclass
from contextlib import contextmanager
from abc import ABC, abstractmethod

from ..quantity import Quantity
from ..format import table
from ..errors import *

@autoprop
class Reaction:

    def __init__(self):
        self._reagents = []
        self._key_map = {}
        self._volume = None
        self._solvent = None

    def __repr__(self):
        builder = ReprBuilder(self)
        for reagent in self:
            builder.add_positional_value(reagent)

        if self.solvent and self.volume:
            builder.add_keyword_attr('volume')

        return str(builder)

    def __eq__(self, other):
        """
        Determine if two reaction call for the same amount of the same reagents in 
        the same order.
        """
        if not isinstance(other, Reaction):
            return NotImplemented

        return list(self) == list(other)

    def __iter__(self):
        yield from self._reagents

    def __contains__(self, key):
        return key in self._key_map

    def __len__(self):
        return len(self._reagents)

    def __getitem__(self, key):
        if key not in self._key_map:
            self.append_reagent(key)

        return self._reagents[self._key_map[key]]

    def __setitem__(self, key, reagent):
        if key in self._key_map:
            if self._reagents[self._key_map[key]] is reagent:
                return

        if isinstance(reagent, Solvent):
            if self._solvent is not None and self._solvent != key:
                raise UsageError(f"cannot make {key!r} the solvent; {self._solvent!r} is already the solvent")

        # I can't imagine this conditional being False in a non-contrived use 
        # case, but I include it anyways for good measure.
        if reagent.reaction is not None:
            memo = {id(reagent._reaction): None}
            reagent = deepcopy(reagent, memo)

        reagent._reaction = self
        reagent._key = key

        if key in self._key_map:
            i = self._key_map[key]
            self._reagents[i]._detach()
            self._reagents[i] = reagent

            if not isinstance(reagent, Solvent) and key == self._solvent:
                self._solvent = None
                self._volume = None

        else:
            self._key_map[key] = len(self._reagents)
            self._reagents.append(reagent)

            if isinstance(reagent, Solvent):
                self._solvent = key

    def __delitem__(self, key):
        self.remove_reagent(key)

    @classmethod
    def from_text(cls, text):
        """
        Define a reaction using an ASCII-style table.

        Here is an example table for a ligation reaction::

            Reagent           Stock Conc    Volume  Master Mix  Flags
            ================  ==========  ========  ==========  =====
            water                          6.75 μL         yes
            T4 ligase buffer         10x   1.00 μL         yes
            T4 PNK               10 U/μL   0.25 μL         yes
            T4 DNA ligase       400 U/μL   0.25 μL         yes
            DpnI                 20 U/μL   0.25 μL         yes
            PCR product         50 ng/μL   1.50 μL

        The first three columns are required, the rest are optional.  The 
        column headers must exactly match the following:

        - "Reagent"
        - "Stock" or "Stock Conc"
        - "Volume"
        - "Conc", "Final", or "Final Conc"
        - "Master Mix" or "MM?"
        - "Flags"
        - "Catalog #" or "Cat"

        Extra columns will be ignored.  The columns are delineated by looking 
        for breaks of at least 2 spaces in the underline below the header.  
        Either '=' or '-' can be used for the underline.  The values in the 
        "Stock Conc", "Conc", and "Volume" columns must have units.  The values 
        in the "Master Mix" column must be either "yes", "no", "+", "-", or "" 
        (which means "no").
        """
        lines = text.rstrip().splitlines()

        if lines and not lines[0]:
            lines = lines[1:]

        if len(lines) < 3:
            raise UsageError(f"reagent table has {plural(lines):# line/s}, but needs at least 3 (i.e. header, underline, first reagent).")
        if not re.fullmatch(r'[-=\s]+', lines[1]):
            raise UsageError(f"the 2nd line of the reagent table must be an underline (e.g. '===' or '---'), not {lines[1]!r}.")

        column_slices = [
                slice(x.start(), x.end())
                for x in re.finditer(r'[-=]+', lines[1])
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
    def from_df(cls, df):
        cols = df.fillna('').to_dict('list')
        return cls.from_cols(cols)

    @classmethod
    def from_rows(cls, rows):
        keys = set()
        for row in rows:
            keys.update(row)

        cols = {k: [] for k in keys}

        for row in rows:
            for k in keys:
                cols[k].append(row.get(k))

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
        - "Catalog #" or "Cat"
        - "Flags"

        The values in the "Reagent" and "Catalog #" columns must be strings.  
        The values in the "Stock Conc" and "Volume" columns must be strings 
        containing a number and a unit, i.e. compatible with 
        `Quantity.from_string()`.  The values in the "Master Mix" column can be 
        either booleans or the strings "yes", "y", "no", or "n".  The values in 
        the "Flags" column should be a comma-separated list of keywords.
        """

        # TODO: specify concentrations
        # - Need at least one volume.
        # - If "to xx µL", use that as total volume
        # - Otherwise, add up all volumes and solve algebra

        # Use consistent column names:

        column_aliases = {
                'key': {
                    'Key',
                },
                'reagent': {
                    'Reagent',
                },
                'stock_conc': {
                    'Stock Conc',
                    'Stock',
                },
                'conc': {
                    'Final Conc',
                    'Final',
                    'Conc',
                },
                'name': {
                    'Name',
                    'Alias',
                },
                'volume': {
                    'Volume',
                },
                'master_mix': {
                    'Master Mix',
                    'MM?',
                },
                'catalog_num': {
                    'Catalog #',
                    'Catalog',
                    'Cat',
                },
                'flags': {
                    'Flags',
                },
        }
        given_keys = set(cols.keys())

        for k_std, aliases in column_aliases.items():
            aliases |= {x.lower() for x in aliases}
            aliases.add(k_std)
            k_given = only(
                    (k_match := aliases & given_keys),
                    too_long=UsageError(f"multiple {k_std!r} columns found: {', '.join(repr(x) for x in sorted(k_match))}"),
            )
            if k_given:
                cols[k_std] = cols.pop(k_given)

        # Strip whitespace:

        def strip_if_str(x):
            return x.strip() if isinstance(x, str) else x

        cols = {
                k: [strip_if_str(x) for x in v]
                for k, v in cols.items()
        }

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
        required_column('volume')

        num_rows = one(
                x := {len(v) for v in cols.values()},
                too_short=AssertionError,
                too_long=UsageError(f"columns have different numbers of rows: {', '.join(map(str, x))}"),
        )
        if num_rows == 0:
            raise UsageError("reaction must have at least one reagent")

        def optional_column(key, default=''):
            if key not in cols:
                cols[key] = num_rows * [default]
        
        optional_column('key')
        optional_column('stock_conc')
        optional_column('conc')
        optional_column('name')
        optional_column('master_mix', 'y')
        optional_column('catalog_num')
        optional_column('flags')

        if not all(cols['reagent']):
            raise UsageError("some reagents are missing names")

        # Configure the reaction:

        rxn = cls()

        def parse_bool(x):
            if x in ('yes', 'y', 'x', '+', 1):
                return True
            if x in ('no', 'n', '', '-', '−', 0):
                return False
            raise UsageError(f"expected 'yes' or 'no', got '{x}'")

        def parse_comma_set(x):
            return set(x.split(',') if x else [])

        conc_rows = []
        has_solvent = False

        for i in range(num_rows):
            key = cols['reagent'][i]
            volume = cols['volume'][i]

            if volume:
                rxn[key].volume = volume

            # Don't save a reference to the reagent object before trying to set 
            # the volume, because doing so might cause the reaction to discard 
            # that object and replace it with a solvent.
            reagent = rxn[key]
            reagent.flags = parse_comma_set(cols['flags'][i])
            reagent.master_mix = parse_bool(cols['master_mix'][i])

            if (x := cols['key'][i]):
                reagent.key = x
                key = x

            if (x := cols['name'][i]):
                reagent.name = x

            if (x := cols['catalog_num'][i]):
                reagent.catalog_num = x

            if key == rxn.solvent:
                if (x := cols['stock_conc'][i]):
                    raise UsageError(f"cannot specify a stock concentration ({x!r}) for the solvent ({rxn.solvent!r})")

                if (x := cols['conc'][i]):
                    raise UsageError(f"cannot specify a concentration ({x!r}) for the solvent ({rxn.solvent!r})")

            else:
                if (x := cols['stock_conc'][i]):
                    reagent.stock_conc = x

                conc = cols['conc'][i]

                if volume and conc:
                    raise UsageError(f"cannot specify volume ({volume!r}) and concentration ({conc!r}) for {key!r}")
                elif volume:
                    pass
                elif conc:
                    conc_rows.append((reagent, conc))
                else:
                    raise UsageError(f"must specify either volume or concentration for {key!r}")

        # Convert concentrations to volumes in a second pass.

        if rxn.solvent:
            for reagent, conc in conc_rows:
                reagent.hold_stock_conc.conc = conc
        else:
            known_volumes = [x.volume or 0 for x in rxn]
            if not known_volumes:
                raise UsageError("must specify at least one volume")

            dilution_factors = []
            for reagent, conc in conc_rows:
                reagent.require_stock_conc()
                dilution_factors.append(conc / reagent.stock_conc)

            coeff = 1 - sum(dilution_factors)
            v = sum(known_volumes) / coeff

            for (reagent, _), factor in zip(conc_rows, dilution_factors):
                reagent.volume = v * factor

        return rxn

    def keys(self):
        return [x.key for x in self]

    def copy(self):
        return deepcopy(self)

    def append_reagent(self, key):
        self.insert_reagent(key, len(self))

    def prepend_reagent(self, key):
        self.insert_reagent(key, 0)

    def insert_reagent(self, key, loc):
        if key in self._key_map:
            raise UsageError(f"{key!r} is already a reagent")

        reagent = Reagent(self, key)
        i = self._index_from_loc(loc)
        self._reagents.insert(i, reagent)
        self._refresh_key_map()

    def reorder_reagent(self, key, loc):
        self.require_reagent(key)

        i = self._key_map[key]
        j = self._index_from_loc(loc)

        reagent = self._reagents.pop(i)
        self._reagents.insert(j, reagent)
        self._refresh_key_map()

    def remove_reagent(self, key):
        self.pop_reagent(key)

    def pop_reagent(self, key):
        self.require_reagent(key)

        i = self._key_map[key]
        reagent = self._reagents[i]
        reagent._detach()

        if key == self._solvent:
            self._solvent = None
            self._volume = None

        del self._key_map[key]
        del self._reagents[i]

        self._refresh_key_map()

        return reagent
    
    def iter_nonzero_reagents(self, precision=2):
        yield from (x for x in self if not x.is_empty(precision))

    def iter_nonsolvent_reagents(self):
        for reagent in self:
            if reagent.key != self._solvent:
                yield reagent

    def iter_reagents_by_flag(self, flag):
        for reagent in self:
            if flag in reagent.flags:
                yield reagent

    def by_order(self, key):
        return self._key_map[key]

    def get_solvent(self):
        return self._solvent

    def get_volume(self):
        if self._solvent and not self[self._solvent].is_held:
            return self._volume

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

        for reagent in self.iter_nonsolvent_reagents():
            if reagent.key not in keys:
                reagent.require_volume()
                v -= reagent.volume

        return v

    def repair_volumes(self, donor, acceptor=None):
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

    @property
    def hold_ratios(self):
        return self._HoldRatios(self)

    @contextmanager
    def hold_solvent_volume(self):
        """
        Prevent the volume of the solvent from changing as other reagents are 
        added/removed/updated.
        """
        if not self._solvent:
            yield
            return

        solvent = self[self._solvent]

        if solvent.is_held:
            yield
            return

        try:
            solvent.hold_volume()
            yield
        finally:
            if solvent.is_held:
                solvent.release_volume()

    def require_reagent(self, key):
        if key not in self._key_map:
            raise ValueError(f"no {key!r} reagent in the reaction")

    def require_volume(self):
        if self._solvent and not self[self._solvent].is_held and self._volume is None:
            raise ValueError(f"no reaction volume specified")

    def require_volumes(self):
        self.require_volume()
        for reagent in self.iter_nonsolvent_reagents():
            reagent.require_volume()

    def require_solvent(self):
        if self._solvent is None:
            raise ValueError(f"no solvent specified")

    def _refresh_key_map(self):
        self._key_map = {
                reagent.key: i
                for i, reagent in enumerate(self._reagents)
        }

    def _index_from_loc(self, loc):
        if callable(loc):
            return loc(self._key_map, self._reagents, solvent=self._solvent)
        else:
            return loc


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
class BaseReagent(ABC):

    def __init__(self, reaction):
        self._reaction = reaction
        self._name = None

        # Subclasses are expected to define `self._key` as either an attribute 
        # or a property.  It's not defined here because solvents can look this 
        # information up in the reaction; they don't need an attribute to store 
        # it in.

        self.flags = set()
        self.catalog_num = None

    def __eq__(self, other):
        """
        Determine if two reagents represent the same amount of the same 
        material.

        Reagents can be considered equivalent despite being very different 
        internally.  For example, a solvent can be equal to a non-solvent so 
        long as both have the same volume.  Reagents with different keys but 
        the same name can be equal.  Flags are not considered when checking for 
        equality.
        """
        if not isinstance(other, BaseReagent):
            return NotImplemented
        return (
                self.name == other.name and
                self.catalog_num == other.catalog_num and
                self.volume_or_none == other.volume_or_none and
                self.stock_conc == other.stock_conc
        )

    def get_reaction(self):
        return self._reaction

    def get_key(self):
        return self._key

    def set_key(self, key):
        if key in self._reaction._key_map:
            raise UsageError(f"cannot change {self._key!r} key to {key!r}; new key already in use")

        i = self._reaction._key_map.pop(self._key)
        self._reaction._key_map[key] = i

        if self._name is None:
            self._name = self._key

        self._key = key

    def get_name(self):
        return self._name or self.key

    def set_name(self, name):
        self._name = name

    @abstractmethod
    def get_volume(self):
        raise NotImplementedError

    def get_volume_or_none(self):
        try:
            return self.volume
        except (ValueError, NotImplementedError):
            return None

    def get_conc(self):
        raise NotImplementedError

    def get_conc_or_none(self):
        try:
            return self.conc
        except (ValueError, NotImplementedError):
            return None

    def get_stock_conc(self):
        return None

    def is_solvent(self):
        return False

    def is_empty(self, precision=2):
        self.require_volume()
        return rounds_to_zero(self.volume.value, precision)

    def require_volume(self):
        if self.volume is None:
            raise ValueError(f"no volume specified for {self.name!r}")

    def require_stock_conc(self):
        if self.stock_conc is None:
            raise ValueError(f"no stock concentration specified for '{self.name}'")
        if not isinstance(self.stock_conc, Quantity):
            raise ValueError(f"stock concentration specified for '{self.name}' cannot be interpreted as a value with a unit")

    def _detach(self):
        self._reaction = None

@autoprop
class Reagent(BaseReagent):

    def __init__(self, reaction, key):
        super().__init__(reaction)

        # When adding or removing attributes from this class, be sure to update 
        # the code in `set_as_solvent()` that copies attributes into a new 
        # `Solvent` instance.

        self._key = key
        self._volume = None
        self._stock_conc = None

        self.master_mix = False

    def __repr__(self):
        builder = ReprBuilder(self)
        builder.add_positional_value(self.key)

        if self._name:
            builder.add_keyword_attr('name')
        if self._volume:
            builder.add_keyword_attr('volume')
        if self._stock_conc:
            builder.add_keyword_attr('stock_conc')
        if self.flags:
            builder.add_keyword_attr('flags')
        if self.catalog_num:
            builder.add_keyword_attr('catalog_num')

        return str(builder)

    def set_as_solvent(self):
        if self.reaction.solvent:
            raise UsageError(f"cannot set {self.key!r} as solvent; {self._reaction.solvent!r} is already the solvent")
        if self.volume is not None:
            raise UsageError(f"{self.key!r} has a volume ({self.volume}); cannot set as solvent")
        if self.stock_conc is not None:
            raise UsageError(f"{self.key!r} has a stock concentration ({self.stock_conc}); cannot set as solvent")

        # Prepare to copy any attributes that aren't specific to the Reagent 
        # class.  It's ok that we're using a shallow copy here, because this 
        # Reagent instance won't be used for anything after this method 
        # completes.
        copy_attrs = self.__dict__.copy()
        del copy_attrs['_key']
        del copy_attrs['_volume']
        del copy_attrs['_stock_conc']
        del copy_attrs['master_mix']

        solvent = Solvent(self)
        solvent.__dict__.update(copy_attrs)

        self.reaction[self.key] = solvent

    def get_volume(self):
        return self._volume

    def set_volume(self, volume):
        volume = parse_volume(volume)

        if isinstance(volume, To):
            rxn = self._reaction
            self.set_as_solvent()
            rxn._volume = Quantity.from_anything(volume.quantity)
        else:
            self._volume = Quantity.from_anything(volume)

    def del_volume(self, volume):
        self._volume = None

    def get_conc(self):
        self.require_volume()
        self.require_stock_conc()
        self.reaction.require_volume()

        ratio = self._volume / self.reaction.volume
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
class Solvent(BaseReagent):

    def __init__(self, reaction):
        super().__init__(reaction)
        self._volume = None
        self.master_mix = True

    def __repr__(self):
        builder = ReprBuilder(self)

        if self._reaction:
            builder.add_positional_value(self.key)
        if self._name:
            builder.add_keyword_attr('name')
        if self.flags:
            builder.add_keyword_attr('flags')
        if self.catalog_num:
            builder.add_keyword_attr('catalog_num')

        return str(builder)

    def _get_key(self):
        return self.reaction._solvent

    def _set_key(self, key):
        self.reaction._solvent = key

    def get_volume(self):
        if self._volume is not None:
            return self._volume 
        else:
            return self.reaction.free_volume

    def set_volume(self, volume):
        raise NotImplementedError("cannot directly set solvent volume; set the reaction volume instead")

    def get_conc(self):
        raise NotImplementedError("solvents do not have concentrations")

    def hold_volume(self):
        self._volume = self.reaction.free_volume
        self.reaction._volume = None

    def release_volume(self):
        self.reaction._volume = self.reaction.volume
        self._volume = None

    def is_solvent(self):
        return True

    @property
    def is_held(self):
        return self._volume is not None

    def require_volume(self):
        if not self.is_held:
            self.reaction.require_volume()

    def _detach(self):
        if self.is_held:
            self.release_volume()
        super()._detach()

@dataclass
class To:
    quantity: str

def format_reaction(rxn, *, scale=1, show_1x=True, show_stocks=None, show_concs=None, show_totals=None):
    # Leave out reagents that round to 0 volume.
    reagents = list(rxn.iter_nonzero_reagents())

    scales = sorted(always_iterable(scale))
    if 1 not in scales:
        scales = [1, *scales]

    if show_stocks is None:
        show_stocks = any(x.stock_conc for x in reagents)
    if show_totals is None:
        show_totals = len(rxn) > 1

    def cols(*cols):
        """
        Eliminate columns the user doesn't want to see.
        """
        cols = list(cols)

        if not show_1x:
            del cols[3]
        if not show_concs:
            del cols[2]
        if not show_stocks:
            del cols[1]

        return [str(x) for x in cols]

    def volume_headers():
        for scale in scales:
            if scale == 1:
                yield quantity_header()
            else:
                yield scale_header(scale)

    def volume_rows(volume):
        for scale in scales:
            yield format_volume(scale * volume)

    def quantity_header():
        # This is a bit of a quick-fix; the reaction framework pretty much 
        # assumes that each reagent has a volume/concentration at the 
        # moment, so solid reagents don't fit in really well.
        # 
        # Checking that the unit ends with an 'L' is also not a good way to 
        # know if something is a volume or not.  It'd be better to have a 
        # database of units, each annotated with type, prefix, etc.
        all_volume = all(
                x.volume.unit.endswith('L')
                for x in reagents
        )
        return "Volume" if all_volume else "Quantity"

    def scale_header(scale):
        strip_0 = lambda x: x.rstrip('0').rstrip('.')
        scale_str_1 = strip_0(f"{scale:.1f}")
        scale_str_5 = strip_0(f"{scale:.5f}")
        prefix = '' if scale_str_1 == scale_str_5 else '≈'
        return f'{prefix}{scale_str_1}x'

    def format_volume(v):
        # This is a hack to deal with tables that have different volume 
        # unit scale factors.  It would be better to make the unit handling 
        # more powerful.
        if v.value > 2000 and v.unit in ('uL', 'µL'):
            v = Quantity(v.value / 1000, 'mL')
        return f'{v:.2f}'

    # Figure out how big the table should be.

    header = cols(
            "Reagent",
            "Stock",
            "Final",
            *volume_headers(),
    )
    rows = [
            cols(
                x.name,
                x.stock_conc or '',
                x.conc_or_none or '',
                *volume_rows(x.volume),
            )
            for x in reagents
    ]
    footer = None if not show_totals else cols(
            '',
            '',
            '',
            *volume_rows(rxn.volume),
    )
    align = cols(*('<>>' + '>' * len(scales)))

    return table(
            rows=rows,
            header=header,
            footer=footer,
            align=align,
    )

def parse_volume(v):
    if isinstance(v, str):
        if v.startswith('to '):
            return To(Quantity.from_string(v[3:]))
        else:
            return Quantity.from_string(v)
    else:
        return v

def rounds_to_zero(x, precision=2):
    return f'{abs(x):.{precision}f}' == f'{0:.{precision}f}'

class before:

    def __init__(self, *keys):
        self.keys = keys

    def __call__(self, key_map, reagents, **kwargs):
        return min(key_map[k] for k in self.keys)

    __repr__ = repr_from_init

class after:

    def __init__(self, *keys):
        self.keys = keys

    def __call__(self, key_map, reagents, **kwargs):
        return max(key_map[k] for k in self.keys) + 1

    __repr__ = repr_from_init
