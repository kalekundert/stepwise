import byoc
import autoprop
import networkx as nx
import sys
import re
import math

from byoc import Key, DocoptConfig, float_eval
from inform import plural
from itertools import groupby, permutations, repeat
from more_itertools import (
        pairwise, repeat_last, unique_everseen as unique, mark_ends, ilen, one
)
from reprfunc import repr_from_init
from operator import itemgetter, not_
from collections import Counter
from dataclasses import dataclass
from math import inf
from copy import copy
from fractions import Fraction

from .reaction import Reaction, format_reaction, after
from .mix import (
        Mix, plan_mixes, set_mix_names, set_mix_reactions, set_mix_scales,
        iter_mixes, iter_all_mixes_in_protocol_order, format_stock_conc_as_int,
)
from ..format import pl, ul, dl, table
from ..quantity import Quantity
from ..config import StepwiseConfig
from ..utils import unanimous, repr_join
from ..errors import *

def reaction_from_docopt(args):
    if '--config-file' in args:
        return reaction_from_xlsx(args['--config-file'], 0)

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
    if '--config-file' in args:
        return combos_from_xlsx(args['--config-file'], 1)

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

def reaction_from_xlsx(path, sheet):
    import pandas as pd
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    return Reaction.from_df(df)

def combos_from_xlsx(path, sheet):
    import pandas as pd
    try:
        df = pd.read_excel(path, sheet_name=sheet, dtype=str).fillna('')

    except ValueError as err:
        # `ValueError` is raised when the given worksheet isn't found, but it 
        # is raised in other contexts as well.  Unfortunately, the only way to 
        # make sure we have the right error is to parse the error message.  It 
        # would be more robust to pare the file ourselves using `openpyxl`, but 
        # this would add a lot of complexity and remove a lot of flexibility 
        # that pandas provides.

        if re.match(r'Worksheet index \d+ is invalid, \d+ worksheets found', str(err)):
            return []
        else:
            raise

    return df.to_dict('records')

def mixes_from_strs(mix_strs):
    return [
            Mix(x.split(','))
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

    def __init__(self, reaction, combos=None, *, replicates=None, mixes=None, extra=None):
        self.base_reaction = reaction

        if combos: self._user_combos = combos
        if replicates: self._user_replicates = replicates
        if mixes: self.required_mixes = mixes
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

        if not self.mix.mixes and len(self.combos) < 2:
            step += self.get_mix_table(self.mix)

        else:
            step += ul(br='\n\n')

            if self.show_combos and len(self.combos) > 1:
                step[-1] += self.combos_step

            for mix in self.mixes:
                step[-1] += self.get_mix_step(mix)

        if self.combos.replicates > 1 and self.split_replicates:
            step += ul(f"Split into {self.combos.replicates} identical {self.base_reaction.volume:.2f} reactions.")

        if self.instructions:
            step += self.instructions

        return step

    @autoprop.cache(policy='manual')
    def get_combos(self):
        combos = Combos(self._user_combos or [{}], self._user_replicates)
        combos.check_reagents(self.base_reaction)
        return combos

    def set_combos(self, combos):
        self._user_combos = combos

        try:
            autoprop.del_cached_attr(self, 'combos')
        except AttributeError:
            pass

        try:
            del self.mix
        except AttributeError:
            pass

    def get_combos_step(self):
        self.combos.sort_by_appearance(self.base_reaction)

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

    def get_mix(self):
        mix = plan_mixes(
                self.base_reaction,
                self.combos,
                mixes=self.required_mixes,
                bias=self.master_mix_bias,
        )
        self._refresh(mix)

        # TODO: remove reagents with zero volume and recalculate mixes.

        return mix

    def get_mix_step(self, mix):
        n = mix.num_reactions
        table = self.get_mix_table(mix)

        if mix is self.mix:
            show_n = (self.combos.replicates > 1) and self.split_replicates
            return pl(f"Setup {n if show_n else 'the'} reactions:", table)

        if mix.stock_conc:
            name = f'{mix.stock_conc} {mix.name}'
        else:
            name = f'{mix.name}'

        # Don't use plural() here, because the mix names can contain slashes, 
        # and that would mess up the formatting.
        if n == 1:
            step = f"Make {name} mix:"
        else:
            step = f"Make {n} {name} mixes:"

        return pl(step, table)

    def get_mix_table(self, mix):
        return format_reaction(mix.reaction, scale=mix.scales)

    def get_mixes(self):
        return list(iter_all_mixes_in_protocol_order(
                self.mix,
                self.base_reaction,
        ))

    def refresh(self):
        try: del self.mix
        except AttributeError: pass

        self._refresh(self.mix)

    def refresh_names(self):
        """
        Update the names of all the reagents in all the mixes.

        This is necessary after changing the name of an automatically-generated 
        mix (but not if you simply provided a pre-calculated mix with a 
        non-default name to the constructor).
        """
        self._refresh_names(self.mix)

    def refresh_reactions(self):
        """
        Recalculate the reaction table for each mix.

        This is necessary after making changes to mix volumes.  Note however 
        that if you assigned a volume to a mix that previously didn't have one 
        (or vice versa), a full refresh is required because the entire reaction 
        setup could change.  Setting or unsetting a mix volume can change which 
        reactions have solvent, which can change the number of pipetting steps 
        required to setup the reactions, which can change the whole master mix 
        scheme.
        """
        self._refresh_reactions(self.mix)

    def refresh_scales(self):
        """
        Recalculate how much to scale each reaction.

        This is necessary after changing the *extra* attributes associated with 
        either this `Reactions` object or any of the mixes.
        """
        self._refresh_scales(self.mix)

    def _refresh(self, mix):
        self._refresh_names(mix)

    def _refresh_names(self, mix):
        set_mix_names(
                mix,
                self.base_reaction,
                self.combos.distinct_cols,
                self.format_mix_name,
        )
        self._refresh_reactions(mix)

    def _refresh_reactions(self, mix):
        reagent_names = {
                k: one(v) for k, v in self.combos.unique_values_by_col.items()
                if len(v) == 1
        }
        set_mix_reactions(
                mix,
                self.base_reaction,
                reagent_names,
                self.format_mix_stock_conc,
        )
        self._refresh_scales(mix)

    def _refresh_scales(self, mix):
        if self.last_mix_extra or (self.combos.replicates > 1):
            default_extra = self.extra
        else:
            default_extra = Extra()

        set_mix_scales(mix, self.combos, default_extra, self.extra)

        try: del self.mixes
        except AttributeError: pass

        try: del self.step
        except AttributeError: pass

        try: del self.protocol
        except AttributeError: pass

    docopt_usage = """\
Setup one or more reactions.

Usage:
    reaction (<reagent;stock;conc;volume>... | -f <config>) [-C <reagents>]
        [-c <combo>]... [-r <replicates>] [-v <volume>] [-m <reagents>]...
        [-M <bias>] [-S <step>] [-s <kind>] [-i <instruction>]... 
        [-x <percent>] [-X <volume>] [options]

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
    -f --config-file <path>
        The path to an XLS or XLSX file specifying (i) the reagents comprising 
        the reaction and (ii) what combinations of reagents to setup.  The file 
        should contain two sheets.  The first should have the following 
        columns:

        - "Reagent"
        - "Stock Conc" or "Stock"
        - "Final Conc" or "Final"
        - "Volume"

        See the decription of the <reagent;stock;conc;volume> argument for the 
        specific meanings of these columns.  Each row in this sheet defines a 
        reagent that will be included in the reaction, and you can define as 
        many reagents as you'd like.

        The second sheet should have a column names that exactly match 
        "Reagent" values from the first sheet.  Each row should name a 
        combination of reagent variants that should be mixed together.  This 
        table corresponds to the `--combo-reagents` and `--combo` options.
        
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

    -M --mix-bias
        Set the bias for creating master mixes.  To give some background, this 
        program determines whether or not to make master mixes by calculating 
        the number of pipetting steps that would be required to setup the same 
        reactions with or without.  Master mixes are only made when doing so 
        doesn't increase this number.  This "bias" is added to the number of 
        pipetting steps for the master mix case.  So, by setting the bias to a 
        positive number, you discourage the program from making master mixes 
        unless they really help.  By setting the bias to a negative number, you 
        encourage the program to make master mixes even when it would mean more 
        pipetting.  The default bias is 0.  Note that this option is ignored if 
        `--mix` is specified.

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

    --hide-combos
        Don't include the list of all the reagent combinations to setup in the 
        protocol, e.g. when this information would be clear from prior steps in 
        the protocol.

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

    reactions.mix_bias
        See `--mix-bias`.

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
    required_mixes = byoc.param(
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
    show_combos = byoc.param(
            Key(DocoptConfig, '--hide-combos', cast=not_),
            default=True,
    )
    format_mix_name = byoc.param(
            default=lambda mix: None,
    )
    format_mix_stock_conc = byoc.param(
            default=format_stock_conc_as_int,
    )
    instructions = byoc.param(
            Key(DocoptConfig, '--instruction', cast=ul.from_iterable),
            default_factory=ul,
    )
    split_replicates = byoc.param(
            Key(DocoptConfig, '--no-split-replicates', cast=not_),
            default=True,
    )
    last_mix_extra = byoc.param(
            Key(DocoptConfig, '--last-mix-extra'),
            default=False,
    )
    master_mix_bias = byoc.param(
            Key(DocoptConfig, '--mix-bias', cast=float),
            Key(StepwiseConfig, 'mix_bias'),
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
        return len(self._combos)

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
        cols = set(cols) & self.cols
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

    def sort_by_appearance(self, rxn):
        self._ordered_cols = []

        for reagent in rxn:
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

    __repr__ = repr_from_init(
            attrs={'combos': '_combos', 'replicates': '_replicates'},
            positional=['combos'],
    )

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

    def fork(self, **kwargs):
        extra = copy(self)

        known_attrs = [
                'fraction',
                'percent',
                'reactions',
                'volume',
                'min_volume',
        ]

        for attr in known_attrs:
            try:
                setattr(extra, attr, kwargs.pop(attr))
            except KeyError:
                pass

        if kwargs:
            raise TypeError(f"fork() got unexpected keyword argument(s): {repr_join(kwargs)}")

        return extra

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


