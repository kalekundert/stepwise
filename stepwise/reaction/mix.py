import autoprop
import networkx as nx

from .reaction import Reaction, after
from ..utils import repr_join
from ..errors import UsageError

from itertools import chain, product, combinations
from more_itertools import (
        first, ilen, unique_everseen as unique, always_iterable, flatten,
)
from collections import Counter
from reprfunc import repr_from_init
from operator import itemgetter
from math import inf

# Terminology:
# - "reagent": a string containing the name of one individual reagent to 
#   include in the reaction.
# - "mix": a Mix object containing a number of reagents/mixes that will be all 
#   mixed together, possibly before being added to other mixes.
# - "components": a collection (usually a set) of reagents and mixes.
# - "level": a set of components that all have no more than a certain number of 
#   variants.  The algorithm for finding the optimal way to setup a reaction 
#   involves forming master mixes between components in the same or adjacent 
#   levels, then recursively merging the top two levels until only one remains.

# Potential optimizations:
# - If `bias=0`, I might be able to merge all matching components in the 
#   initial levels.  The rest of the algorithm would be the same.  The question 
#   is just whether there are any cases where prematurely merging these 
#   components would give the wrong result.
# - Cache calls to `count_combos()`.  Basically I would use the same `memo` 
#   dictionary, but I would make it two-level: `memo[func][input]`.  I might 
#   also write a bit of code to help manage that.

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

def plan_mixes(reaction, combos, *, mixes=None, subset=None, bias=0):
    """
    Find the best set of master mixes to use when preparing the given 
    combinations of the given reagents.

    Arguments:
        components:
            Can be string or Mix.

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
    order_map = make_order_map(reaction.keys())
    levels = sort_by_num_combos(components, combos)

    best_mix = None
    best_num_pipetting_steps = inf
    best_num_mixes = 0
    best_num_adjacencies = 0

    for mix in iter_complete_mixes(levels, combos, reaction.solvent, memo):
        n = count_pipetting_steps(mix, combos, memo)
        n_mix = ilen(iter_all_mixes(mix))
        n_adj = count_adjacencies(mix, order_map)
        n += n_mix * bias

        is_best = n < best_num_pipetting_steps
        if n == best_num_pipetting_steps:
            is_best = n_mix > best_num_mixes
            if n_mix == best_num_mixes:
                is_best = n_adj > best_num_adjacencies

        if is_best:
            best_mix = mix
            best_num_pipetting_steps = n
            best_num_mixes = n_mix
            best_num_adjacencies = n_adj

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

def set_mix_names(mix, reaction, notable_reagents):
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
    
    if len(children) == 1:
        children[0].default_name = 'master'
        return

    order_map = make_order_map(reaction.keys())
    by_order = lambda x: order_map[x]

    for child in children:
        reagents = notable_reagents & set(iter_reagents(child))

        if not reagents:
            child.default_name = 'master'
        else:
            child.default_name = '/'.join(
                    reaction[k].name
                    for k in sorted(reagents, key=by_order)
            )

def set_mix_reactions(mix, base_reaction, reagent_names, solvent_volume=None):
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

        set_mix_reactions(child, base_reaction, reagent_names, solvent_volume)

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
            if stock_conc.is_integer():
                child.stock_conc = f'{int(stock_conc)}x'

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

def sort_by_num_combos(components, combos):
    level_assignments = {}

    for component in components:
        n = count_combos(component, combos)
        level_assignments.setdefault(n, set()).add(component)

    levels = []
    for k in sorted(level_assignments):
        levels.append(frozenset(level_assignments[k]))

    return levels

def iter_complete_mixes(levels, combos, solvent, memo=None):
    """
    Yield possibly nested mixes that collectively include every component from 
    all of the given levels.

    You can think of this function as generating every possible way (in terms 
    of master mixes) to mix the given components.  In reality, some pruning is 
    done to eliminate mixes that obviously don't make sense.  The level of 
    pruning is an implementation detail, and may change without warning.
    """
    assert levels

    if len(levels) == 1:
        yield mix_from_level(levels[0])
        return

    top_levels = set(iter_merged_top_levels(
            levels[0],
            levels[1],
            find_matching_components(levels[0], combos),
            find_matching_components(levels[1], combos),
    ))
    top_levels = keep_levels_with_least_pipetting(top_levels, combos, memo)
    top_levels = drop_levels_with_volume_but_not_solvent(top_levels, solvent)

    for top_level in top_levels:
        levels_recurse = [top_level, *levels[2:]]
        yield from iter_complete_mixes(levels_recurse, combos, solvent, memo)
    
def iter_merged_top_levels(level_1, level_2, matches_1, matches_2):
    """
    Yield every possible way to make master mixes between two levels.

    Arguments:
        level_1:
            One of the two levels to combine.  See `sort_by_num_combos()` for 
            how levels are created.
        level_2:
            See *level_1*.
        matches_1:
            A dictionary identifying every group of components in *level_1* 
            that vary in the exact same way.  See `find_matching_components()` 
            for more on this data structure.
        matches_2:
            See *matches_2*.

    Each level is a set of components that are related by the number of 
    variants they have.  Everything in *level_1* will have fewer variants than 
    everything in *level_2*.  Master mixes can be formed (i) between components 
    of adjacent levels or (ii) between components in the same level that have 
    the same number of variants (called "matches").

    The purpose of this function is generate every possible way to combine the 
    top two levels into a single level.  Note that this function may generate 
    duplicates.  The caller is responsible for handling these appropriately.
    """

    def include_matches(component, level, matches):
        try:
            group = matches[component]
        except KeyError:
            yield component, set(level) - {component}, matches
        else:
            assert len(group) > 1
            matches_remaining = {
                    k: v
                    for k, v in matches.items()
                    if k not in group
            }
            yield component, level - {component}, matches_remaining
            yield Mix(group), level - group, matches_remaining

    if (not level_1) and (not level_2):
        yield frozenset()

    elif (not level_1) or (not level_2):
        if not level_1:
            level = level_2
            matches = matches_2
        else:
            level = level_1
            matches = matches_1

        for c, l, m in include_matches(first(level), level, matches):
            for remainder in iter_merged_top_levels(l, set(), m, {}):
                yield frozenset({c, *remainder})

    else:
        for component_1, component_2 in product(level_1, level_2):
            clm_1 = include_matches(component_1, level_1, matches_1)
            clm_2 = include_matches(component_2, level_2, matches_2)

            for (c1, l1, m1), (c2, l2, m2) in product(clm_1, clm_2):
                for remainder in iter_merged_top_levels(l1, l2, m1, m2):
                    yield frozenset({c1, c2, *remainder})
                    yield frozenset({Mix({c1, c2}), *remainder})

def find_matching_components(components, combos):
    groups = {}

    for a, b in combinations(components, 2):
        n_a = count_combos(a, combos)
        n_b = count_combos(b, combos)
        n_ab = count_combos({a, b}, combos)

        if n_a == n_b == n_ab:
            try:
                group = groups[a]
            except KeyError:
                try:
                    group = groups[b]
                except KeyError:
                    group = set()

            group |= {a, b}
            groups[a] = groups[b] = group

    return groups

def keep_levels_with_least_pipetting(levels, combos, memo=None):
    """
    Filter out levels that require more than the minimum number of pipetting 
    steps.
    """
    best_levels = {}
    best_num_pipetting_steps = {}

    for level in levels:
        k = len(level)
        n = count_pipetting_steps(level, combos, memo)
        n_best = best_num_pipetting_steps.get(k, inf)

        if n < n_best:
            best_levels[k] = [level]
            best_num_pipetting_steps[k] = n

        elif n == n_best:
            best_levels[k].append(level)

    for level in best_levels.values():
        yield from level

def drop_levels_with_volume_but_not_solvent(levels, solvent):
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
    for level in levels:
        if all(
                not x.volume or any(iter_all_mixes_with_solvent(x, solvent))
                for x in iter_mixes(level)
        ):
            yield level

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

    # Convert to `frozenset` because we may be passed levels (which are 
    # `frozensets`) and mixes (which are `Mix` instances) that contain the same 
    # components, and they will have the same number of pipetting steps.  This 
    # conversion also allows us to accept non-hashable inputs, although to my 
    # knowledge no such input is ever given.
    components = frozenset(components)

    if memo is not None and components in memo:
        return memo[components]
    
    n_combos = count_combos(components, combos)
    n_steps = n_combos * len(components)

    for mix in iter_mixes(components):
        n_steps += count_pipetting_steps(mix, combos, memo)

    if memo is not None:
        memo[components] = n_steps

    return n_steps

def count_adjacencies(components, order_map):
    if not order_map:
        return 0

    n_adj = 0

    for mix in iter_all_mixes(components, include_given=True):

        # When comparing to reagents in the same mix, order doesn't matter:
        for a, b in combinations(mix.reagents, 2):
            n_adj += abs(order_map[b] - order_map[a]) == 1

        # When comparing to reagents in upstream mixes, order does matter:
        child_reagents = flatten(x.reagents for x in iter_mixes(mix))
        for b in mix.reagents:
            for a in child_reagents:
                if order_map[b] - order_map[a] == 1:
                    n_adj += 1
                    break

    return n_adj

def count_combos(component_or_components, combos):
    components = always_iterable(component_or_components)
    reagents = list(iter_all_reagents(components))
    return len({
            tuple(combo.get(k) for k in reagents)
            for combo in combos
    })

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
        yield components

    for mix in iter_mixes(components):
        yield from iter_all_mixes(mix, include_given=True)

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
    before downstream mixes.  After that, an effort is made to sort the mixes 
    by the order in which the reagents appear in the base reaction.  This makes 
    the order deterministic, which is good for (i) testing and (ii) not 
    confusing the user by re-ordering the mixes every time the protocol is 
    generated.
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
        return mix.order, rxn_order

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



