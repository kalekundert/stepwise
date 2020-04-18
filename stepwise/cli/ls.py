#!/usr/bin/env python3

"""\
List protocols known to stepwise.

Usage:
    stepwise ls [-d] [-p] [<protocol>]

Options:
    -d --dirs
        Show the directories that will be searched for protocols, rather than 
        the protocols themselves.

    -p --paths
        Don't organize paths by directory.
"""

import docopt
from itertools import groupby
from operator import itemgetter
from stepwise import Library, load_config
from .main import command

@command
def ls():
    args = docopt.docopt(__doc__)
    config = load_config()

    library = Library()
    entries = library.find_entries(args['<protocol>'])
    indent = '' if args['--paths'] else '  '

    for collection, entry_group in groupby(entries, lambda x: x.collection):
        if not args['--paths']:
            print(collection.name)
        if args['--dirs']:
            continue

        for entry in entry_group:
            print(indent + entry.name)

        if not args['--paths']:
            print()

