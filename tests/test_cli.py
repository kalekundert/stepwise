#!/usr/bin/env python3

import pytest
from stepwise.testing import check_command
from param_helpers import *

@pytest.mark.slow
@parametrize_from_file(
        schema=Schema({
            'cmd': str,
            Optional('env', default={}): empty_ok({str: str}),
            'stdout': str,
            'stderr': str,
            'return_code': Coerce(int),
        }),
)
def test_main(cmd, env, stdout, stderr, return_code):
    check_command(cmd, stdout, stderr, return_code, env)


