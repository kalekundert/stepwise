#!/usr/bin/env python3

import sys
import re
import math
import autoprop
import byoc
import functools
import networkx as nx

from byoc import Key, DocoptConfig, float_eval
from math import inf
from pathlib import Path
from copy import deepcopy
from inform import plural, warn
from itertools import groupby, permutations
from more_itertools import one, only, flatten, pairwise, zip_equal
from reprfunc import repr_from_init
from operator import itemgetter
from collections import Counter
from dataclasses import dataclass
from .quantity import Quantity
from .format import  pl, ul, dl, table, tabulate, preformatted
from .config import StepwiseConfig
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

# Reactions TODO:
# - Replicates?  Handled well?

def reaction_from_docopt(args):
    reagent_strs = args['<reagent;stock;conc;volume>']
    cols = {
            'reagent': [],
            'stock_conc': [],
            'conc': [],
            'volume': [],
    }
    for reagent_str in reagent_strs:
        fields = reagent_str.split(';')
        if len(fields) != 4:
            raise UsageError(f"expected 4 semicolon-separated fields, not {len(fields)}: {reagent_str}")

        reagent, stock_conc, conc, volume = fields

        cols['reagent'].append(reagent)
        cols['stock_conc'].append(stock_conc)
        cols['conc'].append(conc)
        cols['volume'].append(volume)

    rxn = Reaction.from_cols(cols)

    if '--volume' in args:
        rxn.hold_ratios.volume = float_eval(args['--volume']), rxn.volume.unit

    return rxn

def combos_from_docopt(args):

    def parse_combo(combo_str, header=None):
        if not combo_str:
            return []

        combo = combo_str.split(',')

        if header and len(combo) != len(header):
            raise UsageError(f"expected {len(header)} reagents, not {len(combo)}: {combo_str}")

        return combo

    header = parse_combo(args.get('--combo-reagents', ''))
    rows = [parse_combo(x, header) for x in args.get('--combo', '')]

    if header and not rows:
        raise UsageError("specified combo reagents (`-C`), but no combos (`-c`)")

    return [
            dict(zip(header, row))
            for row in rows
    ]

def mixes_from_strs(mix_strs):
    return [
            Reactions.Mix(x.split(','))
            for x in mix_strs
    ]

def extra_from_docopt(args):
    key_map = {
            '--extra-fraction': 'fraction',
            '--extra-percent': 'percent',
            '--extra-reactions': 'reactions',
            '--extra-volume': 'volume',
            '--extra-min-volume': 'min_volume',
    }

    kwargs = {}
    for k1, k2 in key_map.items():
        try:
            kwargs[k2] = float(args[k1])
        except KeyError:
            pass

    if not kwargs:
        raise KeyError("no --extra-* arguments specified")

    return Extra(**kwargs)

def extra_from_dict(tolerances):
    return Extra(**tolerances)

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
        from .format import replace_text
        # Only make substitutions in the reagent names.
        for reagent in self:
            reagent.name = replace_text(reagent.name, pattern, repl, **kwargs)


@autoprop.cache
class Reactions(byoc.App):
    """
    Setup multiple variants of the given reaction using one or more master 
    mixes.

    Arguments:
        reaction:
          A single reaction containing all of the reagents that will end up in 
          the final reactions.  Any reagents that should end up in a master mix 
          should have the 'master_mix' attribute True.
        
        combos:
          A list of dictionaries, where each dictionary maps names in the 
          reaction to names of the actual reagents to add.  For example, a PCR 
          master mix might have the following combo:
        
              {'template': 'p1', 'fwd': 'o1', 'rev': 'o2'}
        
          From this we can figure out which reagents need master mixes, and we 
          can display a nice table showing which combos to make.
        
        mixes: (optional)
          A list of objects specifying extra information about how to setup 
          each master mix.  This information would include:
        
          - What order to make the master mixes in (if there are more than 
            one).  This is inferred from the order of the list, not specified 
            directly.
          - How to refer to each master mix.
          - Which reagents should be added at each step.
        
          By default:
          - There will be a master mix for each reagent that isn't the same in 
            every combo
          - The order of the master mixes will be taken from the order of the 
            keys in the first combo.
          - Each master mix will be referred to using a name constructed from 
            the reagents added at that step.
        
        extra: (optional)
          A data structure specifying how much extra master mix to make for 
          each step.  You can also specify different extra parameters for each 
          master mix.  The value specified here will be used to any mixes that 
          don't have their own specification.
    """

    @autoprop
    class Mix:

        def __init__(self, reagents, *, name=None, extra=None):
            self.reagents = set(reagents)
            self._name = name
            self.extra = extra

            # Filled in by `Reactions.get_mixes()`:
            self.reaction = None
            self.num_reactions = None
            self.scale = None

        def get_name(self):
            return self._name or f"{'/'.join(self.reagents)}"

        def set_name(self, name):
            self._name = name

        __repr__ = repr_from_init(
                attrs={'name': '_name'},
                positional=['reagents'],
        )

    def __init__(self, reaction, combos, mixes=None, extra=None):
        self.base_reaction = reaction
        self.combos = combos
        if mixes: self._user_mixes = mixes
        if extra: self.extra = extra

    def main(self):
        byoc.load(self)
        self.protocol.print()

    def get_protocol(self):
        from .protocol import Protocol
        return Protocol(steps=[self.step])

    def get_step(self):
        step = pl()
        step += self.step_intro.format(
                n=plural(max(len(self.combos), 1)),
                kind=x if '/' in (x := self.step_kind) else f'{x} reaction/s',
        )

        if len(self.combos) < 2:
            rxn = self.base_reaction.copy()

            if self.combos:
                for k, v in self.combos[0].items():
                    rxn[k].name = v

            step += format_reaction(rxn, 1)

            if self.instructions:
                step += ul(*self.instructions)

            return step

        step += ul(br='\n\n')
        step[-1] += self.combo_step

        for i in range(len(self.mixes)):
            step[-1] += self.get_mix_step(i)

        if self.instructions:
            step += ul(*self.instructions)

        return step

    def get_combo_reagents(self):
        d = {}

        if self.combos:
            expected_keys = self.combos[0].keys()

        for combo in self.combos:
            if combo.keys() != expected_keys:
                raise ValueError

            for k, v in combo.items():
                reagents = d.setdefault(k, [])
                if v not in reagents:
                    reagents.append(v)

        return d

    def get_combo_reagents_in_order_of_appearance(self):
        mix_order = {}
        rxn_order = {}

        for i, reagent in enumerate(self.base_reaction):
            rxn_order[reagent.key] = i

        for j, mix in enumerate(self.mixes):
            for reagent in mix.reagents:
                mix_order[reagent] = j

        def by_appearance(reagent):
            return mix_order[reagent], rxn_order[reagent]

        assert mix_order.keys() == rxn_order.keys()
        return sorted(self.combo_reagents, key=by_appearance)

    def get_combo_step(self):
        if len(self.combo_reagents) == 1:
            return pl(
                    "Use the following reagents:",
                    self.all_combos_dl,
            )

        # There can be duplicate combos, so it is important to ignore those.
        as_tuple = itemgetter(*self.combo_reagents.keys())
        num_combos = len(set(map(as_tuple, self.combos)))
        num_possible_combos = math.prod(
                len(x)
                for x in self.combo_reagents.values()
        )

        if num_combos == num_possible_combos:
            return pl(
                    "Use all combinations of the following reagents:",
                    self.all_combos_dl,
            )

        else:
            return pl(
                    "Use the following combinations of reagents:",
                    self.combo_table,
            )

    def get_combo_table(self):
        reagents = self.combo_reagents_in_order_of_appearance
        rows = [
                [combo[k] for k in reagents]
                for combo in self.combos
        ]
        return table(
                rows=rows,
                header=reagents,
        )

    def get_all_combos_dl(self):
        return dl(*(
                (k, ', '.join(self.combo_reagents[k]))
                for k in self.combo_reagents_in_order_of_appearance
        ))
        
    @autoprop.cache(policy='manual')
    def get_mixes(self):
        if self._user_mixes:
            mixes = self._init_mixes_from_user()
        else:
            mixes = self._init_mixes_from_combos()

        self._add_missing_reagents(mixes)
        self._set_mix_reactions(mixes)
        self._set_mix_scales(mixes)

        return mixes

    def set_mixes(self, mixes):
        self._user_mixes = mixes
        autoprop.del_cached_attr(self, 'mixes')

    def get_mix_step(self, i):
        mix = self.mixes[i]
        n = mix.num_reactions

        table = format_reaction(mix.reaction, mix.scale, show_1x=True)

        if i + 1 == len(self.mixes):
            if i == 0:
                return pl("Mix the reactions:", table)
            else:
                return pl("Add the remaining reagents:", table)

        if n == 1:
            return pl(' '.join([f"Make {mix.name} mix:"]), table)

        return pl(' '.join([f"Make {n} {mix.name} mixes:"]), table)

    def _init_mixes_from_user(self):
        """
        Check that the mixes include all of the reagents being varied.
        """
        reagents = set()

        for mix in self._user_mixes:
            mix.reagents = set(mix.reagents)

            dups = reagents & mix.reagents
            if dups:
                raise UsageError(f"{', '.join(map(repr, dups))} included in multiple master mixes")

            reagents |= mix.reagents

        for reagent, values in self.combo_reagents.items():
            if reagent not in reagents and len(values) > 1:
                raise UsageError(f"{reagent!r} not included in any master mix.\nThe following reagents are included: {', '.join(map(repr, reagents))}")

        return self._user_mixes

    def _init_mixes_from_combos(self):
        """
        Infer a reasonable set of master mixes based on the requested reagent 
        combinations.
        """
        combos = drop_fixed_reagents(self.combos)
        graph = make_pipetting_graph(combos, self.master_mix_penalty)
        groups = minimize_pipetting(graph)
        return [self.Mix(x) for x in groups]

    def _add_missing_reagents(self, mixes):
        """
        Create an initial master mix containing any reagents that aren't 
        explicitly included in any of the given mixes.

        This method also asserts that (i) every mix includes at least one 
        reagent and (ii) every reagent being varied is present in one of the 
        given mixes.  The `_init_*()` methods are responsible for raising 
        helpful errors if either of these conditions are not met.
        """

        all_reagents = set(x.key for x in self.base_reaction)
        missing_reagents = all_reagents.copy()

        for mix in mixes:
            assert mix.reagents
            assert isinstance(mix.reagents, set)
            missing_reagents -= mix.reagents

        # Make sure that the mixes contain every reagent with multiple unique 
        # values.  This code is all crammed into one expression so that it will 
        # all be elided with optimizations enabled.
        assert (all_reagents - missing_reagents) >= set(
                k for k, v in self.combo_reagents.items()
                if len(v) > 1
        )

        n = len(missing_reagents)

        if n == 0:
            pass

        elif n == 1 and mixes:
            mixes[0].reagents |= missing_reagents

        else:
            mix = self.Mix(missing_reagents, name='master')
            mixes.insert(0, mix)

    @autoprop.ignore
    def _set_mix_reactions(self, mixes):
        """
        Create a reaction for each mix.  This process includes (i) copying the 
        reagents from the base reaction that are relevant to each step, (ii) 
        renaming reagents that don't vary, and (iii) adding references to 
        previous master mixes.
        """

        # Copy the base reaction and remove any reagents we don't want:

        for mix in mixes:
            mix.reaction = rxn = self.base_reaction.copy()
            rxn.pin_volumes()

            i = 1
            for reagent in rxn:
                key = reagent.key

                if key not in mix.reagents:
                    del rxn[key]
                else:
                    # Set the order so we can put the previous master mix in 
                    # front later on.
                    rxn[key].order = i; i += 1

                    try:
                        names = self.combo_reagents[key]
                    except KeyError:
                        pass
                    else:
                        if len(names) == 1:
                            rxn[key].name = names[0]

            rxn.unpin_volumes()

        # Add references to the previous master mixes:

        for prev, mix in pairwise(mixes):
            key = f'{prev.name} mix'
            mix.reaction[key].volume = prev.reaction.volume
            mix.reaction[key].order = 0

    @autoprop.ignore
    def _set_mix_scales(self, mixes):
        """
        Calculate (i) how many reactions to setup for each step and (ii) how 
        much to scale each reaction.

        Note that this method must be called after `_set_mix_reactions()`.
        """

        # Account for the combinations of reagents we need to make:

        cumulative_reagents = set()

        for mix in mixes:
            cumulative_reagents |= mix.reagents
            combo_counts = Counter(
                    tuple(combo.get(k) for k in cumulative_reagents)
                    for combo in self.combos
            )
            mix.num_reactions = len(combo_counts) or 1
            mix.scale = max(combo_counts.values(), default=1)

        # Account for the extra volume requested by the user:

        cumulative_factor = 1

        for mix in reversed(mixes[:-1]):
            extra = mix.extra or self.extra
            scale = extra.increase_scale(mix.scale, mix.reaction)
            cumulative_factor *= scale / mix.scale
            mix.scale *= cumulative_factor

    docopt_usage = """\
Setup one or more reactions.

Usage:
    reaction <reagent;stock;conc;volume>... [-C <reagents>] [-c <combo>]...
        [-m <reagents>]... [-M penalty] [-S <step>] [-s <kind>]
        [-i <instruction>]... [-v <volume>] [-x <percent>] [-X <volume>]
        [options]

Arguments:
    <reagent;stock;conc;volume>
        A description of one reagent in the reaction.  Each description must 
        consist of the fields listed above, separated by semi-colons. In 
        greater detail:

        name:
            The name of the reagent.  This can be any string, and will be 
            included verbatim in the reagent table.

        stock:
            The stock concentration of the reagent.  This is only required if a 
            final concentration (see below) is also specified.  

            This is optional , but if 
            specified, should include a unit.

        conc:
            The final concentration of the reagent.  

        volume:
            The volume of the reagent.  This can be specified in one of two 
            forms.  The first form is simply a value with a unit (e.g. '1 µL'), 
            in which case the reagent will have the specified volume.  The 
            second form is also a value with a unit, but prefixed by the string 
            "to" (e.g. 'to 10 µL').  In this case, the whole reaction will 
            have the specified volume, and the volume of the reagent itself 
            will be the difference between the total volume and the volumes of 
            all the other reagents.  Every reagent must have the same volume 
            unit.

        For each reagent, you must specify either (i) a volume or (ii) stock 
        and final concentrations.  If you specify a volume and a final 
        concentration, only the volume will be used.

Options:
    -C --combo-reagents <reagents>
        The names of the reagents to vary when setting up the reactions, 
        separated by commas.  Each reagent name must exactly match one of the 
        reagents specified by the <name;stock;conc;volume> arguments.  The 
        purpose of this option is to define the which reagents the `--combo` 
        arguments refer to.  In other words, if you think of the `--combo` 
        options are specifying rows of a table, this option would specify the 
        header.

    -c --combo <reagents>
        The names of the specific reagents to use for one variant of the 
        reaction in question, separated by commas.  Specify this option once 
        for each variant you want to set up.  The `--combo-reagents` option 
        determines the meaning of each field in this option.

    -m --mix <reagents>
        Which reagents to include in a particular master mix.  The purpose of 
        this option is to manually specify which master mixes to make (e.g. if 
        you aren't happy with the automatically determined master mixes).  
        Specify this option multiple times to make multiple master mixes.  
        Every reagent that's being varied (see `--combo-reagents`) must be 
        present in exactly one master mix.  Use commas to separate multiple 
        reagents in a single mix.

    -M --mix-penalty
        Set the penalty for creating master mixes.  To give some background, 
        this program determines whether or not to make master mixes by 
        calculating the number of pipetting steps that would be required to 
        setup the same reactions with or without.  A master mix is only made if 
        doing so would reduce this number.  This penalty is added to the number 
        of pipetting steps for the master mix case, effectively discouraging 
        the program from making master mixes unless they really help.  The 
        default penalty is 0.  Note that this option is ignored if `--mix` is 
        specified.

    -S --step <str>
        The text introducing the reaction.  "Setup {n:# reaction/s}:" is the 
        default.  This string will be formatted with a single parameter `n`, 
        which will be an `inform.plural()` object representing the number of 
        reactions to setup.

    -s --step-kind <str>
        The kind of reaction being setup.  This value will be included in the 
        text introducing the reaction.  For example, if given "PCR", the 
        reaction might be introduced as "Setup 1 PCR reaction" or "Setup 2 PCR 
        reactions" (depending on `--num-reactions`).

        If the given value contains one or more slashes, they will be used to 
        control pluralization.  See `inform.plural()` for details.  If the 
        given value doesn't contain a slash, it will be suffixed with 
        "reaction/s".  Note that this option cannot be used with `--step`, 
        because `--step` overwrites the text introducing the reaction.

    -i --instruction <str>
        An instruction on how to setup the reaction, e.g. to keep reagents on 
        ice, to use a certain type of tube, etc.  This option can be specified 
        multiple times, and each instruction will be included in a bullet-point 
        list below the reaction tables.

    -v --volume <expr>
        Scale the reaction to the given volume.  This volume is taken to be in 
        the same unit as all of the reagents.

    -x --extra-percent <float>
        How much extra master mix to make, as a percentage of the total master 
        mix volume.  The default is 10%.

    --extra-volume <float>
        How much extra master mix to make, given as a specific volume.  This 
        volume is taken to be in the same unit as all the reagents.

    --extra-reactions <float>
        How much extra master mix to make, given as a number of reactions. 

    -X --extra-min-volume <float>
        Scale the master mix such that every reagent has at least this volume.  
        This volume is taken to be in the same unit as all the reagents.

Configuration:
    Default values for this protocol can be specified in any of the following 
    stepwise configuration files:

        % for path in app.config_paths:
        ${path}
        %endfor

    reactions.mix_penalty
        See `--mix-penalty`.

    reactions.extra.percent
        See `--extra-percent`.

    reactions.extra.volume
        See `--extra-volume`.

    reactions.extra.reactions
        See `--extra-reactions`.

    reactions.extra.min_volume
        See `--extra-min-volume`.
"""
    usage_io = sys.stderr
    config_paths = byoc.config_attr()

    __config__ = [
            DocoptConfig.setup(usage_getter=lambda self: self.docopt_usage),
            StepwiseConfig.setup(root_key='reactions')
    ]
    base_reaction = byoc.param(
            Key(DocoptConfig, reaction_from_docopt),
    )
    combos = byoc.param(
            Key(DocoptConfig, combos_from_docopt),
    )
    _user_mixes = byoc.param(
            Key(DocoptConfig, '--mix', cast=mixes_from_strs),
            default=None,
    )
    step_intro = byoc.param(
            Key(DocoptConfig, '--step'),
            default="Setup {n:# {kind}}:",
    )
    step_kind = byoc.param(
            Key(DocoptConfig, '--step-kind'),
            default="reaction/s",
    )
    instructions = byoc.param(
            Key(DocoptConfig, '--instruction'),
            default_factory=list,
    )
    master_mix_penalty = byoc.param(
            Key(DocoptConfig, '--mix-penalty', cast=float),
            Key(StepwiseConfig, 'mix_penalty'),
            default=0,
    )
    extra = byoc.param(
            Key(DocoptConfig, extra_from_docopt),
            Key(StepwiseConfig, 'extra', cast=extra_from_dict),
            default_factory=lambda: Extra(percent=10),
    )

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

    def __eq__(self, other):
        return all((
            list(self) == list(other),
            self._volume == other._volume,
            self._solvent == other._solvent,
        ))

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
                    'Cat',
                },
                'flags': {
                    'Flags',
                },
        }
        given_keys = set(cols.keys())

        for k_std, aliases in column_aliases.items():
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
        del rxn.solvent

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
            is_solvent = cols['volume'][i].startswith('to')

            if is_solvent:
                has_solvent = True

                if rxn.solvent:
                    raise UsageError(f"multiple solvents specified: {rxn.solvent!r}, {cols['reagent'][i]!r}")

                # Have to set the solvent before adding the reagent, because 
                # reagents can't be turned into solvents.
                rxn.solvent = cols['reagent'][i]
                rxn.volume = cols['volume'][i][2:]

            reagent = rxn.add_reagent(cols['reagent'][i])
            reagent.master_mix = parse_bool(cols['master_mix'][i])
            reagent.flags = parse_comma_set(cols['flags'][i])

            if (x := cols['name'][i]):
                reagent.name = x

            if (x := cols['stock_conc'][i]):
                reagent.stock_conc = x

            if (x := cols['catalog_num'][i]):
                reagent.catalog_num = x

            if not is_solvent:
                volume_str = cols['volume'][i]
                conc_str = cols['conc'][i]


                if volume_str and conc_str:
                    raise UsageError(f"cannot specify volume ({volume_str!r}) and concentration ({conc_str!r}) for {reagent.name!r}")
                elif volume_str:
                    reagent.volume = cols['volume'][i]
                elif conc_str:
                    conc_rows.append((reagent, conc_str))
                else:
                    raise UsageError(f"must specify either volume or concentration for {reagent.name!r}")

        # Convert concentrations to volumes in a second pass.

        if has_solvent:
            for reagent, conc_str in conc_rows:
                reagent.hold_stock_conc.conc = conc_str

        else:
            known_volumes = [x.volume or 0 for x in rxn]
            if not known_volumes:
                raise UsageError("must specify at least one volume")

            dilution_factors = []
            for reagent, conc_str in conc_rows:
                reagent.require_stock_conc()
                dilution_factors.append(conc_str / reagent.stock_conc)

            coeff = 1 - sum(dilution_factors)
            v = sum(known_volumes) / coeff

            for (reagent, _), factor in zip(conc_rows, dilution_factors):
                reagent.volume = v * factor

        return rxn

    def copy(self):
        return deepcopy(self)

    def iter_reagents(self):
        # Yield the solvent before any of the other reagents, unless the 
        # solvent has been explicitly added to the reaction.
        if self._solvent is not None:
            if self._solvent not in self._reagents:
                yield Solvent(self)

        def by_order(x):
            order = math.inf if x.order is None else x.order
            return order < 0, order

        yield from sorted(
                self._reagents.values(),
                key=by_order,
        )

    def iter_nonzero_reagents(self, precision=2):
        yield from (x for x in self if not x.is_empty(precision))

    def iter_non_solvent_reagents(self):
        for reagent in self:
            if reagent.key != self._solvent:
                yield reagent

    def iter_reagents_by_flag(self, flag):
        for reagent in self:
            if flag in reagent.flags:
                yield reagent

    def get_volume(self):
        if self._solvent and not self[self._solvent].is_pinned:
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

    def copy_reagent(self, old_key, new_key):
        if old_key == self.solvent:
            raise UsageError("can't copy the solvent")
        if new_key in self:
            raise UsageError("can't overwrite existing reagent")

        memo = {id(self): self}
        new_reagent = deepcopy(self._reagents[old_key], memo)
        new_reagent._key = new_key
        self._reagents[new_key] = new_reagent

    @property
    def hold_ratios(self):
        return self._HoldRatios(self)

    def pin_volumes(self):
        """
        Prevent the volume of the solvent from changing as other reagents are 
        added/removed/updated.
        """
        if self._solvent:
            self._reagents[self._solvent].pin_volume()

    def unpin_volumes(self):
        if self._solvent:
            self._reagents[self._solvent].unpin_volume()

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
            raise ValueError(f"no {key!r} reagent in the reaction")

    def require_volume(self):
        if self._solvent and not self[self._solvent].is_pinned and self._volume is None:
            raise ValueError(f"no reaction volume specified")

    def require_volumes(self):
        self.require_volume()
        for reagent in self.iter_non_solvent_reagents():
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
        self.flags = set()
        self.catalog_num = None

    def __repr__(self):
        reaction_id = str(id(self._reaction))[-4:]
        return f'Reagent(reaction={reaction_id}, name={self.name!r})'

    def __eq__(self, other):
        # `Reaction.__eq__()` takes care of checking order.
        #
        # I don't check `master_mix` because it causes problems with the tests 
        # (python defaults are different than `from_cols()` defaults), and I'm 
        # planning to deprecate it anyway.
        return (
                isinstance(other, Reagent) and
                self._key == other._key and
                self._name == other._name and
                self._volume == other._volume and
                self._stock_conc == other._stock_conc and
                self.flags == other.flags and
                self.catalog_num == other.catalog_num
        )

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

    def is_empty(self, precision=2):
        self.require_volume()
        return rounds_to_zero(self.volume.value, precision)

    def get_conc(self):
        self.require_volume()
        self.require_stock_conc()
        self._reaction.require_volume()

        ratio = self._volume / self._reaction.volume
        return self._stock_conc * ratio

    def get_conc_or_none(self):
        try:
            return self.conc
        except ValueError:
            return None

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
        self._volume = None
        self.master_mix = True
        self.order = None
        self.flags = set()
        self.catalog_num = None

    def __repr__(self):
        reaction_id = str(id(self._reaction))[-4:]
        return f'Solvent(reaction={reaction_id}, name={self.name!r})'

    def __eq__(self, other):
        # `Reaction.__eq__()` takes care of checking order.
        return (
                isinstance(other, Solvent) and
                self._name == other._name and
                self._stock_conc == other._stock_conc and
                self.flags == other.flags and
                self.catalog_num == other.catalog_num
        )

    def get_key(self):
        return self._reaction.solvent

    def set_key(self, key):
        self._reaction.solvent = key

    def get_name(self):
        return self._name or self.key

    def set_name(self, name):
        self._name = name

    def get_volume(self):
        if self._volume is not None:
            return self._volume 
        else:
            return self._reaction.free_volume

    def set_volume(self, volume):
        raise NotImplementedError("cannot directly set solvent volume, set the reaction volume instead.")

    def pin_volume(self):
        self._volume = self._reaction.free_volume
        self._reaction._volume = None

    def unpin_volume(self):
        self._reaction._volume = self._reaction.volume
        self._volume = None

    def is_empty(self, precision=2):
        return rounds_to_zero(self.volume.value, precision)

    @property
    def is_pinned(self):
        return self._volume is not None

    def get_conc(self):
        raise ValueError("solvents cannot have concentrations")

    def get_conc_or_none(self):
        return None

    def get_stock_conc(self):
        return self._stock_conc

    def set_stock_conc(self, stock_conc):
        self._stock_conc = Quantity.from_anything(stock_conc)

    def require_volume(self):
        if not self.is_pinned:
            self._reaction.require_volume()

@autoprop
@dataclass
class Extra:
    fraction: float
    reactions: float
    volume: float
    min_volume: float

    def __init__(self, *, fraction=0, percent=None, reactions=0, volume=0, min_volume=0):
        self.fraction = fraction
        if percent is not None: self.percent = percent
        self.reactions = reactions
        self.volume = volume
        self.min_volume = min_volume

    def get_percent(self):
        return 100 * self.fraction

    def set_percent(self, percent):
        self.fraction = percent / 100

    def increase_scale(self, scale, rxn):
        min_volume = min((x.volume for x in rxn), default=None)
        return max((
            scale * (1 + self.fraction),
            scale + self.reactions,
            scale + self.volume / rxn.volume,
            self.min_volume / min_volume if min_volume else 0,
        ))

    __repr__ = repr_from_init(skip=['percent'])

def format_reaction(rxn, scale, *, show_1x=False, show_concs=False, show_totals=True):
    # This code is mostly copied from MasterMix right now.
    show_totals = show_totals and len(rxn) > 1

    # Leave out reagents that round to 0 volume.
    reagents = list(rxn.iter_nonzero_reagents())

    def cols(*cols):
        """
        Eliminate columns the user doesn't want to see.
        """
        cols = list(cols)

        if scale == 1:
            del cols[4]
        if scale != 1 and not show_1x:
            del cols[3]
        if not show_concs:
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
        scale_str_1 = strip_0(f"{scale:.1f}")
        scale_str_5 = strip_0(f"{scale:.5f}")
        prefix = '' if scale_str_1 == scale_str_5 else '≈'
        return f'{prefix}{scale_str_1}x'

    def format_volume(v):
        # This is a hack to deal with tables that have different volume 
        # unit scale factors.  It would be better to make the unit handling 
        # more powerful.
        if v.value > 1000 and v.unit in ('uL', 'µL'):
            v = Quantity(v.value / 1000, 'mL')
        return f'{v:.2f}'

    # Figure out how big the table should be.

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
                format_volume(x.volume * scale),
            )
            for x in reagents
    ]
    footer = None if not show_totals else cols(
            '',
            '',
            '',
            format_volume(rxn.volume),
            format_volume(rxn.volume * scale),
    )
    align = cols(*'<>>>>')

    return table(
            rows=rows,
            header=header,
            footer=footer,
            align=align,
    )

def drop_fixed_reagents(combos):
    """
    Remove any reagents that are the same in every combo.
    """
    if not combos:
        return []

    fixed = combos[0].copy()

    for combo in combos:
        for k in combo:
            if k in fixed and combo[k] != fixed[k]:
                del fixed[k]

    keys = [k for k in combos[0] if k not in fixed]

    if not keys:
        return []

    return [
            {k: combo[k] for k in keys}
            for combo in combos
    ]

def make_pipetting_graph(combos, split_penalty=0):
    """
    Create a graph where the nodes are reagents and the edge weights are the 
    number of pipetting steps required to created every desired combination of 
    those reagents.

    There are two ways to pipet each pair of reagents: either by merging the 
    reagents into a single master mix or splitting them into separate master 
    mixes.  Whichever requires fewer pipetting steps will be used.  Each edge 
    will also have a boolean "split" attribute indicating which approach was 
    used.

    Note that the edges are not symmetric.  In other words, the order in which 
    the reagents are added matters.
    """
    g = nx.DiGraph()

    if not combos:
        return g

    g.add_nodes_from(combos[0].keys())
    
    for a, b in permutations(g.nodes, 2):
        ab_combos = sorted(map(itemgetter(a, b), combos))

        merge_weight = 2 * len(list(groupby(ab_combos)))
        split_weight = split_penalty
        for _, group in groupby(ab_combos, key=itemgetter(0)):
            split_weight += 1 + len(list(groupby(group, key=itemgetter(1))))

        weight = min(merge_weight, split_weight)
        split = split_weight < merge_weight

        g.add_edge(a, b, weight=weight, split=split)

    return g
    
def minimize_pipetting(g):
    """
    Find the best order in which to mix the given reagents.

    This is a realization of the Traveling Salesman problem: we want the 
    lowest-weight path that includes every reagent exactly once.  I wrote a 
    simple brute-force implementation, because I don't anticipate ever having a 
    significant number of reagents, and I like that this brute-force algorithm 
    outputs its results in lexicographical order.  In other words, this 
    algorithm is O(N!), but I expect N<5 in almost all cases.

    After finding the best path, the algorithm also interprets the 
    splits/merges encoded in each edge, to group the reagents into master 
    mixes.
    """
    if not g:
        return []

    best_weight = inf
    best_tour = None

    def weights(g, tour):
        yield from (
                g.edges[a, b]['weight']
                for a, b in pairwise(tour)
        )

    for tour in permutations(g.nodes):
        weight = sum(weights(g, tour))

        if weight < best_weight:
            best_weight = weight
            best_tour = tour

    groups = [{best_tour[0]}]

    for a, b in pairwise(best_tour):
        if g.edges[a, b]['split']:
            groups.append(set())
        groups[-1].add(b)

    return groups

def rounds_to_zero(x, precision=2):
    return f'{abs(x):.{precision}f}' == f'{0:.{precision}f}'


