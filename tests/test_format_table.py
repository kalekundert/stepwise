#!/usr/bin/env python3

import pytest, stepwise
from inspect import getmodule
from param_helpers import *

# I can't directly import this module because it's name is masked by various 
# other modules and classes.  Rather than renaming a bunch of things, I decided 
# to just access the module indirectly.
mod = getmodule(stepwise.table)

@parametrize_from_file(
        schema=Schema({
            'rows': eval_python,
            Optional('header', default='None'): eval_python,
            Optional('footer', default='None'): eval_python,
            Optional('format', default='None'): eval_python,
            Optional('align', default='None'): eval_python,
            Optional('truncate', default='None'): eval_python,
            Optional('max_width', default='-1'): eval_python,
            'expected': str,
        }),
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
        schema=Schema({
            'rows': eval_python,
            'header': eval_python,
            'footer': eval_python,
            'format': eval_python,
            'expected': eval_python,
            'i_header': Coerce(int),
            'i_footer': Coerce(int),
        }),
)
def test_concat_rows(rows, header, footer, format, expected, i_header, i_footer):
    assert mod._concat_rows(rows, header, footer, format) == (
            expected, i_header, i_footer)

@parametrize_from_file(
        schema=Schema({
            'rows': eval_python,
            'header': eval_python,
            'footer': eval_python,
            'format': eval_python,
            'err': str,
        }),
)
def test_concat_rows_err(rows, header, footer, format, err):
    with pytest.raises(ValueError, match=err):
        mod._concat_rows(rows, header, footer, format)

@parametrize_from_file(
        schema=Schema({
            'row': eval_python,
            'align': eval_python,
            'expected': eval_python,
        }),
)
def test_split_row(row, align, expected):
    assert mod._split_row(row, align) == expected

@parametrize_from_file(
        schema=Schema({
            'rows': eval_python,
            'expected': eval_python,
        }),
)
def test_auto_align(rows, expected):
    assert mod._auto_align(rows) == expected

@parametrize_from_file(
        schema=Schema({
            'table': eval_python,
            'truncate': eval_python,
            'max_width': eval_python,
            'pad': eval_python,
            'expected': {
                'cols': eval_python,
                'table': Coerce(int),
            },
        }),
)
def test_measure_cols(table, truncate, max_width, pad, expected):
    expected = expected['cols'], expected['table']
    assert mod._measure_cols(table, truncate, max_width, pad) == expected

@parametrize_from_file(
        schema=Schema({
            'table': eval_python,
            'truncate': eval_python,
            'max_width': eval_python,
            'pad': eval_python,
            'err': str,
        }),
)
def test_measure_cols_err(table, truncate, max_width, pad, err):
    with pytest.raises(ValueError, match=err):
        mod._measure_cols(table, truncate, max_width, pad)

@parametrize_from_file(
        schema=Schema({
            'table': eval_python,
            'expected': Coerce(int),
        }),
)
def test_count_cols(table, expected):
    assert mod._count_cols(table) == expected

@parametrize_from_file(
        schema=Schema({
            'table': eval_python,
            'err': str,
        }),
)
def test_count_cols_err(table, err):
    with pytest.raises(ValueError, match=err):
        mod._count_cols(table)

