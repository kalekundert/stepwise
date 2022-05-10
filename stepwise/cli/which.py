#!/usr/bin/env python3

import byoc
from stepwise import StepwiseCommand, Library

class Which(StepwiseCommand):
    """\
Show the full path to the specified protocol.

Usage:
    stepwise which <protocol>
"""
    __config__ = [
            byoc.DocoptConfig,
    ]
    protocol = byoc.param('<protocol>')

    def main(self):
        byoc.load(self)

        library = Library()
        entries = library.find_entries(self.protocol)

        for entry in entries:
            print(entry.path)

