#!/usr/bin/env python3

import autoprop

from math import inf
from copy import deepcopy

from . import Reaction
from ..quantity import Quantity
from ..format import table, tabulate, preformatted
from ..errors import *

@autoprop
class MasterMix:
    # This class is deprecated by `Reactions`.  I'm going to get rid of it once 
    # I finish transitioning all of my scripts.

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
        self.show_concs = False
        self.show_master_mix = None
        self.show_totals = True

    def __repr__(self):
        return self.reaction.__repr__.__func__(self)

    def __str__(self):
        return self.format_text()

    def __iter__(self):
        return self.reaction.__iter__()

    def __contains__(self, key):
        return self.reaction.__contains__(key)

    def __len__(self):
        return self.reaction.__len__()

    def __getitem__(self, key):
        return self.reaction.__getitem__(key)

    def __setitem__(self, key, value):
        return self.reaction.__setitem__(key, value)

    def __delitem__(self, key):
        return self.reaction.__delitem__(key)

    def __getattr__(self, attr):
        # Note that `__getattr__()` isn't used to lookup dunder methods, so 
        # methods like `__getitem__()` need to be explicitly defined.  See 
        # Section 3.3.10 of the python docs.

        # Due to the way `autoprop` does caching, this method is called by 
        # `__setattr__()` when the `reaction` attribute is being set for the 
        # first time.  This means we have to be careful about accessing 
        # `reaction`, because the normal `self.reaction` syntax would trigger 
        # infinite recursion in this case.

        try:
            reaction = self.__dict__['reaction']
        except KeyError:
            raise AttributeError

        try:
            return getattr(reaction, attr)
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

    def copy(self):
        return deepcopy(self)

    def iter_master_mix_reagents(self):
        yield from (
                x for x in self.iter_nonzero_reagents()
                if x.master_mix
        )

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

    def format_text(self, width=inf, **kwargs):
        # Leave out reagents that round to 0 volume.
        reagents = list(self.iter_nonzero_reagents())
        show_master_mix = not any([
                # Nothing in the master mix:
                sum(x.master_mix for x in reagents) <= 1,

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
                del cols[4]
            if not self.show_1x:
                del cols[3]
            if not self.show_concs:
                del cols[2]

            return cols

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

        def scale_header():
            strip_0 = lambda x: x.rstrip('0').rstrip('.')
            scale_str_1 = strip_0(f"{self.scale:.1f}")
            scale_str_5 = strip_0(f"{self.scale:.5f}")
            prefix = '' if scale_str_1 == scale_str_5 else '≈'
            return f'{prefix}{scale_str_1}x'

        # Figure out how big the table should be.

        def format_volume(v):
            # This is a hack to deal with tables that have different volume 
            # unit scale factors.  It would be better to make the unit handling 
            # more powerful.
            if v.value > 1000 and v.unit in ('uL', 'µL'):
                v = Quantity(v.value / 1000, 'mL')
            return f'{v:.2f}'

        header = cols(
                "Reagent",
                "Stock",
                "Final",
                quantity_header(),
                scale_header(),
        )
        rows = [
                cols(
                    x.name,
                    x.stock_conc or '',
                    x.conc_or_none or '',
                    format_volume(x.volume),
                    format_volume(x.volume * self.scale) if x.master_mix else '',
                )
                for x in reagents
        ]
        footer = None if not self.show_totals else cols(
                '',
                '',
                '',
                format_volume(self.volume),
                format_volume(self.master_mix_volume),
        )
        align = cols(*'<>>>>')

        table = tabulate(rows, header, footer, align=align)

        if show_master_mix and self.show_totals:
            table += '/rxn'

        return preformatted(table).format_text(width, **kwargs)

    def replace_text(self, pattern, repl, **kwargs):
        from ..format import replace_text
        # Only make substitutions in the reagent names.
        for reagent in self:
            reagent.name = replace_text(reagent.name, pattern, repl, **kwargs)


