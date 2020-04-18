#!/usr/bin/env python3

"""\
Show the full path to the specified protocol.

Usage:
    stepwise which <protocol>
"""

import docopt
from .main import command
from ..library import Library

@command
def which():
    args = docopt.docopt(__doc__)
    library = Library()
    entries = library.find_entries(args['<protocol>'])

    for entry in entries:
        print(entry.path)

