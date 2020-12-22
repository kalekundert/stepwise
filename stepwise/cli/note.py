#!/usr/bin/env python3

import sys, re, textwrap
import appcli
from inform import fatal
from stepwise import StepwiseCommand, ProtocolIO, Footnote

class Note(StepwiseCommand):
    """\
Insert a footnote into a protocol.

This command can be used to elaborate on a previous step in a protocol.  The 
footnote will be numbered automatically, and any subsequent footnotes will be 
renumbered accordingly.

Usage:
    stepwise note <footnote> [<where>] [-W]

Arguments:
    <footnote>
         The text of the footnote to add.

    <where>
        A regular expression indicating where the footnote reference should be 
        placed.  The steps will be searched in reverse order for this pattern, 
        and the reference will be inserted directly after the first matching 
        substring found.

        You can use a lookahead assertion to match text that will appear after 
        the reference, e.g. '(?=:)' will place a reference before the first 
        colon that is found.  By default the footnote will be placed just 
        before the first period (.) or colon (:) in the previous step.

Options:
    -W --no-wrap
        Do not automatically line-wrap the given message.  The default is to 
        wrap the message to fit within the width specified by the 
        `printer.default.content_width` configuration option.
"""
    __config__ = [
            appcli.DocoptConfig(),
    ]

    text = appcli.param('<footnote>')
    where = appcli.param('<where>', default=None)
    wrap = appcli.param('--no-wrap', cast=lambda x: not x)

    def main(self):
        appcli.load(self)

        footnote = Footnote(self.text, wrap=self.wrap)
        pattern = re.compile(self.where or '(?=[.:])')

        io = ProtocolIO.from_stdin()
        if io.errors:
            fatal("protocol has errors, not adding footnote.")
        if not io.protocol:
            fatal("no protocol specified.")

        p = io.protocol

        # The protocol could have footnotes in any order, so number this 
        # footnote based on `max() + 1` instead of `len() + 1` or similar.
        ref = max(p.footnotes, default=0) + 1
        ref_str = f'[{ref}]'

        for i, step in reversed(list(enumerate(p.steps))):
            if m := pattern.search(step):
                j = m.end()
                if step[j - 1] != ' ':
                    ref_str = ' ' + ref_str

                p.steps[i] = step[:j] + ref_str + step[j:]
                p.footnotes[ref] = footnote
                break
        else:
            fatal(f"pattern {pattern!r} not found in protocol.")

        io.to_stdout(self.force_text)
