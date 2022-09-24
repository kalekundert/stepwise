#!/usr/bin/env python3

from param_helpers import *
from stepwise.cli.skip import parse_index, parse_indices

@parametrize_from_file(
        schema=[
            cast(n_steps=int, expected=int),
            with_py.error_or('expected'),
        ],
)
def test_parse_index(step_str, n_steps, expected, error):
    with error:
        assert parse_index(step_str, n_steps) == expected

@parametrize_from_file(
        schema=[
            cast(n_steps=int, expected=with_py.eval),
            with_py.error_or('expected'),
        ],
)
def test_parse_indices(steps_str, n_steps, expected, error):
    l = list(range(n_steps))
    with error:
        i = parse_indices(steps_str, n_steps)
        assert l[i] == expected

