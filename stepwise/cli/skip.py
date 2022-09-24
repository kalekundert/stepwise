#!/usr/bin/env python3

import byoc
from stepwise import StepwiseCommand, ProtocolIO, replace_text
from inform import fatal, plural

class Skip(StepwiseCommand):
    """\
Skip one or more of the steps previously added to the protocol.

This can be useful if you need to customize a step beyond what a script 
normally allows.  For example, maybe you want to optimize the duration of a 
reaction by setting up a reaction and quenching aliquots at defined intervals.  
With this command, you can use the reaction protocol to setup the reaction, 
remove the normal reaction incubation step, and replace it with this bespoke 
quenching step.

Usage:
    stepwise skip [--] [<steps>]

Arguments:
    <steps>
        The indices of the steps to skip.  The first step in the protocol is 1, 
        the second is 2, etc.  In other words, indexing is one-based.  Index 
        number can also be negative: the last step is -1, the second-to-last 
        step is -2, etc.  In order to prevent negative numbers from being 
        confused with options, you may need to precede them with `--`.

        You can specify an inclusive range of steps to skip using the following 
        syntax: `<first>:<last>`.  For example, `1:2` would skip the first two 
        steps, `-2:-1` would skip the last two steps, etc.  Both the indices 
        are optional, and default to the first and last step respectively when 
        not specified.  So the above examples could be more succinctly 
        specified as `:2` and `-2:`.

        If no steps are specified, only the last step will skipped.
"""
    __config__ = [byoc.DocoptConfig]
    steps = byoc.param('<steps>', default=None)

    def main(self):
        byoc.load(self)

        io = ProtocolIO.from_stdin()
        if io.errors:
            fatal("protocol has errors, not skipping.")
        if not io.protocol:
            fatal("no protocol specified.")

        p = io.protocol
        i = parse_indices(self.steps, len(p.steps)) if self.steps else -1
        del p.steps[i]

        io.to_stdout(self.force_text)

def parse_indices(steps_str, n_steps):
    fields = steps_str.split(':')

    if len(fields) == 1:
        return parse_index(fields[0], n_steps)

    if len(fields) == 2:
        i = parse_index(x, n_steps)     if (x := fields[0].strip()) else 0
        j = parse_index(x, n_steps) + 1 if (x := fields[1].strip()) else n_steps
        return slice(i, j)

    raise ValueError(f"expected `<index>` or `<first>:<last>`, not: {steps_str!r}")

def parse_index(step_str, n_steps):
    """
    Return a positive, 0-based index corresponding to the given 1-based index 
    string.
    """
    if n_steps == 0:
        raise ValueError("no previous steps")

    i = int(step_str)

    if i > 0:
        if i > n_steps:
            raise ValueError(f"no step with index {step_str}: only {plural(n_steps):# step/s}")
        return i - 1

    if i < 0:
        i += n_steps
        if i < 0:
            raise ValueError(f"no step with index {step_str}: only {plural(n_steps):# step/s}")
        return i

    raise ValueError("no step with index 0: indexing starts at 1")

