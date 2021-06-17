#!/usr/bin/env python3

import appcli
from itertools import groupby
from operator import not_
from stepwise import StepwiseCommand, Library

class List(StepwiseCommand):
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
    __config__ = [
            appcli.DocoptConfig,
    ]

    protocol = appcli.param('<protocol>', default=None)
    dirs_only = appcli.param('--dirs', default=False)
    organize_by_dir = appcli.param('--paths', cast=not_, default=True)

    def main(self):
        appcli.load(self)

        library = Library()
        entries = library.find_entries(self.protocol)
        indent = '  ' if self.organize_by_dir else ''

        for collection, entry_group in groupby(entries, lambda x: x.collection):
            if self.organize_by_dir:
                print(collection.name)
            if self.dirs_only:
                continue

            for entry in entry_group:
                print(indent + entry.name)

            if self.organize_by_dir:
                print()

