#!/usr/bin/env python3

import pytest
from stepwise.testing import check_command
from utils import *

@pytest.mark.slow
@parametrize_via_toml('test_cli.toml')
def test_main(cmd, env, stdout, stderr, return_code):
    check_command(cmd, stdout, stderr, return_code, env)


