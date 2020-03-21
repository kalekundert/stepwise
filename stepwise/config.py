#!/usr/bin/env python3

import sys
from pathlib import Path
from appdirs import AppDirs
from configurator import Config
from voluptuous import Schema, All, Invalid
from gitignore_parser import parse_gitignore, rule_from_pattern

config = None
config_dirs = AppDirs("stepwise")
user_config_path = Path(config_dirs.user_config_dir) / 'conf.toml'
site_config_path = Path(config_dirs.site_config_dir) / 'conf.toml'

def load_config():
    global config
    if config: return config

    defaults = Config({
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
    user = Config.from_path(user_config_path, optional=True)
    site = Config.from_path(site_config_path, optional=True)
    config = defaults + site + user

    schema = Schema({
        'search': {
            'find': list,
            'path': list,
            'ignore': list,
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

def load_ignore_matcher():
    matcher = IgnoreMatcher()
    matcher.parse(site_config_path / 'ignore')
    matcher.parse(user_config_path / 'ignore')

    # By default, ignore files starting with '.' or '__'.
    if not matcher.matchers:
        rules = [rule_from_pattern(x) for x in ['.*', '__*']]
        matcher.matchers = [lambda p: any(r.match(p) for r in rules)]

    pprint(matcher.matchers)
    return matcher

class IgnoreMatcher:

    def __init__(self):
        self.matchers = []

    def parse(self, path):
        path = Path(path)

        if path.is_dir():
            path = path / '.stepwiseignore'

        if path.exists():
            matcher = parse_gitignore(path)
            self.matchers.append(matcher)

    def match(self, path):
        return any(x(path) for x in self.matchers)

