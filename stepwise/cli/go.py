#!/usr/bin/env python3

import sys
import byoc
from pathlib import Path
from inform import fatal
from stepwise import ProtocolIO, Printer, get_default_printer_name, format_protocol, print_protocol
from stepwise.config import StepwiseCommand, StepwiseConfig
from byoc import Key, DocoptConfig
from operator import not_

class Go(StepwiseCommand):
    """\
Make copies of a protocol before starting an experiment.

Usage:
    stepwise go [-fFP] [-o PATH] [-O SUFFIX] [-p NAME]

Options:
    -o --output PATH
        The name of the file where the protocol will be recorded.  By default, 
        this name will follow the pattern: `YYYYMMDD_all_protocol_names.txt`

    -O --output-suffix SUFFIX
        A string to add to the end of the default output file name (but before 
        the default file extension).  This is useful to distinguish between two 
        protocols that would otherwise have the same name (e.g. `sw make p1` 
        and `sw make p2`).

    -f --force
        Overwrite existing files.

    -F --no-file
        Only print the protocol and don't write it to a file.

    -P --no-print
        Only write the protocol to a file and don't attempt to print it.

    -p --printer NAME       
        Print to the specified printer.  The default is: ${app.printer_name}
        You can get a list of the printer names recognized on your system by 
        running `lpstat -p -d`.

Configuration:
    The settings described below can be set in the following files:

        % for p in app.config_paths:
        ${p}
        %endfor

    go.printer:
        The printer to use if `--printer` is not specified.  If this setting is 
        not specified either, the default is taken from `lpstat -d`.  You can 
        set this default by running `lpoptions -d <printer name>`.

    printer.<name>.page_height
    printer.<name>.page_width
    printer.<name>.content_width
    printer.<name>.margin_width
        Setting that control how protocols will be formatted when using this 
        printer.

    printer.<name>.paps_flags
        Flags to pass to `paps`, the program used to convert text to 
        postscript.  These flags can control things like font, paper size, etc.  
        Note that you may have to use homebrew to install paps on Mac.

    printer.<name>.lpr_flags
        Flags to pass to `lpr`, the program used to send the print job to a 
        printer.
"""
    __config__ = [
            DocoptConfig,
            StepwiseConfig,
    ]

    output_path = byoc.param(
            Key(DocoptConfig, '--output'),
            default=None,
    )
    output_suffix = byoc.param(
            Key(DocoptConfig, '--output-suffix'),
            default='',
    )
    send_to_file = byoc.param(
            Key(DocoptConfig, '--no-file', cast=not_),
            default=True,
    )
    send_to_printer = byoc.param(
            Key(DocoptConfig, '--no-print', cast=not_),
            default=True,
    )
    overwrite_file = byoc.param(
            Key(DocoptConfig, '--force'),
            default=False,
    )
    printer_name = byoc.param(
            Key(DocoptConfig, '--printer'),
            Key(StepwiseConfig, 'go.printer'),
            default_factory=get_default_printer_name,
    )
    config_paths = byoc.config_attr()

    def main(self):
        byoc.load(self)

        io = ProtocolIO.from_stdin()
        io.make_quiet(self.quiet)

        if not io.protocol:
            fatal("No protocol specified.")

        printer = Printer(self.printer_name)

        # Write the protocol to a file.
        if self.send_to_file:
            path = Path(self.output_path or f'{io.protocol.pick_slug()}{self.output_suffix}.txt')
            if path.exists() and not self.overwrite_file:
                print(f"'{path}' already exists, use '-f' to overwrite.")
                print(f"Aborting; protocol NOT sent to printer.")
                sys.exit(1)
                
            path.write_text(format_protocol(io.protocol, printer))
            print(f"Protocol saved to '{path}'")

        # Send to protocol to the printer.
        if self.send_to_printer:
            print_protocol(io.protocol, printer)
            print(f"Protocol sent to '{printer.name}'")
