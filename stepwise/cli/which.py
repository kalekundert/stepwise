#!/usr/bin/env python3

"""\
Show the full path to the specified protocol.

Usage:
    stepwise which <protocol>
"""

import docopt
from ..protocol import find_protocol_paths

def main():
    args = docopt.docopt(__doc__)
    paths = find_protocol_paths(args['<protocol>'])

    for path in paths:
        print(path['path'])

