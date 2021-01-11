#!/usr/bin/env python3

import pytest
from stepwise import Presets
from utils import *

@parametrize_via_toml('test_config.toml')
def test_presets(presets, expected):
    p = Presets(presets)
    for k, v in expected.items():
        assert p[k] == v

@parametrize_via_toml('test_config.toml')
def test_presets_err(presets, key, error):
    p = Presets(presets)
    with pytest.raises(KeyError, match=error):
        p[key]
       




