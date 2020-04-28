#!/usr/bin/env python3

import sys
from pathlib import Path
from appdirs import AppDirs

config = None
config_dirs = AppDirs("stepwise")
user_config_path = Path(config_dirs.user_config_dir) / 'conf.toml'
site_config_path = Path(config_dirs.site_config_dir) / 'conf.toml'

def load_config():
    global config
    if config: return config

    from configurator import Config, default_mergers
    from voluptuous import Schema, Invalid
    from entrypoints import get_group_all
    from collections.abc import Mapping
    from inform import warn

    # Specify that list should be overridden, rather than appended to.

    def overwrite_list(context, source, target):
        return source

    mergers = default_mergers + {list: overwrite_list}

    # Load config data from plugins.

    plugin_configs = {}
    plugin_schemas = {}

    for entry in get_group_all('stepwise.protocols'):
        plugin = entry.load()
        defaults = getattr(plugin, 'config_defaults', {})
        schema = getattr(plugin, 'config_schema', {})

        if defaults:
            plugin_configs[entry.name] = (
                    defaults if isinstance(defaults, Mapping) else
                    Config.from_path(defaults).data
            )
        if schema:
            plugin_schemas[entry.name] = schema

    # Load config data from the local system.

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
        **plugin_configs,
    })
    site = Config.from_path(site_config_path, optional=True)
    user = Config.from_path(user_config_path, optional=True)

    config.merge(site, mergers=mergers)
    config.merge(user, mergers=mergers)

    # Validate the config data.

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
        **plugin_schemas,
    })

    try:
        schema(config.data)
    except Invalid as err:
        warn(err)

    return config

