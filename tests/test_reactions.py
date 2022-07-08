#!/usr/bin/env python3

from stepwise.reaction import *
from test_reaction import eval_reaction
from param_helpers import *
from pytest_unordered import unordered
from funcy import autocurry

class MixWrapper:

    @classmethod
    def from_strs(cls, d):
        if isinstance(d, Mock):
            return Mock()

        try:
            d['scales'] = [d['scale']]
        except KeyError:
            pass

        return cls(
                name=d.get('name'),
                reagents=set(d['reagents']),
                mixes=[MixWrapper.from_strs(x) for x in d.get('mixes', [])],
                reaction=eval_reaction(d['reaction']),
                scales=[float(x) for x in d['scales']],
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
        if not isinstance(actual, Mix):
            raise AssertionError(f"expected 'Reactions.Mix', got {actual!r}")

        if self.name and self.name != actual.name:
            raise AssertionError(f"expected name={self.name!r}, got {actual.name!r}")

        if self.reagents != actual.reagents:
            raise AssertionError(f"expected reagents={self.reagents!r}, got {actual.reagents!r}")

        if self.mixes:
            assert UnorderedList(self.mixes, False) == actual.mixes

        if self.reaction != actual.reaction:
            raise AssertionError(f"expected reaction={self.reaction!r}, got {actual.reaction!r}")

        if self.num_reactions != actual.num_reactions:
            raise AssertionError(f"expected num_reactions={self.num_reactions!r}, got {actual.num_reactions!r}")

        if approx(sorted(self.scales)) != sorted(actual.scales):
            raise AssertionError(f"expected scales={self.scales!r}, got {actual.scales!r}")

        return True

@autocurry
def exec_reactions(x, defer=False):

    def from_str(x):
        return with_sw.exec(x, get='rxns', defer=defer)

    def from_dict(d):

        def factory():
            schema = Schema({
                'base': eval_reaction,
                'combos': [dict],
                Optional('replicates'): Coerce(int),
                Optional('mixes'): [with_sw.eval],

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

def list_of_tuples(xs):
    return [tuple(x) for x in xs]


@parametrize_from_file
def test_reactions_protocol(reactions, expected):
    rxns = exec_reactions(reactions)
    expected = with_sw.eval(expected)
    print(rxns.step.format_text(inf))
    assert rxns.protocol.steps == expected

def test_reactions_refresh_names():
    rxn = Reaction()
    rxn['a'].volume = '1 µL'
    rxn['b'].volume = '2 µL'
    rxn['c'].volume = '3 µL'

    combos = [
            {'a': '1'},
            {'a': '2'},
    ]

    mix = Mix({'b', 'c'})

    rxns = Reactions(rxn, combos, mixes=[mix], extra=Extra())

    # Check auto-generated mix name:
    assert rxns.step == pl(
            "Setup 2 reactions:",
            ul(
              pl(
                "Use the following reagents:",
                dl(('a', '1, 2')),
              ),
              pl(
                "Make master mix:",  # <---
                table(
                  header=["Reagent", "Volume", "2x"],
                  rows=[
                      ["b", "2.00 µL", "4.00 µL"],
                      ["c", "3.00 µL", "6.00 µL"],
                  ],
                  footer=["", "5.00 µL", "10.00 µL"],
                  align=list("<>>"),
                ),
              ),
              pl(
                "Setup the reactions:",
                table(
                  header=["Reagent", "Volume"],
                  rows=[
                      ["a", "1.00 µL"],
                      ["master mix", "5.00 µL"],  # <---
                  ],
                  footer=["", "6.00 µL"],
                  align=list("<>"),
                ),
              ),
              br='\n\n',
            ),
    ), 'before'

    # Check refreshed mix name:
    mix.name = 'B/C'
    rxns.refresh_names()

    assert rxns.step == pl(
            "Setup 2 reactions:",
            ul(
              pl(
                "Use the following reagents:",
                dl(('a', '1, 2')),
              ),
              pl(
                "Make B/C mix:",  # <---
                table(
                  header=["Reagent", "Volume", "2x"],
                  rows=[
                      ["b", "2.00 µL", "4.00 µL"],
                      ["c", "3.00 µL", "6.00 µL"],
                  ],
                  footer=["", "5.00 µL", "10.00 µL"],
                  align=list("<>>"),
                ),
              ),
              pl(
                "Setup the reactions:",
                table(
                  header=["Reagent", "Volume"],
                  rows=[
                      ["a", "1.00 µL"],
                      ["B/C mix", "5.00 µL"],  # <---
                  ],
                  footer=["", "6.00 µL"],
                  align=list("<>"),
                ),
              ),
              br='\n\n',
            ),
    ), 'after'

def test_reactions_refresh_reactions():
    rxn = Reaction()
    rxn['w'].volume = 'to 6 µL'
    rxn['a'].volume = '1 µL'
    rxn['b'].volume = '2 µL'

    combos = [
            {'a': '1'},
            {'a': '2'},
    ]

    mix = Mix({'w', 'b'}, volume=4)

    rxns = Reactions(rxn, combos, mixes=[mix], extra=Extra())
    rxns.master_mix_bias = 1

    # Check the auto-generated mix reaction:
    assert rxns.step == pl(
            "Setup 2 reactions:",
            ul(
              pl(
                "Use the following reagents:",
                dl(('a', '1, 2')),
              ),
              pl(
                "Make master mix:",
                table(
                  header=["Reagent", "Volume", "2x"],
                  rows=[
                      ["w", "2.00 µL", "4.00 µL"],
                      ["b", "2.00 µL", "4.00 µL"],
                  ],
                  footer=["", "4.00 µL", "8.00 µL"],
                  align=list("<>>"),
                ),
              ),
              pl(
                "Setup the reactions:",
                table(
                  header=["Reagent", "Volume"],
                  rows=[
                      ["w", "1.00 µL"],
                      ["a", "1.00 µL"],
                      ["master mix", "4.00 µL"],
                  ],
                  footer=["", "6.00 µL"],
                  align=list("<>"),
                ),
              ),
              br='\n\n',
            ),
    ), 'before'

    # Check the refreshed mix reaction:
    mix.volume = 3
    rxns.refresh_reactions()

    assert rxns.step == pl(
            "Setup 2 reactions:",
            ul(
              pl(
                "Use the following reagents:",
                dl(('a', '1, 2')),
              ),
              pl(
                "Make 2x master mix:",
                table(
                  header=["Reagent", "Volume", "2x"],
                  rows=[
                      ["w", "1.00 µL", "2.00 µL"],
                      ["b", "2.00 µL", "4.00 µL"],
                  ],
                  footer=["", "3.00 µL", "6.00 µL"],
                  align=list("<>>"),
                ),
              ),
              pl(
                "Setup the reactions:",
                table(
                  header=["Reagent", "Stock", "Volume"],
                  rows=[
                      ["w", "", "2.00 µL"],
                      ["a", "", "1.00 µL"],
                      ["master mix", "2x", "3.00 µL"],
                  ],
                  footer=["", "", "6.00 µL"],
                  align=list("<>>"),
                ),
              ),
              br='\n\n',
            ),
    ), 'after'

def test_reactions_refresh_scales():
    rxn = Reaction()
    rxn['w'].volume = 'to 6 µL'
    rxn['a'].volume = '1 µL'
    rxn['b'].volume = '2 µL'

    combos = [
            {'a': '1'},
            {'a': '2'},
    ]

    rxns = Reactions(rxn, combos, extra=Extra())

    # Check auto-generated mix volumes:
    assert rxns.step == pl(
            "Setup 2 reactions:",
            ul(
              pl(
                "Use the following reagents:",
                dl(('a', '1, 2')),
              ),
              pl(
                "Make master mix:",
                table(
                  header=["Reagent", "Volume", "2x"],  # <---
                  rows=[
                      ["w", "3.00 µL", "6.00 µL"],     # <---
                      ["b", "2.00 µL", "4.00 µL"],     # <---
                  ],
                  footer=["", "5.00 µL", "10.00 µL"],  # <---
                  align=list("<>>"),
                ),
              ),
              pl(
                "Setup the reactions:",
                table(
                  header=["Reagent", "Volume"],
                  rows=[
                      ["master mix", "5.00 µL"],
                      ["a", "1.00 µL"],
                  ],
                  footer=["", "6.00 µL"],
                  align=list("<>"),
                ),
              ),
              br='\n\n',
            ),
    ), 'before'

    # Check refreshed mix volumes:
    rxns.extra = Extra(percent=10)
    rxns.refresh_scales()

@parametrize_from_file
def test_reactions_combos_step(reactions, expected):
    rxns = exec_reactions(reactions)
    expected = with_sw.eval(expected)
    assert rxns.combos_step == expected

@parametrize_from_file
def test_reactions_combos_table(reactions, expected):
    rxns = exec_reactions(reactions)
    rxn = rxns.base_reaction
    combos = rxns.combos
    expected = with_sw.eval(expected)

    combos.sort_by_appearance(rxn)
    assert combos.format_as_table(rxn) == expected

@parametrize_from_file
def test_reactions_combos_dl(reactions, expected):
    rxns = exec_reactions(reactions)
    rxn = rxns.base_reaction
    combos = rxns.combos
    expected = with_sw.eval(expected)

    combos.sort_by_appearance(rxn)
    assert combos.format_as_dl(rxn) == expected

@parametrize_from_file(
        schema=with_sw.error_or('expected'),
)
def test_reactions_mixes(reactions, expected, error):
    rxns = exec_reactions(reactions)
    expected = MixWrapper.from_strs(expected)

    with error:
        assert rxns.mix == expected


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
def test_combos_sort_by_appearance(combos, reaction, ordered_cols, ordered_rows):
    combos = Combos(combos)
    rxn = eval_reaction(reaction)

    combos.sort_by_appearance(rxn)

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
        expected_repr = extra.replace('Extra().fork(', 'Extra(')

    extra = with_sw.eval(extra)

    if reaction:
        rxn = eval_reaction(reaction)
    else:
        rxn = Reaction()
        rxn['w'].volume = 'to 1 µL'

    assert repr(extra) == expected_repr
    assert extra.increase_scale(scale, rxn) == approx(expected)

def test_extra_fork_unknown_arg():
    with pytest.raises(TypeError, match=r"unexpected keyword argument\(s\): 'unknown_attr'"):
        Extra().fork(unknown_attr=0)


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


