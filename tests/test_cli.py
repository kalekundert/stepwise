#!/usr/bin/env python3

import pytest
from stepwise.testing import check_command
from param_helpers import *

@pytest.mark.slow
@parametrize_from_file(schema=defaults(env={}))
def test_main(cmd, env, stdout, stderr, return_code):
    check_command(cmd, stdout, stderr, int(return_code), env)


