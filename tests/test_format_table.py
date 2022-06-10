#!/usr/bin/env python3

import pytest, stepwise
from inspect import getmodule
from param_helpers import *

# I can't directly import this module because it's name is masked by various 
# other modules and classes.  Rather than renaming a bunch of things, I decided 
# to just access the module indirectly.
mod = getmodule(stepwise.table)

@parametrize_from_file(
        schema=[
            cast(
                rows=with_py.eval,
                header=with_py.eval,
                footer=with_py.eval,
                format=with_py.eval,
                align=with_py.eval,
                truncate=with_py.eval,
                max_width=with_py.eval,
            ),
            defaults(
                header=None,
                footer=None,
                format=None,
                align=None,
                truncate=None,
                max_width=-1,
            ),
        ]
)
def test_tabulate(rows, header, footer, format, align, truncate, max_width, expected):
    table = stepwise.tabulate(
            rows,
            header=header,
            footer=footer,
            format=format,
            align=align,
            truncate=truncate,
            max_width=max_width,
    )
    assert table == expected.strip('\n')

@parametrize_from_file(
        schema=[
            cast(
                rows=with_py.eval,
                header=with_py.eval,
                footer=with_py.eval,
                format=with_py.eval,
                expected=with_py.eval,
                i_header=int,
                i_footer=int,
            ),
            error_or('expected', 'i_header', 'i_footer'),
        ],
)
def test_concat_rows(rows, header, footer, format, expected, i_header, i_footer, error):
    with error:
        assert mod._concat_rows(rows, header, footer, format) == (
                expected, i_header, i_footer)

@parametrize_from_file(
        schema=cast(
            row=with_py.eval,
            align=with_py.eval,
            expected=with_py.eval,
        ),
)
def test_split_row(row, align, expected):
    assert mod._split_row(row, align) == expected

@parametrize_from_file(
        schema=cast(
            rows=with_py.eval,
            expected=with_py.eval,
        ),
)
def test_auto_align(rows, expected):
    assert mod._auto_align(rows) == expected

@parametrize_from_file(
        schema=[
            cast(
                table=with_py.eval,
                truncate=with_py.eval,
                max_width=with_py.eval,
                pad=with_py.eval,
                expected=with_py.eval,
            ),
            error_or('expected'),
        ],
)
def test_measure_cols(table, truncate, max_width, pad, expected, error):
    with error:
        expected = expected['cols'], expected['table']
        assert mod._measure_cols(table, truncate, max_width, pad) == expected

@parametrize_from_file(
        schema=[
            cast(
                table=with_py.eval,
                expected=int,
            ),
            error_or('expected'),
        ]
)
def test_count_cols(table, expected, error):
    with error:
        assert mod._count_cols(table) == expected

