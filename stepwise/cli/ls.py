#!/usr/bin/env python3

"""\
List protocols known to stepwise.

Usage:
    stepwise ls [-d|--dirs] [-p|--paths] [<protocol>]

Options:
    -d --dirs
        Show the directories that will be search for protocols, rather than the 
        protocols themselves.

    -p --paths
        Don't organize paths by directory.
"""

import docopt
from itertools import groupby
from operator import itemgetter
from ..protocol import find_protocol_paths, find_protocol_dirs
from ..config import config

def main():
    args = docopt.docopt(__doc__)

    def by_type(x):
        type_order = {
                'parent': 1,
                'path': 2,
                'plugin': 3,
        }
        return type_order[x['type']]

    def by_name(x):
        if x['type'] == 'parent':
            return -len(x['name'])

        if x['type'] == 'path':
            return config.search.path.data.index(str(x['dir'])),

        return x['name']

    def by_relpath(x):
        return x['relpath']

    def by_type_then_name_then_relpath(x):
        return by_type(x), by_name(x), by_relpath(x)

    paths = find_protocol_paths(args['<protocol>'])
    paths = sorted(paths, key=by_type_then_name_then_relpath)
    indent = '' if args['--paths'] else '  '

    for type, dirs in groupby(paths, by_type):
        for name, subpaths in groupby(dirs, itemgetter('name')):

            if not args['--paths']:
                print(name)
            if args['--dirs']:
                continue

            for path in subpaths:
                print(f'{indent}{path["relpath"].with_suffix("")}')

            if not args['--paths']:
                print()

