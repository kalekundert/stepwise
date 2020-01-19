#!/usr/bin/env python3

import sys
import functools
import subprocess as subp
from docopt import docopt
from pathlib import Path
from pkg_resources import iter_entry_points
from .protocol import load, merge, Protocol, UserError
from .printer import print_protocol, get_default_printer
from .config import config, user_config_path, site_config_path
from . import __version__

def main():
    """\
Generate and display scientific protocols.

Usage:
    stepwise <command>
    stepwise -h|--help
    stepwise -v|--version

Options:
    -h --help
        Show this help message.  Use this flag with any command to get more 
        information about that command.

    -v --version
        Show version information and exit.

Examples:

    Create a protocol for cloning by inverse PCR.  First do PCR, then ligate 
    with KLD, then send the full protocol to the printer.

        $ alias sw=stepwise
        $ sw pcr | sw kld | sw lpr

    Show all possible commands:

        $ stepwise ls
"""
    try:
        args = docopt(
                main.__doc__,
                sys.argv[1:2],
                version=__version__,
        )
        command = args['<command>']
        plugins = {
                x.name: x
                for x in iter_entry_points('stepwise.commands')
        }

        if command in plugins:
            plugins[command].load()()

        else:
            # Parse any previous protocols from stdin.
            prev_protocol = Protocol.parse_stdin()

            # Load the protocol associated with this command.
            curr_protocol = load(sys.argv[1], sys.argv[2:])
            curr_protocol.set_current_date()
            curr_protocol.set_current_command()

            # Combine the two protocols and output the result to stdout.
            merged_protocol = merge(prev_protocol, curr_protocol)
            print(merged_protocol)

    except UserError as err:
        print("Error:", err, file=sys.stderr)
        sys.exit(1)

    except subp.CalledProcessError as err:
        sys.exit(err.returncode)
    
def ls():
    """\
List protocols known to stepwise.

Usage:
    stepwise ls [-d|--dirs]

Options:
    -d --dirs
        Show the directories that will be search for protocols, rather than the 
        protocols themselves.
"""
    from .protocol import find_protocol_names, find_protocol_dirs

    args = docopt(ls.__doc__)

    if args['--dirs']:
        names = find_protocol_dirs()
    else:
        names = find_protocol_names()

    for name in names:
        print(name)

def lpr():
    usage = f"""\
Write the protocol to a file and print a paper copy.

Usage:
    stepwise lpr [options]

Options:
    -f --force
        Overwrite existing files.

    -P --no-print
        Only write the protocol to a file and don't attempt to print it.

    -p --printer NAME
        Print to the specified printer, rather than the system default.  The 
        current system default is: {get_default_printer()}

Many aspects of the print job (e.g. the dimensions of the paper, the font face 
and size, etc.) can be configured in:

    {user_config_path}
    {site_config_path}
"""
    args = docopt(usage)
    protocol = Protocol.parse_stdin()

    # Write the protocol to a file.
    path = Path(f'{protocol.pick_slug()}.txt')

    if path.exists() and not args['--force']:
        print(f"'{path}' already exists, use '-f' to overwrite.")
        sys.exit(1)
        
    path.write_text(str(protocol))

    # Send to protocol to the printer.
    if not args['--no-print']:
        print_protocol(protocol, args['--printer'])


