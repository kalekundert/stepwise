#!/usr/bin/env python3

import byoc
from stepwise import StepwiseCommand, ProtocolIO, replace_text
from inform import fatal

class Swap(StepwiseCommand):
    """\
Rearrange the order of the protocol steps.

Usage:
    stepwise swap [--] <indices>...

Arguments:
    <indices>
        Each index number refers to the current index of a step.  Indices count 
        from one, and may be negative to count backwards from the last step of 
        the protocol.  In order to prevent negative numbers from being confused 
        with options, you may need to precede them with `--`.  Zero is not a 
        valid index.

        The order of the indices specifies the new order that the steps should 
        go in.  Steps between the earliest and latest of the specified indices 
        will be overwritten by the new order.  It is possible to drop steps 
        from the protocol in this way, e.g. the indices `1 3` would drop the 
        second step, although the `skip` command does this better.

        For example: the indices `-1 -2` would swap the last two steps.
"""
    __config__ = [
            byoc.DocoptConfig,
    ]

    indices = byoc.param('<indices>', cast=lambda xs: [int(x) for x in xs])

    def main(self):
        byoc.load(self)

        io = ProtocolIO.from_stdin()
        if io.errors:
            fatal("protocol has errors, not making substitution.")
        if not io.protocol:
            fatal("no protocol specified.")

        p = io.protocol
        n = len(p.steps)

        indices = [
                i - 1 if i > 0 else n + i
                for i in self.indices
        ]
        new_steps = [
                p.steps[i]
                for i in indices
        ]
        p.steps = (
                p.steps[:min(indices)] +
                new_steps +
                p.steps[max(indices)+1:]
        )
        io.to_stdout(self.force_text)
