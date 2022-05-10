#!/usr/bin/env python3

import byoc
from stepwise import StepwiseCommand, ProtocolIO, replace_text
from inform import fatal

class Substitute(StepwiseCommand):
    """\
Edit text in a previous step of the protocol.

Usage:
    stepwise sub <pattern> <replace> [-n <count>]

Arguments:
    <pattern>
        A regular expression identifying the text to replace.  The steps will 
        be searched in reverse order for this pattern, but the text comprising 
        each step will be search from front to back.

    <replace>
        The string to 

Options:
    -n <int>    [default: 1]
        The maximum number of replacements to make.
"""
    __config__ = [
            byoc.DocoptConfig,
    ]

    pattern = byoc.param('<pattern>')
    replace = byoc.param('<replace>', default=None)
    n = byoc.param('-n', cast=int)

    def main(self):
        byoc.load(self)

        io = ProtocolIO.from_stdin()
        if io.errors:
            fatal("protocol has errors, not making substitution.")
        if not io.protocol:
            fatal("no protocol specified.")

        p = io.protocol
        i = len(p.steps) - 1
        n_remaining = self.n

        while (i >= 0) and n_remaining:
            state = {}
            step = replace_text(
                    p.steps[i], self.pattern, self.replace,
                    count=n_remaining,
                    state=state,
            )
            if state['n'] > 0:
                p.steps[i] = step

            i -= 1
            n_remaining -= state['n']

        if n_remaining == self.n:
            fatal(f"pattern {self.pattern!r} not found in protocol.")

        io.to_stdout(self.force_text)
