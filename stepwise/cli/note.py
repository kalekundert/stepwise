#!/usr/bin/env python3

import sys, re, textwrap
import appcli
from inform import fatal
from operator import not_
from stepwise import StepwiseCommand, ProtocolIO, pre

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
            appcli.DocoptConfig,
    ]

    text = appcli.param('<footnote>')
    where = appcli.param('<where>', default=None)
    wrap = appcli.param('--no-wrap', cast=not_, default=True)

    def main(self):
        appcli.load(self)

        io = ProtocolIO.from_stdin()
        if io.errors:
            fatal("protocol has errors, not adding footnote.")
        if not io.protocol:
            fatal("no protocol specified.")

        p = io.protocol
        footnote = self.text if self.wrap else pre(self.text)
        pattern = re.compile(self.where or '(?=[.:])')

        try:
            p.insert_footnotes(footnote, pattern=pattern)
        except ValueError:
            fatal(f"pattern {pattern!r} not found in protocol.")

        p.merge_footnotes()

        io.to_stdout(self.force_text)
