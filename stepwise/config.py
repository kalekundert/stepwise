#!/usr/bin/env python3

import sys
from pathlib import Path
from appdirs import AppDirs
from configurator import Config, default_mergers
from voluptuous import Schema, All, Invalid

config = None
config_dirs = AppDirs("stepwise")
user_config_path = Path(config_dirs.user_config_dir) / 'conf.toml'
site_config_path = Path(config_dirs.site_config_dir) / 'conf.toml'

def load_config():
    global config
    if config: return config

    def overwrite_list(context, source, target):
        return source

    mergers = default_mergers + {list: overwrite_list}

    config = Config({
        'search': {
            'find': ['protocols'],
            'path': [],
            'ignore': [],
        },
        'printer': {
            'default': {
                'page_height': 56,
                'page_width': 78,
                'content_width': 53,
                'margin_width': 10,
                'paps_flags': '--font "FreeMono 12" --paper letter --left-margin 0 --right-margin 0 --top-margin 12 --bottom-margin 12',
                'lpr_flags': '-o sides=one-sided',
            },
        },
    })
    site = Config.from_path(site_config_path, optional=True)
    user = Config.from_path(user_config_path, optional=True)

    config.merge(site, mergers=mergers)
    config.merge(user, mergers=mergers)

    schema = Schema({
        'search': {
            'find': [str],
            'path': [str],
            'ignore': [str],
        },
        'printer': {
            'default': {
                'page_height': int,
                'page_width': int,
                'content_width': int,
                'margin_width': int,
                'paps_flags': str,
                'lpr_flags': str,
            },
        },
    })

    try:
        schema(config.data)
    except Invalid as err:
        print(f"Warning: {err}", file=sys.stdout)

    return config

