#!/usr/bin/env python3

from stepwise.reaction import *
from test_reaction import eval_reaction
from param_helpers import *
from pytest_unordered import unordered
from funcy import autocurry

class MixWrapper:

    @classmethod
    def from_strs(cls, d):
        return cls(
                name=d.get('name'),
                reagents=set(d['reagents']),
                reaction=eval_reaction(d['reaction']),
                scale=pytest.approx(float(d['scale'])),
                num_reactions=int(d['num_reactions']),
        )

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        builder = ReprBuilder(self)
        for k, v in self.__dict__.items():
            builder.add_keyword_value(k, v)
        return str(builder)

    def __eq__(self, actual):
        if not isinstance(actual, Reactions.Mix):
            raise AssertionError(f"expected 'Reactions.Mix', got {actual!r}")

        if hasattr(self, 'name') and self.name != actual.name:
            raise AssertionError(f"expected name={self.name!r}, got {actual.name!r}")

        if self.reagents != actual.reagents:
            raise AssertionError(f"expected reagents={self.reagents!r}, got {actual.reagents!r}")

        if self.reaction != actual.reaction:
            raise AssertionError(f"expected reaction={self.reaction!r}, got {actual.reaction!r}")

        if self.num_reactions != actual.num_reactions:
            raise AssertionError(f"expected num_reactions={self.num_reactions!r}, got {actual.num_reactions!r}")

        if approx(self.scale) != actual.scale:
            raise AssertionError(f"expected scale={self.scale!r}, got {actual.scale!r}")

        return True

@autocurry
def exec_reactions(x, defer=False):

    def from_str(x):
        return with_sw.exec(x, get='rxns', defer=defer)

    def from_dict(d):

        def factory():
            with_mix = with_sw.fork(
                    Mix=Reactions.Mix,
                    AutoMix=Reactions.AutoMix,
            )
            schema = Schema({
                'base': eval_reaction,
                'combos': [dict],
                Optional('replicates'): Coerce(int),
                Optional('mixes'): [with_mix.eval],

                # Default extra to 0 for testing, because calculating it by 
                # hand adds complexity and isn't usually relevant.
                Optional('extra', default={}): Or(
                    And(dict, lambda x: Extra(**with_py.eval(x))),
                    And(str, with_sw.eval),
                ),

                Optional('exec'): str,
            })
            kw = schema(d)
            exec = kw.pop('exec', None)
            rxns = Reactions(kw.pop('base'), kw.pop('combos'), **kw)

            if exec:
                with_sw.fork(rxns=rxns).exec(exec)

            return rxns


        if defer:
            factory.exec = factory
            return factory
        else:
            return factory()

    schema = Or(
            And(str, from_str),
            And(dict, from_dict),
    )
    return schema(x)

def eval_mix_wrappers(mix_dicts):
    return [MixWrapper.from_strs(x) for x in mix_dicts]


@parametrize_from_file
def test_reactions_protocol(reactions, expected):
    rxns = exec_reactions(reactions)
    expected = with_sw.eval(expected)
    assert rxns.protocol.steps == expected

@parametrize_from_file
def test_reactions_combo_step(reactions, expected):
    rxns = exec_reactions(reactions)
    expected = with_sw.eval(expected)
    assert rxns.combo_step == expected

@parametrize_from_file
def test_reactions_combos_table(reactions, expected):
    rxns = exec_reactions(reactions)
    rxn = rxns.base_reaction
    combos = rxns.combos
    expected = with_sw.eval(expected)

    combos.sort_by_appearance(rxns.mixes)
    assert combos.format_as_table(rxn) == expected

@parametrize_from_file
def test_reactions_combos_dl(reactions, expected):
    rxns = exec_reactions(reactions)
    rxn = rxns.base_reaction
    combos = rxns.combos
    expected = with_sw.eval(expected)

    combos.sort_by_appearance(rxns.mixes)
    assert combos.format_as_dl(rxn) == expected

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reactions_mixes(reactions, expected, error):
    rxns = exec_reactions(reactions)
    expected = eval_mix_wrappers(expected)

    with error:
        assert rxns.mixes == expected


@parametrize_from_file(
        schema=[
            defaults(replicates=1),
            with_sw.error_or('expected'),
        ],
)
def test_combos_init(combos, replicates, expected, error):
    with error:
        combos = Combos(combos, int(replicates))
        assert list(combos) == expected['combos']
        assert len(combos) == int(expected['len'])
        assert combos.replicates == int(expected['replicates'])

@parametrize_from_file
def test_combos_values_by_col(combos, expected):
    combos = Combos(combos)

    assert combos.cols == set(expected['all'].keys())
    assert combos.values_by_col == expected['all']

    assert combos.unique_values_by_col == expected['unique']

    assert combos.distinct_cols == set(expected['distinct'].keys())
    assert combos.distinct_values_by_col == expected['distinct']

@parametrize_from_file(schema=with_sw.error_or())
def test_combos_check_reagents(combos, reaction, error):
    combos = Combos(combos)
    rxn = eval_reaction(reaction)
    with error:
        combos.check_reagents(rxn)

@parametrize_from_file
def test_combos_select(combos, cols, expected):
    combos = Combos(combos)
    assert list(combos.select(cols)) == expected['unordered']
    assert combos.select_ordered_rows(cols) == list_of_tuples(expected['ordered'])

@parametrize_from_file
def test_combos_sort_by_appearance(combos, mixes, ordered_cols, ordered_rows):
    combos = Combos(combos)
    mixes = mixes_with_reactions(mixes)

    combos.sort_by_appearance(mixes)

    assert combos.ordered_cols == ordered_cols
    assert combos.ordered_rows == list_of_tuples(ordered_rows)


@parametrize_from_file(
        schema=[
            cast(scale=float, expected=float),
            defaults(reaction='', expected_repr=''),
        ],
)
def test_extra(extra, scale, reaction, expected, expected_repr):
    if not expected_repr:
        expected_repr = extra

    extra = with_sw.eval(extra)

    if reaction:
        rxn = eval_reaction(reaction)
    else:
        rxn = Reaction()
        rxn['w'].volume = 'to 1 µL'

    assert repr(extra) == expected_repr
    assert extra.increase_scale(scale, rxn) == approx(expected)

@parametrize_from_file(
        schema=[
            cast(penalty=int),
            defaults(order=None, penalty=0),
        ],
)
def test_minimize_pipetting(combos, order, penalty, graph, groups):
    g = make_pipetting_graph(combos, order, penalty)

    actual_edges = [
            {'start': a, 'end': b, **data}
            for a, b, data in g.edges.data()
    ]
    expected_edges = unordered(with_py.eval(graph))
    assert actual_edges == expected_edges

    actual_groups = minimize_pipetting(g)
    expected_groups = [set(x) for x in groups]
    assert actual_groups == expected_groups

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reaction_from_docopt(args, expected, error):
    with error:
        assert reaction_from_docopt(args) == eval_reaction(expected)

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_combos_from_docopt(args, expected, error):
    with error:
        assert combos_from_docopt(args) == expected

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_extra_from_docopt(args, expected, error):
    with error:
        assert extra_from_docopt(args) == with_sw.eval(expected)


def mixes_with_reactions(mixes):
    mix_objs = []

    for reagents in mixes:
        mix = Reactions.Mix(reagents); mix_objs.append(mix)
        mix.reaction = Reaction()
        for reagent in reagents:
            mix.reaction.append_reagent(reagent)

    return mix_objs

def list_of_tuples(xs):
    return [tuple(x) for x in xs]
