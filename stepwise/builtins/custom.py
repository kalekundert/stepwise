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
from stepwise import Protocol, load_config
import textwrap

def format_steps(steps, wrap, delim, subdelim):
    step_strs = steps.split(delim)
    max_width = load_config().printer.default.content_width
    prefix_width = len(str(len(step_strs))) + 2
    wrap_width = max_width - prefix_width if wrap else False

    return [
            format_step(x, wrap_width, subdelim)
            for x in steps.split(delim)
    ]

def format_step(step, wrap_width, subdelim):
    step, *substeps = step.split(subdelim)

    step_fmt = textwrap.fill(step, width=wrap_width) if wrap_width else step
    substeps_fmt = [
            format_substep(x, wrap_width)
            for x in substeps
    ]

    br = '\n'
    return f'{step_fmt}{br}{br}{br.join(substeps_fmt)}'

def format_substep(substep, wrap_width):
    if not wrap_width:
        return '- ' + substep

    substep = textwrap.wrap(substep, width=wrap_width - 2)
    return '- ' + '\n  '.join(substep)

if __name__ == '__main__':
    args = docopt(__doc__)

    protocol = Protocol()
    protocol.steps = format_steps(
            args['<protocol>'],
            not args['--no-wrap'],
            args['--delimiter'],
            args['--sub-delimiter'],
    )
    print(protocol)
