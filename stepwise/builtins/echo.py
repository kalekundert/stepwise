#!/usr/bin/env python3

"""\
Create a protocol directly from the command line.

This command simply prints its arguments to stdout to be directly interpreted 
as a protocol (e.g. as if it were being read as a text file).  If multiple 
arguments are given, they will be concatenated by spaces.  Any newline '\n' or 
tab '\t' characters will be expanded.  A warning will be issued if the 
resulting output cannot be parsed as a protocol.

Usage:
    echo <args>...
"""

import sys, docopt
docopt.docopt(__doc__, argv=sys.argv[0])

p = ' '.join(sys.argv[1:])
p = p.replace('\\n', '\n')
p = p.replace('\\t', '\t')
print(p)
