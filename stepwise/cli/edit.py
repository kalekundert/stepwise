#!/usr/bin/env python3

"""\
Edit the specified protocol using $EDITOR.

Usage:
    stepwise edit <protocol>
"""

import os
import docopt
import subprocess as subp
from .main import command
from ..library import Library

@command
def edit():
    args = docopt.docopt(__doc__)
    library = Library()
    entry = library.find_entry(args['<protocol>'])
    cmd = os.environ['EDITOR'], entry.path
    subp.run(cmd)

