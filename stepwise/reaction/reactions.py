import sys
import math
import byoc
import autoprop
import networkx as nx

from byoc import Key, DocoptConfig, float_eval
from inform import plural
from itertools import groupby, permutations, repeat
from more_itertools import pairwise, repeat_last, unique_everseen as unique
from reprfunc import repr_from_init
from operator import itemgetter, not_
from collections import Counter
from dataclasses import dataclass
from math import inf

from .reaction import Reaction, format_reaction
from ..format import pl, ul, dl, table
from ..config import StepwiseConfig
from ..utils import unanimous, repr_join
from ..errors import *

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

        replicates:
            An integer specifying how many times to setup each combination of 
            reagents, e.g. to make technical replicates.  This parameter can 
            also be inferred from the given combos.
        
        mixes: (optional)
          A list of objects dictating how to setup each master mix.  This 
          information would include:
        
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
            self.name = name
            self.extra = extra

            # Filled in by `Reactions.get_mixes()`:
            self.reaction = None
            self.num_reactions = None
            self.scale = None

        __repr__ = repr_from_init(
                positional=['reagents'],
        )

    class AutoMix:

        def __init__(self, reagents, *, name=None, extra=None):
            self.reagents = set(reagents)
            self.name = name
            self.extra = extra

        def get_name(self, reagents):
            if callable(self.name):
                return self.name(reagents)
            else:
                return self.name

        def get_extra(self, reagents):
            if callable(self.extra):
                return self.extra(reagents)
            else:
                return self.extra

        __repr__ = repr_from_init(
                positional=['reagents'],
        )

    def __init__(self, reaction, combos=None, *, replicates=None, mixes=None, extra=None):
        self.base_reaction = reaction

        if combos: self._user_combos = combos
        if replicates: self._user_replicates = replicates
        if mixes: self._user_mixes = mixes
        if extra: self.extra = extra

    def main(self):
        byoc.load(self)
        self.protocol.print()

    def get_protocol(self):
        from ..protocol import Protocol
        return Protocol(steps=[self.step])

    def get_step(self):
        step = pl()

        n = len(self.combos)
        if self.split_replicates:
            n *= self.combos.replicates

        step += self.step_intro.format(
                n=plural(n),
                kind=x if '/' in (x := self.step_kind) else f'{x} reaction/s',
        )

        if len(self.mixes) == 1 and len(self.combos) < 2:
            step += self.get_mix_table(0)

        else:
            step += ul(br='\n\n')
            step[-1] += self.combo_step

            for i in range(len(self.mixes)):
                step[-1] += self.get_mix_step(i)

        if self.combos.replicates > 1 and self.split_replicates:
            step += ul(f"Split into {self.combos.replicates} identical {self.base_reaction.volume:.2f} reactions.")

        if self.instructions:
            step += ul(*self.instructions)

        return step

    def get_combos(self):
        combos = Combos(self._user_combos, self._user_replicates)
        combos.check_reagents(self.base_reaction)
        return combos

    def get_combo_step(self):
        self.combos.sort_by_appearance(self.mixes)

        if len(self.combos.distinct_cols) == 1:
            return pl(
                    "Use the following reagents:",
                    self.combos.format_as_dl(self.base_reaction),
            )

        if self.combos.have_all_possible_combos():
            return pl(
                    "Use all combinations of the following reagents:",
                    self.combos.format_as_dl(self.base_reaction),
            )

        return pl(
                "Use the following combinations of reagents:",
                self.combos.format_as_table(self.base_reaction),
        )

    @autoprop.cache(policy='manual')
    def get_unprocessed_mixes(self):
        if self._user_mixes:
            return self._init_mixes_from_user()
        else:
            return self._init_mixes_from_combos(self.combos)
    
    def set_unprocessed_mixes(self, mixes):
        self._user_mixes = mixes
        autoprop.del_cached_attr(self, 'unprocessed_mixes')
        autoprop.del_cached_attr(self, 'mixes')

    @autoprop.cache(policy='manual')
    def get_mixes(self):
        mixes = self.unprocessed_mixes

        self._add_missing_reagents(mixes)
        self._merge_trivial_mixes(mixes)
        self._set_mix_names(mixes)
        self._set_mix_reactions(mixes)
        self._set_mix_scales(mixes)

        # TODO: remove reagents with zero volume and recalculate mixes.

        return mixes

    def set_mixes(self, mixes):
        self._user_mixes = mixes
        autoprop.del_cached_attr(self, 'mixes')

    def get_mix_step(self, i):
        mix = self.mixes[i]
        n = mix.num_reactions
        table = self.get_mix_table(i)

        if i + 1 == len(self.mixes):
            if i == 0:
                return pl("Mix the reactions:", table)
            else:
                return pl("Add the remaining reagents:", table)

        if n == 1:
            return pl(' '.join([f"Make {mix.name} mix:"]), table)

        return pl(' '.join([f"Make {n} {mix.name} mixes:"]), table)

    def get_mix_table(self, i):
        mix = self.mixes[i]
        return format_reaction(mix.reaction, scale=mix.scale)

    def _init_mixes_from_user(self):
        """
        Check that the mixes include all of the reagents being varied.
        """

        mixes = []
        reagents = set()

        for mix in self._user_mixes:

            # Automatically calculate master mixes as requested:
            if isinstance(mix, self.AutoMix):
                keys = itemgetter(mix.reagents)
                combos = self.combos.select(mix.reagents)
                mixes += self._init_mixes_from_combos(combos)

            else:
                # Silently ignore mixes with no reagents.  I was on the fence 
                # about whether or not to make this an error.  On one hand, an 
                # empty mix has a pretty clear interpretation.  On the other, 
                # an empty mix could very well be indicative of a logic error.  
                # That said, I decided to allow it because I can imagine 
                # building a list of mixes in some automated way where it would 
                # be inconvenient to prune empty lists.
                if mix.reagents:
                    mixes.append(mix)

            # Check for duplicates:
            dups = reagents & mix.reagents
            if dups:
                raise UsageError(f"{', '.join(map(repr, dups))} included in multiple master mixes")
            reagents |= mix.reagents

        for reagent, values in self.combos.distinct_values_by_col.items():
            if reagent not in reagents:
                raise UsageError(f"{reagent!r} not included in any master mix.\nThe following reagents are included: {', '.join(map(repr, reagents))}")

        return mixes

    def _init_mixes_from_combos(self, combos):
        """
        Infer a reasonable set of master mixes based on the requested reagent 
        combinations.
        """
        combos = list(combos.select(combos.distinct_cols))
        ideal_order = [x.key for x in self.base_reaction]
        graph = make_pipetting_graph(combos, ideal_order, self.master_mix_penalty)
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

        if not missing_reagents:
            return

        # Verify that the mixes collectively contain every reagent with 
        # multiple unique values.  Note that the `_init*()` methods are 
        # actually responsible for making sure that this is the case; we're 
        # just double-checking here.
        assert (all_reagents - missing_reagents) >= self.combos.distinct_cols

        mix = self.Mix(missing_reagents)
        mixes.insert(0, mix)

    def _merge_trivial_mixes(self, mixes):
        # It doesn't make sense to setup a "master mix" with only a single 
        # reagent.  If this would happen, we can simply remove the mix in 
        # question and add its reagent in the next mix instead.
        # 
        # This is only a concern for the first mix.  Every other mix has at 
        # least two reagents: one for the previous mix, and one because it is 
        # an error for mixes to have no reagents of their own.  Only the first 
        # mix doesn't have a previous mix.

        if len(mixes[0].reagents) == 1 and len(mixes) > 1:
            mixes[1].reagents |= mixes[0].reagents
            del mixes[0]

    @autoprop.ignore
    def _set_mix_names(self, mixes):
        order_map = {x.key: i for i, x in enumerate(self.base_reaction)}
        by_order = lambda x: order_map[x]
        name_reagents = self.combos.distinct_cols

        for i, mix in enumerate(mixes):
            if mix.name:
                continue

            reagents = mix.reagents & name_reagents
            only_master_mix = (i == 0) and (len(mixes) == 2)

            if not reagents or only_master_mix:
                mix.name = 'master'
                continue

            mix.name = '/'.join(
                    self.base_reaction[k].name
                    for k in sorted(reagents, key=by_order)
            )

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

            for key in rxn.keys():
                if key not in mix.reagents:
                    with rxn.hold_solvent_volume():
                        del rxn[key]
                else:
                    try:
                        names = self.combos.unique_values_by_col[key]
                    except KeyError:
                        pass
                    else:
                        if len(names) == 1:
                            rxn[key].name = names[0]

        # Add references to the previous master mixes:

        for prev, mix in pairwise(mixes):
            key = f'{prev.name} mix'
            mix.reaction.prepend_reagent(key)
            mix.reaction[key].volume = prev.reaction.volume

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
            cumulative_reagents |= mix.reagents & self.combos.cols
            combo_counts = Counter(
                    self.combos.select_ordered_rows(cumulative_reagents)
            )
            mix.num_reactions = len(combo_counts) or 1
            mix.scale = max(combo_counts.values(), default=1) * \
                    self.combos.replicates

        # Account for the extra volume requested by the user:

        cumulative_factor = 1
        if self.last_mix_extra or (self.combos.replicates > 1):
            extra_defaults = repeat(self.extra)
        else:
            extra_defaults = repeat_last([Extra(), self.extra])

        for mix, extra_default in zip(reversed(mixes), extra_defaults):
            extra = mix.extra or extra_default
            scale = extra.increase_scale(mix.scale, mix.reaction)
            cumulative_factor *= scale / mix.scale
            mix.scale *= cumulative_factor

    docopt_usage = """\
Setup one or more reactions.

Usage:
    reaction <reagent;stock;conc;volume>... [-C <reagents>] [-c <combo>]...
        [-r <replicates>] [-v <volume>] [-m <reagents>]... [-M <penalty>]
        [-S <step>] [-s <kind>] [-i <instruction>]... [-x <percent>]
        [-X <volume>] [options]

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

    -r --replicates <int>
        Prepare the given number of technical replicates of each reaction.  You 
        can get the same behavior by specifying every combo multiple times, but 
        this option is more succinct.

    -v --volume <expr>
        Scale the reaction to the given volume.  This volume is taken to be in 
        the same unit as all of the reagents.

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

    --last-mix-extra
        Make extra of the final mix (i.e. the mix representing the 1x 
        reaction), in addition to all of the mixes leading up to it.  This is 
        useful if you plan on using these reactions as inputs to other 
        reactions, and don't want to run out of material.

    --no-split-replicates
        If multiple replicates are specified, skip the step where they are 
        split into separate but identical reactions.

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
    _user_combos = byoc.param(
            Key(DocoptConfig, combos_from_docopt),
            default_factory=list,
    )
    _user_replicates = byoc.param(
            Key(DocoptConfig, '--replicates', cast=int),
            default=1,
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
    split_replicates = byoc.param(
            Key(DocoptConfig, '--no-split-replicates', cast=not_),
            default=True,
    )
    last_mix_extra = byoc.param(
            Key(DocoptConfig, '--last-mix-extra'),
            default=False,
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

@autoprop.cache
class Combos:
    """
    A collection of reagent combinations to prepare via a series of master 
    mixes.

    You can think of this data structure as a table, where each column 
    corresponds to one reagent, and each row gives a different combination of 
    values for those reagents.  Typically, each column would also be a key in 
    the `Reaction` object used to build the master mixes.

    If every row in the tables is duplicated the same number of times, the 
    duplicates are removed and the number of duplicates is recorded in the 
    *replicate* attribute.
    """

    # This API feels too rigid to me.  It doesn't really matter, because the 
    # code works, but there's definitely some logic in the Reagents class that 
    # should be moved here.  I wonder if something like the following would be 
    # more powerful:
    #
    # iter_rows(self, replicates=False, order=None)
    # iter_cols(self, singleton=False)

    def __init__(self, combos, replicates=1):
        self._combos = combos
        self._replicates = replicates
        self._ordered_cols = None

        self._check_cols()
        self._infer_replicates()

    def __iter__(self):
        yield from self._combos

    def __len__(self):
        return max(len(self._combos), 1)

    def get_cols(self):
        return set(self._combos[0].keys()) if self._combos else set()

    def get_ordered_cols(self):
        assert self._ordered_cols is not None
        return self._ordered_cols

    def get_ordered_rows(self):
        assert self._ordered_cols is not None
        return self.select_ordered_rows(self.ordered_cols)

    def get_distinct_cols(self):
        return set(self.distinct_values_by_col)

    def get_values_by_col(self):
        values_by_col = {}

        for combo in self:
            for k, v in combo.items():
                values_by_col.setdefault(k, []).append(v)

        return values_by_col

    def get_unique_values_by_col(self):
        # Keep the values in the same order they were given in, to make for 
        # nice output.  This is why we don't use `set`, which would be simpler 
        # and more performant.
        return {k: list(unique(v)) for k, v in self.values_by_col.items()}

    def get_distinct_values_by_col(self):
        return {k: v for k, v in self.unique_values_by_col.items() if len(v) > 1}

    def get_replicates(self):
        return self._replicates

    def check_reagents(self, rxn):
        known_reagents = set(x.key for x in rxn)
        unknown_reagents = self.cols - known_reagents

        if unknown_reagents:
            raise UsageError(f"can't specify combos for reagents that aren't in the reaction\nreaction: {repr_join(rxn.keys())}\nunexpected: {repr_join(unknown_reagents)}")

    def select(self, cols):
        combos = [
                {k: combo[k] for k in cols}
                for combo in self
        ]
        return Combos(combos, self.replicates)

    def select_ordered_rows(self, ordered_cols):
        return [
                tuple(combo[k] for k in ordered_cols)
                for combo in self
        ]

    def sort_by_appearance(self, mixes):
        self._ordered_cols = []

        for mix in mixes:
            for reagent in mix.reaction:
                key = reagent.key
                if key in self.cols:
                    self._ordered_cols.append(key)

        assert set(self._ordered_cols) == self.cols
            
        try:
            del self.ordered_cols
            del self.ordered_rows
        except AttributeError:
            pass

    def have_all_possible_combos(self):
        # There can be duplicate combos, so it's important to ignore those.
        num_combos = max(len(set(self.select_ordered_rows(self.cols))), 1)
        num_possible_combos = math.prod(
                len(x)
                for x in self.distinct_values_by_col.values()
        )
        return num_combos == num_possible_combos

    def format_as_table(self, rxn):
        return table(
                header=[rxn[k].name for k in self.ordered_cols],
                rows=self.ordered_rows,
        )

    def format_as_dl(self, rxn):
        return dl(*(
                (rxn[k].name, ', '.join(self.distinct_values_by_col[k]))
                for k in self.ordered_cols
                if k in self.distinct_values_by_col
        ))
        
    def _check_cols(self):
        if not self._combos:
            return

        expected_keys = self._combos[0].keys()

        for combo in self._combos:
            if combo.keys() != expected_keys:
                raise UsageError(f"every combo must have the same keys\nexpected: {repr_join(expected_keys)}\nfound: {repr_join(combo.keys())}")

    def _infer_replicates(self):
        """
        Check for "de-facto" replicates, i.e. the case where each combo appears 
        more than once and exactly the same number of times as every other 
        combo.  By detecting this, we can make better protocols by scaling-up 
        and dividing the final reaction mix.
        """
        cols = self.cols
        rows = self.select_ordered_rows(cols)
        counts = Counter(rows)

        try:
            self.replicates *= unanimous(counts.values())
        except ValueError:
            return

        self._combos = [
                dict(zip(cols, row))
                for row in unique(rows)
        ]

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

def make_pipetting_graph(combos, ideal_order=None, split_penalty=0):
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

    if ideal_order:
        order_map = {k: i for i, k in enumerate(ideal_order)}
    
    for a, b in permutations(g.nodes, 2):
        ab_combos = sorted(map(itemgetter(a, b), combos))

        merge_weight = 2 * len(list(groupby(ab_combos)))
        split_weight = split_penalty
        for _, group in groupby(ab_combos, key=itemgetter(0)):
            split_weight += 1 + len(list(groupby(group, key=itemgetter(1))))

        weight = min(merge_weight, split_weight)
        split = split_weight < merge_weight

        if ideal_order:
            order = (order_map[b] - order_map[a] != 1)
        else:
            order = 0

        g.add_edge(a, b, weight=weight, order=order, split=split)

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

    best_weight = inf,
    best_tour = None

    def weights(g, tour):
        weight = itemgetter('weight', 'order')
        yield from (
                weight(g.edges[a, b])
                for a, b in pairwise(tour)
        )

    def tuple_sum(xs):
        return tuple(map(sum, zip(*xs)))

    for tour in permutations(g.nodes):
        weight = tuple_sum(weights(g, tour))

        if weight < best_weight:
            best_weight = weight
            best_tour = tour

    groups = [{best_tour[0]}]

    for a, b in pairwise(best_tour):
        if g.edges[a, b]['split']:
            groups.append(set())
        groups[-1].add(b)

    return groups

