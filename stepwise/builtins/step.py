#!/usr/bin/env python3

"""\
Add custom steps to a protocol directly from the command line.

Usage:
    step <text> [-d CHAR] [-D char] [-W]

Options:
    -d --delimiter CHAR                                 [default: ~]
        The character (or characters) used to break steps into "substeps".  
        Each substep will be prefixed with a hyphen and printed on its own 
        line.  You can also create sub-substeps by repeating the delimiter 
        twice (e.g. '~~'), sub-sub-substeps by repeating it three times, etc.

    -W --no-wrap
        Do not automatically wrap the text to fit within the width specified 
        by the `printer.default.content_width` configuration option.
"""

from docopt import docopt
from stepwise import Protocol, pl, ul, pre

args = docopt(__doc__)
p = Protocol()

wrap = pre if args['--no-wrap'] else str
body, *substeps = args['<text>'].split(args['--delimiter'])
body = wrap(body)
substeps = map(wrap, substeps)

p += pl(body, ul(*substeps))

p.print()
