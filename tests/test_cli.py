#!/usr/bin/env python3

import pytest, os
from stepwise.testing import check_command
from param_helpers import *

@pytest.mark.slow
@parametrize_from_file(
        schema=defaults(tmp_files={}, env={}),
        indirect=['tmp_files'],
)
def test_main(tmp_files, cmd, env, stdout, stderr, return_code):
    linux_config = tmp_files / '.config' / 'stepwise' / 'conf.toml'
    mac_config = tmp_files / 'Library' / 'Application Support' / 'stepwise'
    if linux_config.exists():
        mac_config.parent.mkdir(parents=True, exist_ok=False)
        mac_config.symlink_to(linux_config.parent)

    check_command(cmd, stdout, stderr, int(return_code), env, home=tmp_files)
