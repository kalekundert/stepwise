#!/usr/bin/env python3

"""\
Show configuration settings.

Usage:
    stepwise config [<setting>]

Arguments:
    <setting>
        A particular setting to show.  By default, all settings will be shown.
"""

import docopt
import toml
from inform import fatal
from stepwise import load_config
from .main import command

@command
def config():
    args = docopt.docopt(__doc__)
    config = load_config().data

    if setting := args['<setting>']:
        keys = setting.split('.')

        try:
            for key in keys:
                config = config[key]
        except KeyError:
            fatal(f"unknown setting {setting!r}")

        if not isinstance(config, dict):
            config = {key: config}

    print(toml.dumps(config))

