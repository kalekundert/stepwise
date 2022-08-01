#!/usr/bin/env python3

from stepwise import Reaction, Extra, Combos
from stepwise.reaction.mix import *
from test_reaction import eval_reaction
from param_helpers import *

def parse_combos(given):
    if not given:
        return [{}]

    n = 0
    rows = {}

    for k in given:
        row = given[k].split()
        if not row:
            continue

        rows[k] = row

        if n == 0:
            n = len(row)
        else:
            assert n == len(row)

    return [
            {k: rows[k][i] for k in rows}
            for i in range(n)
    ]

def parse_reaction_and_combos(reaction, combos):
    if reaction:
        rxn = eval_reaction(reaction)
    else:
        rxn = Reaction()
        for k in combos:
            rxn.append_reagent(k)

    combos = parse_combos(combos)
    return rxn, combos
    
def parse_components_and_combos(components, combos):
    """
    Construct `components` and `combos` data structures from a succinct 
    table-like representation.  Not every reaction setup can be represented 
    this way, but those that can are very succinct.
    """
    components = parse_components(x) if (x := components) else set(combos)
    combos = parse_combos(combos)
    return components, combos

def parse_levels(level_strs):
    return [parse_components(x) for x in level_strs]

def parse_components(given):
    if isinstance(given, str):
        given = given.split()

    return frozenset(parse_component(x) for x in given)

def parse_component(given):
    if isinstance(given, str):
        if '+' in given:
            return Mix(given.split('+'))
        else:
            return given

    return parse_mix(given)

def parse_mix(given):
    return Mix(parse_components(given))

def parse_mixes(given):
    return [parse_mix(x) for x in given]

def parse_matches(given):
    matches = {}

    for group in parse_components(given):
        for k in group:
            matches[k] = frozenset(group)

    return matches

def eval_mix(mixes, reactions=None, **globals):
    for k in mixes:
        mixes[k] = with_sw.fork(MIXES=mixes, **globals).eval(mixes[k])
        if reactions:
            mixes[k].reaction = eval_reaction(reactions[k])

    return mixes[k]


@parametrize_from_file(
        schema=[
            cast(required_mixes=with_sw.eval, bias=int),
            defaults(reaction=None, required_mixes=None, bias=0),
        ],
)
def test_plan_mixes(reaction, combos, required_mixes, bias, expected):
    ideal_order = list(combos.keys())
    rxn, combos = parse_reaction_and_combos(reaction, combos)
    actual = plan_mixes(rxn, combos, mixes=required_mixes, bias=bias)
    expected = parse_mix(expected)
    assert actual == expected

@parametrize_from_file(schema=defaults(notable_reagents=[]))
def test_set_mix_names(mixes, reaction, notable_reagents, expected):
    mix = eval_mix(mixes)
    rxn = eval_reaction(reaction)
    notable_reagents = set(notable_reagents)

    set_mix_names(mix, rxn, notable_reagents)

    for k, name in expected.items():
        assert mixes[k].name == name

@parametrize_from_file(schema=defaults(names={}, kwargs={}))
def test_set_mix_reactions(mixes, reaction, names, kwargs, expected):
    mix = eval_mix(mixes)
    rxn = eval_reaction(reaction)
    kwargs = with_sw.eval(kwargs)

    set_mix_reactions(mix, rxn, names, **kwargs)

    for k, expected_rxn in expected.items():
        expected_rxn = eval_reaction(expected_rxn)
        assert mixes[k].reaction == expected_rxn, k

@parametrize_from_file(
        schema=[
            cast(
                expected=Schema({
                    str: {
                        'scales': lambda xs: [float(x) for x in xs.split()],
                        'num_reactions': Int,
                        },
                }),
                extra=with_sw.eval(),
            ),
            defaults(extra={'root': Extra(), 'children': Extra()}),
        ],
)
def test_set_mix_scales(mixes, reactions, combos, extra, expected):
    mix = eval_mix(mixes, reactions)
    combos = Combos(parse_combos(combos))

    set_mix_scales(mix, combos, extra['root'], extra['children'])

    for k, params in expected.items():
        assert sorted(mixes[k].scales) == approx(params['scales']), k
        assert mixes[k].num_reactions == params['num_reactions'], k

@parametrize_from_file(
        schema=[
            defaults(subset=None),
            with_sw.error_or('expected'),
        ],
)
def test_init_components(reaction, mixes, subset, expected, error):
    rxn = eval_reaction(reaction)
    required_mixes = with_sw.eval(mixes)
    expected = parse_components(expected)

    with error:
        assert init_components(rxn, required_mixes, subset) == expected

def test_init_partial_mix():
    assert PartialMix({'a', 'b'}) == {'a', 'b'}
    assert PartialMix({'a', PartialMix({'b', 'c'})}) == {'a', 'b', 'c'}
    assert PartialMix({PartialMix({'a', 'b'}), 'c'}) == {'a', 'b', 'c'}
    assert PartialMix({PartialMix({'a', 'b'}), PartialMix({'c', 'd'})}) == {'a', 'b', 'c', 'd'}

@parametrize_from_file(schema=defaults(components=None))
def test_mix_matching_components(components, combos, expected):
    components, combos = parse_components_and_combos(components, combos)
    expected = set(with_sw.eval(expected))
    assert mix_matching_components(components, combos) == expected

@parametrize_from_file
def test_count_pipetting_steps(mix, combos, expected):
    mix = parse_mix(mix)
    combos = parse_combos(combos)
    expected = eval(expected)
    assert count_pipetting_steps(mix, combos) == expected

@parametrize_from_file
def test_count_combos_by_reagent(mix, reagents, combos, expected):
    mix = parse_mix(mix)
    combos = parse_combos(combos)
    expected = Schema({str: Int})(expected)
    assert count_combos_by_reagent(mix, reagents, combos) == expected

@parametrize_from_file
def test_count_adjacencies(mix, ideal_order, expected):
    mix = parse_mix(mix)
    order_map = make_order_map(ideal_order)
    expected = eval(expected)
    assert count_adjacencies(mix, order_map) == expected

@parametrize_from_file
def test_find_depth(mix, expected):
    mix = parse_mix(mix)
    assert find_depth(mix) == int(expected)

@parametrize_from_file
def test_iter_all_mixes_in_protocol_order(mixes, reaction, expected):
    mix = eval_mix(mixes)
    rxn = eval_reaction(reaction)
    actual = list(iter_all_mixes_in_protocol_order(mix, rxn))
    expected = parse_mixes(expected)
    assert actual == expected

@parametrize_from_file(schema=with_sw.eval)
def test_format_stock_conc(func, conc, expected):
    assert func(None, conc) == expected


