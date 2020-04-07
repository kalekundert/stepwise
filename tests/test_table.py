#!/usr/bin/env python3

import pytest, stepwise, stepwise.table as mod
from utils import parametrize_via_toml

@parametrize_via_toml('test_table.toml')
def test_tabulate(rows, header, footer, alignments, expected):
    assert stepwise.tabulate(rows, header, footer, alignments) == expected.strip('\n')

@parametrize_via_toml('test_table.toml')
def test_concat_rows(rows, header, footer, expected):
    assert mod._concat_rows(rows, header, footer) == expected

@parametrize_via_toml('test_table.toml')
def test_auto_align(rows, expected):
    assert mod._auto_align(rows) == expected

@parametrize_via_toml('test_table.toml')
def test_count_cols(table, expected):
    assert mod._count_cols(table) == expected

@parametrize_via_toml('test_table.toml')
def test_count_cols_err(table, err):
    with pytest.raises(ValueError, match=err):
        mod._count_cols(table)

@parametrize_via_toml('test_table.toml')
def test_measure_cols(table, expected):
    assert mod._measure_cols(table) == expected

