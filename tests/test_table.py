#!/usr/bin/env python3

import pytest, stepwise, stepwise.table as mod
from utils import parametrize_via_toml

@parametrize_via_toml('test_table.toml')
def test_tabulate(rows, header, footer, format, align, truncate, max_width, expected):
    table = stepwise.tabulate(
            rows,
            header=header,
            footer=footer,
            format=eval(format) if format else None,
            align=align,
            truncate=truncate,
            max_width=max_width,
    )
    assert table == expected.strip('\n')

@parametrize_via_toml('test_table.toml')
def test_concat_rows(rows, header, footer, format, expected, i_header, i_footer):
    assert mod._concat_rows(rows, header, footer, eval(format)) == (
            expected, i_header, i_footer)

@parametrize_via_toml('test_table.toml')
def test_concat_rows_err(rows, header, footer, format, err):
    with pytest.raises(ValueError, match=err):
        mod._concat_rows(rows, header, footer, eval(format))

@parametrize_via_toml('test_table.toml')
def test_split_row(row, align, expected):
    assert mod._split_row(row, align) == expected

@parametrize_via_toml('test_table.toml')
def test_auto_align(rows, expected):
    assert mod._auto_align(rows) == expected

@parametrize_via_toml('test_table.toml')
def test_measure_cols(table, truncate, max_width, pad, expected):
    expected = expected['cols'], expected['table']
    assert mod._measure_cols(table, truncate, max_width, pad) == expected

@parametrize_via_toml('test_table.toml')
def test_measure_cols_err(table, truncate, max_width, pad, err):
    with pytest.raises(ValueError, match=err):
        mod._measure_cols(table, truncate, max_width, pad)

@parametrize_via_toml('test_table.toml')
def test_count_cols(table, expected):
    assert mod._count_cols(table) == expected

@parametrize_via_toml('test_table.toml')
def test_count_cols_err(table, err):
    with pytest.raises(ValueError, match=err):
        mod._count_cols(table)

