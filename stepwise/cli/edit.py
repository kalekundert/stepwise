#!/usr/bin/env python3

import os
import byoc
import subprocess as subp
from stepwise import StepwiseCommand, Library

class Edit(StepwiseCommand):
    """\
Edit the specified protocol using $EDITOR.

Usage:
    stepwise edit <protocol>
"""
    __config__ = [
            byoc.DocoptConfig,
    ]
    protocol = byoc.param('<protocol>')


    def main(self):
        byoc.load(self)

        library = Library()
        entry = library.find_entry(self.protocol)
        cmd = os.environ['EDITOR'], entry.path
        subp.run(cmd)

