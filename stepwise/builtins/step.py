#!/usr/bin/env python3

"""\
Create impromptu protocols by using delimiters to separate steps specified on 
the command line.

Usage:
    custom <protocol> [-d CHAR] [-D char] [-W]

Options:
    -d --delimiter CHAR                                     [default: ;]
        The character (or characters) used to break the protocol into steps.

    -D --sub-delimiter CHAR                                 [default: ~]
        The character (or characters) used to break steps into "substeps".  
        Each substep will be prefixed with a hyphen and printed on its own 
        line.

    -W --no-wrap
        Do not automatically wrap each step to fit within the width specified 
        by the `printer.default.content_width` configuration option.
"""

from docopt import docopt
from stepwise import Protocol, Step

args = docopt(__doc__)
p = Protocol()

for step in args['<protocol>'].split(args['--delimiter']):
    body, *substeps = step.split(args['--sub-delimiter'])
    p += Step(body, substeps=substeps, wrap=not args['--no-wrap'])

print(p)
