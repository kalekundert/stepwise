#!/usr/bin/env python3

"""\
Make copies of a protocol before starting an experiment.

Usage:
    stepwise go [options]

Options:
    -o --output PATH
        The name of the file where the protocol will be recorded.  By default, 
        this name will follow the pattern: `YYYYMMDD_all_protocol_names.txt`

    -f --force
        Overwrite existing files.

    -F --no-file
        Only print the protocol and don't write it to a file.

    -P --no-print
        Only write the protocol to a file and don't attempt to print it.

    -p --printer NAME
        Print to the specified printer, rather than the system default.  The 
        current system default is: {default_printer}

Many aspects of the print job (e.g. the dimensions of the paper, the font face 
and size, etc.) can be configured in:

    {user_config_path}
    {site_config_path}
"""

import sys
import docopt
from pathlib import Path
from inform import fatal
from stepwise import ProtocolIO, print_protocol, get_default_printer
from stepwise import user_config_path, site_config_path
from .main import command

@command
def go(quiet):
    args = docopt.docopt(__doc__.format(
            default_printer=get_default_printer(),
            user_config_path=user_config_path,
            site_config_path=site_config_path,
    ))
    io = ProtocolIO.from_stdin()
    io.make_quiet(quiet)

    if not io.protocol:
        fatal("No protocol specified.")

    # Write the protocol to a file.
    if not args['--no-file']:
        if args['--output']:
            path = Path(args['--output'])
        else:
            path = Path(f'{io.protocol.pick_slug()}.txt')

        if path.exists() and not args['--force']:
            print(f"'{path}' already exists, use '-f' to overwrite.")
            sys.exit(1)
            
        path.write_text(str(io.protocol))
        print(f"Protocol saved to '{path}'")

    # Send to protocol to the printer.
    if not args['--no-print']:
        options = print_protocol(io.protocol, args['--printer'])
        print(f"Protocol sent to '{options.printer}'")

