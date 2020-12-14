#!/usr/bin/env python3

import os
import appcli
import subprocess as subp
from stepwise import StepwiseCommand, Library

class Edit(StepwiseCommand):
    """\
Edit the specified protocol using $EDITOR.

Usage:
    stepwise edit <protocol>
"""
    __config__ = [
            appcli.DocoptConfig(),
    ]
    protocol = appcli.param('<protocol>')


    def main(self):
        appcli.load(self)

        library = Library()
        entry = library.find_entry(self.protocol)
        cmd = os.environ['EDITOR'], entry.path
        subp.run(cmd)

