#!/usr/bin/env python3

"""\
Edit the specified protocol using $EDITOR.

Usage:
    stepwise edit <protocol>
"""

import os
import docopt
import subprocess as subp
from ..protocol import find_protocol_path

def main():
    args = docopt.docopt(__doc__)
    path = find_protocol_path(args['<protocol>'])
    cmd = os.environ['EDITOR'], path['path']
    subp.run(cmd)

