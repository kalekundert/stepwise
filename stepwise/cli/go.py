#!/usr/bin/env python3

import sys
import appcli
from pathlib import Path
from inform import fatal
from stepwise import ProtocolIO, print_protocol, get_default_printer
from stepwise.config import StepwiseCommand, StepwiseConfig
from appcli import DocoptConfig, DefaultConfig
from operator import not_

class Go(StepwiseCommand):
    """\
Make copies of a protocol before starting an experiment.

Usage:
    stepwise go [-fFP] [-o PATH] [-p NAME]

Options:
    -o --output PATH
        The name of the file where the protocol will be recorded.  By default, 
        this name will follow the pattern: `YYYYMMDD_all_protocol_names.txt`

    -f --force
        Overwrite existing files.  Default

    -F --no-file
        Only print the protocol and don't write it to a file.

    -P --no-print
        Only write the protocol to a file and don't attempt to print it.

    -p --printer NAME
        Print to the specified printer.  The default is: {0.printer}

Configuration:
    The settings described below can be set in the following files:

        {0.dirs.user_config_dir}
        {0.dirs.site_config_dir}

    go.printer:
        The printer to use if --printer is not specified.  If this setting is 
        not specified either, the default is taken from `lpstat -d`.

    printer.<name>.page_height
    printer.<name>.page_width
    printer.<name>.content_width
    printer.<name>.margin_width
        Setting that control how protocols will be formatted when using this 
        printer.

    printer.<name>.paps_flags
        Flags to pass to `paps`, the program used to convert text to 
        postscript.  These flags can control things like font, paper size, etc.

    printer.<name>.lpr_flags
        Flags to pass to `lpr`, the program 
"""
    __config__ = [
            DocoptConfig(),
            StepwiseConfig(),
            DefaultConfig(
                printer=get_default_printer(),
            ),
    ]

    output_path = appcli.param(
            key={DocoptConfig: '--output'},
    )
    send_to_file = appcli.param(
            key={DocoptConfig: '--no-file'},
            cast=not_,
    )
    send_to_printer = appcli.param(
            key={DocoptConfig: '--no-print'},
            cast=not_,
    )
    overwrite_file = appcli.param(
            key={DocoptConfig: '--force'},
    )
    printer = appcli.param('--printer', 'go.printer', 'printer')

    def main(self):
        appcli.load(self)

        io = ProtocolIO.from_stdin()
        io.make_quiet(self.quiet)

        if not io.protocol:
            fatal("No protocol specified.")

        # Write the protocol to a file.
        if not self.protocol_to_file:
            path = Path(self.output_path or f'{io.protocol.pick_slug()}.txt')
            if path.exists() and not self.overwrite_file:
                print(f"'{path}' already exists, use '-f' to overwrite.")
                sys.exit(1)
                
            path.write_text(str(io.protocol))
            print(f"Protocol saved to '{path}'")

        # Send to protocol to the printer.
        if not self.protocol_to_printer:
            options = print_protocol(io.protocol, self.printer)
            print(f"Protocol sent to '{options.printer}'")
