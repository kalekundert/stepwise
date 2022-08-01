import autoprop
import networkx as nx

from .reaction import Reaction, after
from ..utils import get_memo, repr_join
from ..errors import UsageError

from itertools import product, combinations
from more_itertools import (
        first, ilen, unique_everseen as unique, always_iterable, flatten,
)
from dataclasses import dataclass
from collections import Counter
from reprfunc import repr_from_init
from operator import itemgetter
from math import inf

# Terminology:
# - "reagent": a string containing the name of one individual reagent to 
#   include in the reaction.
#
# - "mix": a Mix object containing a number of reagents/mixes that will be all 
#   mixed together, possibly before being added to other mixes.
#
# - "component": a generic term for either a reagent or a mix.

@autoprop
class Mix:

    def __init__(self, components, *, name=None, volume=None, extra=None, order=0):
        self._components = frozenset(components)
        self._name = name
        self.volume = volume
        self.extra = extra
        self.order = order

        # Filled in by `set_mix_*()`:
        self.default_name = None
        self.reaction = None
        self.stock_conc = None
        self.scales = None
        self.num_reactions = None

    def __eq__(self, other):
        try:
            return self.components == other.components
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash(self.components)

    def __iter__(self):
        yield from self.components

    def __len__(self):
        return len(self.components)

    def get_name(self):
        return self._name or self.default_name

    def set_name(self, name):
        self._name = name

    @autoprop.immutable
    def get_components(self):
        return self._components

    @autoprop.immutable
    def get_mixes(self):
        return frozenset(iter_mixes(self.components))

    @autoprop.immutable
    def get_reagents(self):
        return frozenset(iter_reagents(self.components))

    @autoprop.immutable
    def get_all_reagents(self):
        return frozenset(iter_all_reagents(self.components))

    __repr__ = repr_from_init(
            attrs={'components': set},
            positional=['components'],
    )

class AutoMix:

    def __init__(self, components, init=lambda x: x):
        self.components = components
        self.init = init

    def __iter__(self):
        yield from self.components

    def __len__(self):
        return len(self.components)

    __repr__ = repr_from_init(
            positional=['components'],
    )

class PartialMix(frozenset):
    """
    This class is used internally by `iter_complete_mixes()` to identify mixes 
    that may have more reagents added to them.
    """

    def __new__(cls, components):

        def merge_partial_mixes(components):
            for component in components:
                if isinstance(component, PartialMix):
                    yield from component
                else:
                    yield component

        return super().__new__(cls, merge_partial_mixes(components))

@dataclass
class Score:
    num_pipetting_steps: int
    num_mixes: int
    num_careful_reactions: int
    num_adjacencies: int
    depth: int

    def __lt__(self, other):
        # Lower scores are considered better.  Think of the score as "the 
        # number of pipetting steps it would take to setup these mixes, plus a 
        # bunch of tiebreakers".

        if other is None:
            return True

        a, b = self.num_pipetting_steps, other.num_pipetting_steps

        if a < b: return True
        if a > b: return False

        # If it would take the same amount of pipetting to setup the reaction 
        # with or without a master mix, prefer to make the master mix because 
        # it will make the pipetting more accurate and consistent.

        a, b = self.num_mixes, other.num_mixes

        if a > b: return True
        if a < b: return False

        # Fewer reactions means larger volumes, which is what we want for 
        # reagents that needed to be pipetted carefully.

        a, b = self.num_careful_reactions, other.num_careful_reactions

        if a < b: return True
        if a > b: return False

        a, b = self.num_adjacencies, other.num_adjacencies

        if a > b: return True
        if a < b: return False

        return self.depth < other.depth

def plan_mixes(reaction, combos, *, mixes=None, subset=None, bias=0):
    """
    Find the best set of master mixes to use when preparing the given 
    combinations of the given reagents.

    Arguments:
        reaction:
            ...

        combos:
            ...

        mixes:
            A collections of `Mix` or `AutoMix` instances that must be included 
            in the ultimate reaction setup.

        subset:
            Only consider the given reagents.

    The following criteria are used to decide if one way of mixing the given 
    reagents is better or worse than another:

    - Smallest number of pipetting steps.
    - Largest number of master mixes.
    - Most compatible with *ideal_order*.
    """
    memo = {}

    mixes = plan_automixes(mixes or [], reaction, combos, bias=bias)
    components = init_components(reaction, mixes, subset)
    components = mix_matching_components(components, combos, memo)
    filters = [
            lambda mix: require_solvent_with_volume(mix, reaction.solvent),
    ]

    best_mix = None
    best_score = None

    careful_reagents = find_careful_reagents(reaction)
    order_map = make_order_map(reaction.keys())

    for mix in unique(iter_complete_mixes(components, combos, filters)):
        score = score_mix(mix, combos, bias, careful_reagents, order_map, memo)
        if score < best_score:
            best_mix = mix
            best_score = score

    assert best_mix or not reaction
    return best_mix

def plan_automixes(mixes, *args, **kwargs):
    processed = []

    for mix in mixes:
        if isinstance(mix, AutoMix):
            automix, mix = mix, plan_mixes(
                    *args,
                    **kwargs,
                    subset=iter_all_reagents(mix),
            )
            automix.init(mix)

        processed.append(mix)

    return processed

def set_mix_names(mix, reaction, notable_reagents, format_name=lambda x: None):
    """
    Assign a name to each mix.

    - If there is only one master mix, it will simply be named "master mix".

    - Any mixes containing only reagents that are the same in every combo will 
      also be named "master mix".  Note that it is possible for several mixes 
      to be named "master mix", but only if you specify mixes manually.  In 
      this case, the best solution is to provide a name when creating manual 
      mixes.

    - Any remaining mixes will be named after any "notable" reagents they 
      contain.  Typically, these would be reagents that vary between the 
      different combinations.
    """
    children = list(iter_all_mixes(mix))
    
    order_map = make_order_map(reaction.keys())
    by_order = lambda x: order_map[x]

    for child in children:
        if name := format_name(child):
            child.default_name = name
            continue

        reagents = notable_reagents & set(iter_reagents(child))

        if not reagents or len(children) == 1:
            child.default_name = 'master'
        else:
            child.default_name = '/'.join(
                    reaction[k].name
                    for k in sorted(reagents, key=by_order)
            )

def set_mix_reactions(
        mix,
        base_reaction,
        reagent_names,
        format_stock_conc=lambda m, c: None,
        solvent_volume=None,
    ):
    """
    Create a reaction for each mix.  This process includes (i) copying the 
    reagents from the base reaction that are relevant to each step, (ii) 
    renaming reagents that don't vary, and (iii) adding references to 
    previous master mixes.
    """

    mix.reaction = rxn = Reaction()
    reagents = mix.reagents

    # Make a reaction containing all of the relevant reagents:

    for key in base_reaction.keys():
        if key in reagents:
            rxn[key] = base_reaction[key]
            try:
                rxn[key].name = reagent_names[key]
            except KeyError:
                pass

    # Set the volume of the reaction, accounting for the fact that some 
    # reagents will be added in different mixes and the solvent could be split 
    # between any number of mixes:

    solvent = base_reaction.solvent

    def sum_mix_volume(mix, solvent_volume=0):
        volume = 0 * base_reaction.volume

        for reagent in mix.reagents:
            if reagent == solvent:
                volume += solvent_volume
            else:
                volume += base_reaction[reagent].volume

        for child in mix.mixes:
            if child.volume:
                volume += child.volume, base_reaction.volume.unit
            else:
                volume += sum_mix_volume(child, solvent_volume)

        return volume

    def divide_solvent_between_children(solvent_volume):
        n = ilen(iter_all_mixes_with_solvent(mix, solvent))
        return solvent_volume / n if n else None

    if solvent:
        if mix.volume:
            mix_volume = mix.volume, base_reaction.volume.unit
            reagents_volume = sum_mix_volume(mix, 0)
            solvent_volume = divide_solvent_between_children(
                    mix_volume - reagents_volume
            )

        if not solvent_volume:
            # The solvent volume is only unset for (i) the root mix and (ii) 
            # any mixes that don't contain solvent.  Since we checked for a 
            # solvent above, we will only enter this conditional for the root 
            # mix.  That's why it's correct to subtract the reagent volumes 
            # from the total reaction volume.
            reagents_volume = sum_mix_volume(mix, 0)
            solvent_volume = divide_solvent_between_children(
                    base_reaction.volume - reagents_volume
            )

        if solvent in reagents:
            rxn.volume = sum_mix_volume(mix, solvent_volume)

    # Add any relevant master mixes to the reaction:

    current_reagents = {x: (x, False) for x in reagents}

    for child in iter_mixes(mix):

        # Recursively configure the reaction for the child mix, because we'll 
        # need to know its volume in the following steps:

        set_mix_reactions(
                child,
                base_reaction,
                reagent_names,
                format_stock_conc,
                solvent_volume,
        )

        # Try to match the order of reagents in the original reaction as best 
        # as possible:

        i = 0
        child_reagents = set(iter_all_reagents(child))

        for k in base_reaction.keys():
            if k in current_reagents:
                reagent, skip = current_reagents[k]
                if not skip:
                    i = after(reagent)
            elif k in child_reagents:
                break

        key = f'{child.name} mix'
        rxn.insert_reagent(key, i)
        rxn[key].volume = child.reaction.volume

        current_reagents.update({
            x: (key, x == solvent)
            for x in child_reagents - reagents
        })

        # If the master mix has a nice stock concentration, include it:
        
        if not child.stock_conc:
            stock_conc = base_reaction.volume / child.reaction.volume
            if x := format_stock_conc(child, stock_conc):
                child.stock_conc = x

        rxn[key].stock_conc = child.stock_conc

def set_mix_scales(
        mix,
        combos,
        default_extra,
        default_extra_children,
        combo_volumes=None,
    ):
    """
    Calculate how much to scale up each mix, accounting for all the reagent 
    combinations that need to be prepared and the amount of extra volume 
    requested by the user.

    This task is complicated by the fact that it's sometimes necessary to 
    prepare multiple scales of the same mix.
    """

    # Account for how many times each combination of reagents will be used:

    all_reagents = sorted(set(iter_all_reagents(mix)))
    combo_counts = Counter(
            tuple(combo.get(k) for k in all_reagents)
            for combo in combos
    )

    # Account for volumes needed in downstream mixes:

    if not combo_volumes:
        count_scales = {
                v: v * combos.replicates
                for v in unique(combo_counts.values())
        }

    else:
        count_volumes = {}
        for combo, count in combo_counts.items():
            volumes = count_volumes.setdefault(count, [])
            volumes.append(combo_volumes[combo])

        count_scales = {
                k: max(v) / mix.reaction.volume
                for k, v in count_volumes.items()
        }

    # Account the amount of extra volume requested:

    extra = mix.extra or default_extra
    count_scales = {
            k: extra.increase_scale(v, mix.reaction)
            for k, v in count_scales.items()
    }

    mix.scales = set(count_scales.values())
    mix.num_reactions = len(combo_counts)

    # Handle upstream mixes:

    for child in iter_mixes(mix):
        child_reagents = set(iter_all_reagents(child))
        child_combo_indices = [
                i for i, x in enumerate(all_reagents)
                if x in child_reagents
        ]
        child_combo_volumes = {}

        for combo, count in combo_counts.items():
            child_combo = itemgetter(*child_combo_indices)(combo)
            volume = child_combo_volumes.get(child_combo, 0)
            volume += child.reaction.volume * count_scales[count]
            child_combo_volumes[child_combo] = volume

        set_mix_scales(
                child,
                combos,
                default_extra_children,
                default_extra_children,
                child_combo_volumes,
        )

def init_components(reaction, required_mixes, subset=None):
    # Silently ignore mixes with no reagents.  I was on the fence about whether 
    # or not to make this an error.  On one hand, an empty mix has a pretty 
    # clear interpretation.  On the other, an empty mix could very well be 
    # indicative of a logic error.  That said, I decided to allow it because I 
    # can imagine building mixes in some automated way where it would be 
    # inconvenient to prune empty values.
    required_mixes = set(x for x in required_mixes if x)
    reagents = set(reaction.keys())
    solvent = reaction.solvent
    subset = set(subset or [])
    already_seen = set()

    if subset:
        reagents = reagents & subset
        if solvent not in subset:
            solvent = None

    for mix in required_mixes:
        mix_reagents = set(iter_all_reagents(mix))

        unknown_reagents = mix_reagents - reagents
        if unknown_reagents:
            raise UsageError(f"can't use reagents that aren't in the {'automix' if subset else 'reaction'}: {repr_join(sorted(unknown_reagents))}")

        duplicate_reagents = mix_reagents & already_seen
        if duplicate_reagents:
            raise UsageError(f"can't use the same reagent in multiple mixes: {repr_join(k for k in reaction.keys() if k in duplicate_reagents)}")

        if mix.volume:
            if not solvent:
                raise UsageError(f"can't specify mix volume unless the {'automix' if subset else 'reaction'} has a solvent")
            if not any(iter_all_mixes_with_solvent(mix, solvent)):
                raise UsageError("can't specify mix volume unless the mix contains solvent")
            mix_reagents.discard(solvent)

        already_seen |= mix_reagents

    return (reagents - already_seen) | required_mixes 

def iter_complete_mixes(components, combos, filters, memo=None):
    """
    Yield mixes that include every component from all of the given levels.

    You can think of this function as generating every possible way (in terms 
    of master mixes) to mix the given components.  In reality, some common 
    sense is used to avoid generating unreasonable results.  Specifically:

    - Reagents with the fewest number of variants are the first to be merged.
    - Reagents that vary together will always be added together.
    - If the same reagents can be mixed in multiple different ways, only keep 
      those that take the fewest pipetting steps.
    - Custom filters can be provided to perform more targeted pruning.

    This function may yield the same mix multiple times, so the caller should 
    account for this.
    """

    def find_best_pairs(components):
        best_pairs = []
        best_num_combos = inf

        for pair in combinations(components, 2):
            n = count_combos(pair, combos, memo)
            if n == best_num_combos:
                best_pairs.append(pair)
            elif n < best_num_combos:
                best_pairs = [pair]
                best_num_combos = n

        return best_pairs

    def mix_pairs(pairs):
        for a1, b1 in pairs:
            a2 = iter_possible_components(a1)
            b2 = iter_possible_components(b1)
            for a3, b3 in product(a2, b2):
                yield {a1, b1}, PartialMix({*a3, *b3})

    def iter_possible_components(x):
        """
        Yield the components associated with the given argument.

        Reagents and mixes are yielded directly.  Partial mixes are yielded as 
        both a mix and a collection of reagents.
        """
        if isinstance(x, PartialMix):
            yield [Mix(x)]
            yield x
        else:
            yield [x]

    def mix_from_component(component):
        if isinstance(component, Mix):
            return component
        if isinstance(component, PartialMix):
            return Mix(component)
        else:
            return Mix({component})

    if len(components) == 1:
        yield mix_from_component(first(components))
        return

    # We only consider the pairs that have the fewest combos at each 
    # iteration, so this is a greedy algorithm.  I haven't been able to 
    # think of a case where it generates the wrong answer, but I'm not 
    # totally sure that no such cases exist.

    pairs = find_best_pairs(components)

    for components_to_remove, mix_to_add in mix_pairs(pairs):
        if all(f(mix_to_add) for f in filters):
            merged = components - components_to_remove | {mix_to_add}
            yield from iter_complete_mixes(merged, combos, filters)

def mix_matching_components(components, combos, memo=None):
    levels = {}

    for component in components:
        n = count_combos(component, combos, memo)
        levels.setdefault(n, set()).add(component)

    for n in levels:
        groups = []
        group_map = {}

        for a, b in combinations(levels[n], 2):
            n_ab = count_combos((a, b), combos, memo)
            if n == n_ab:
                try:
                    group = group_map[a]
                except KeyError:
                    try:
                        group = group_map[b]
                    except KeyError:
                        group = set()
                        groups.append(group)

                group |= {a, b}
                group_map[a] = group_map[b] = group

        for group in groups:
            levels[n] -= group
            levels[n] |= {PartialMix(group)}

    return frozenset().union(*levels.values())

def require_solvent_with_volume(components, solvent):
    """
    Filter out any reaction setups with that would make it impossible to 
    satisfy the mix volumes requested by the user.

    Any mix that specifies a volume must also contain solvent, since the 
    solvent is the only reagent with variable volume.  The solvent doesn't need 
    to be in the mix itself, though: it could be in any of that mixes children 
    (not counting children that specify their own volumes).

    This function only really matters if the user requests an `AutoMix` with a 
    specific volume.  Regular mixes with volumes are already required to 
    contain solvent (e.g. an exception is raised if they don't), and so will 
    always pass this test.
    """
    return all(
            not x.volume or any(iter_all_mixes_with_solvent(x, solvent))
            for x in iter_mixes(components)
    )

def prune_suboptimal_mixes(
        new_components,
        combos,
        candidates,
        best_num_pipetting_steps,
        memo=None,
):
    def contains_mix(components, mix):
        return any(mix == x for x in iter_all_mixes(components))

    suboptimal = set()

    for mix in iter_mixes(new_components):
        n_pipet = count_pipetting_steps(mix, combos, memo)
        n_best = best_num_pipetting_steps.get(mix.all_reagents, inf)

        if n_pipet < n_best:
            suboptimal.add(mix.all_reagents)
            best_num_pipetting_steps[mix.all_reagents] = n_pipet
        if n_pipet > n_best:
            return False

    if suboptimal:
        candidates[:] = [
                x for x in candidates
                if not any(contains_mix(x, y) for y in suboptimal)
        ]

    return True

def find_careful_reagents(reaction):
    return [x.key for x in reaction.iter_reagents_by_flag('careful')]

def score_mix(mix, combos, bias, careful_reagents, order_map, memo):
    n_mix = ilen(iter_all_mixes(mix))
    n_pipet = count_pipetting_steps(mix, combos, memo) + n_mix * bias
    n_care = count_combos_by_reagent(mix, careful_reagents, combos, memo)
    n_adj = count_adjacencies(mix, order_map)
    depth = find_depth(mix)

    return Score(n_pipet, n_mix, sum(n_care.values()), n_adj, depth)

def count_pipetting_steps(components, combos, memo=None):
    """
    Return the number of pipetting steps it would take to prepare each 
    combination of the given reagents.

    Arguments:
        mix:
            A mix object that specifies which reagents to mix in which order, 
            and what master mixes to make.

        combos:
            A list of dictionaries specifying which combinations of reagents to 
            make.

        memo:
            A dictionary containing the results from previous calls to this 
            function.  If the given mix is a key in this dictionary, the 
            corresponding value will be returned immediately.  The combos are 
            not checked when consulting the memo, so the caller must take care 
            to not reuse memos that were calculated with different combos.

    Note that if there are duplicate combinations, this function will return 
    just the number of pipetting steps necessary to create a single tube for 
    each unique combination.
    """
    assert not isinstance(components, str)
    memo = get_memo(memo, count_pipetting_steps)

    # Convert to `frozenset` because we may be passed levels (which are 
    # `frozensets`) and mixes (which are `Mix` instances) that contain the same 
    # components, and we want both to be cached with the same key.  This 
    # conversion also allows us to accept non-hashable inputs, although to my 
    # knowledge no such input is ever given.
    components = frozenset(components)

    if components in memo:
        return memo[components]
    
    n_combos = count_combos(components, combos, memo)
    n_steps = n_combos * len(components)

    for mix in iter_mixes(components):
        n_steps += count_pipetting_steps(mix, combos, memo)

    memo[components] = n_steps
    return n_steps

def count_combos(component_or_components, combos, memo=None):
    memo = get_memo(memo, count_combos)

    components = always_iterable(component_or_components)
    reagents = frozenset(iter_all_reagents(components))

    if reagents in memo:
        return memo[reagents]
    
    n_combos = len({
            tuple(combo.get(k) for k in reagents)
            for combo in combos
    })

    memo[reagents] = n_combos
    return n_combos

def count_combos_by_reagent(mix, reagents, combos, memo=None):
    mixes = {}

    for child in iter_all_mixes(mix, include_given=True):
        for reagent in child.reagents:
            mixes[reagent] = child

    n_combos = {}

    for reagent in reagents:
        child = mixes[reagent]
        reagents_it = iter_all_reagents(child)
        n_combos[reagent] = count_combos(reagents_it, combos, memo=None)

    return n_combos

def count_adjacencies(components, order_map):
    if not order_map:
        return 0

    n_adj = 0

    for mix in iter_all_mixes(components, include_given=True):

        # When comparing to reagents in the same mix, order doesn't matter:
        for a, b in combinations(mix.reagents, 2):
            n_adj += abs(order_map[b] - order_map[a]) == 1

        # When comparing to reagents in upstream mixes, order does matter:
        child_reagents = set(flatten(x.reagents for x in iter_mixes(mix)))
        for b in mix.reagents:
            for a in child_reagents:
                if order_map[b] - order_map[a] == 1:
                    n_adj += 1
                    break

    return n_adj

def find_depth(mix):
    mixes = mix.mixes
    return 1 + max(find_depth(x) for x in mixes) if mixes else 0

def iter_reagents(components):
    for component in components:
        if isinstance(component, str):
            yield component

def iter_mixes(components):
    for component in components:
        if isinstance(component, Mix):
            yield component

def iter_all_reagents(components):
    for component in components:
        if isinstance(component, str):
            yield component
        else:
            yield from iter_all_reagents(component)

def iter_all_mixes(components, include_given=False):
    if include_given:
        if isinstance(components, Mix):
            yield components

    for component in components:
        if not isinstance(component, str):
            yield from iter_all_mixes(component, include_given=True)

def iter_all_mixes_with_solvent(mix, solvent):
    """
    Recursively find all mixes that contain the solvent.

    The purpose of this function is to help setup the solvent for mixes with 
    user-specified volumes.  For this reason, the search exclude child mixes 
    that themselves specify a volume, since the volume of solvent in such mixes 
    cannot be freely changed.
    """
    if solvent in iter_reagents(mix):
        yield mix

    for child in iter_mixes(mix):
        if not child.volume:
            yield from iter_all_mixes_with_solvent(child, solvent)

def iter_all_mixes_in_protocol_order(mix, reaction):
    """
    Yield every mix in the order it should be prepared.

    The most important requirement is that upstream mixes must be prepared 
    before downstream mixes.  After that, an effort is made to present the 
    mixes in an intuitive order.  Mixes with the fewest combos come first, and 
    ties are broken by trying to maintain the order in which the reagents 
    appear in the base reaction.  This ordering is deterministic, which is 
    good for (i) testing and (ii) not confusing the user by re-ordering the 
    mixes every time the protocol is generated.
    """
    g = make_mix_graph(mix)
    rxn_order_map = make_order_map(reaction.keys())

    def by_rxn_order(mix):
        rxn_order = min(
                (
                    rxn_order_map[k]
                    for k in iter_reagents(mix)
                    if k != reaction.solvent
                ),
                default=0,
        )
        return mix.order, mix.num_reactions, rxn_order

    yield from nx.lexicographical_topological_sort(g, by_rxn_order)

def mix_from_level(level):
    if len(level) == 1:
        head = first(level)
        if isinstance(head, Mix):
            return head

    return Mix(level)

def make_order_map(ideal_order):
    return {k: i for i, k in enumerate(ideal_order)} if ideal_order else {}

def make_mix_graph(mix):
    g = nx.DiGraph()

    for parent in iter_all_mixes(mix, include_given=True):
        g.add_node(parent)
        for child in iter_mixes(parent):
            g.add_edge(child, parent)

    return g

def format_stock_conc_as_int(mix, conc):
    if conc.is_integer():
        return f'{int(conc)}x'

def format_stock_conc_as_int_ratio(mix, conc, sig_figs=2):
    """
    Try to format the given concentration as a "nice" ratio, e.g. "3/2x".

    The current implementation only works for numbers that have exact floating 
    point representations, which I think means just ratios with power-of-two 
    denominators.  However, this might be expanded in the future.
    """
    a, b = conc.as_integer_ratio()

    def count_sig_figs(x):
        return len(str(x).rstrip('0'))

    if b == 1:
        return f'{a}x'

    if all(count_sig_figs(x) <= sig_figs for x in (a,b)):
        return f'{a}/{b}x'

