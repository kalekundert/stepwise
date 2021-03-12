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
from stepwise import Protocol, step_from_str

args = docopt(__doc__)

p = Protocol()
p += step_from_str(
        args['<text>'], 
        delim=args['--delimiter'],
        wrap=not args['--no-wrap'],
)
p.print()
