#!/usr/bin/env python3

import pytest
from stepwise import Presets
from param_helpers import *

@parametrize_from_file(
        schema=Schema({
            'presets': [{str: {str: str}}],
            'expected': {str: {str: str}},
        }),
)
def test_presets(presets, expected):
    p = Presets(presets)

    assert set(p) == set(expected)

    for k, v in expected.items():
        assert p[k] == v

@parametrize_from_file(
        schema=Schema({
            'presets': [{str: {str: str}}],
            'key': eval_python,
            'error': error,
        }),
)
def test_presets_err(presets, key, error):
    p = Presets(presets)
    with error:
        p[key]
       




