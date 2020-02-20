#!/usr/bin/env python3

import sys
import os
import functools
import subprocess as subp
from docopt import docopt
from pathlib import Path
from inform import Inform
from pkg_resources import iter_entry_points
from .protocol import Protocol, ProtocolIO
from .printer import print_protocol, get_default_printer
from .config import config, user_config_path, site_config_path
from .utils import *
from . import __version__

def main():
    """\
Generate and display scientific protocols.

Usage:
    stepwise [-qx] <command> [<args>...]
    stepwise -h|--help
    stepwise -v|--version

Options:
    -h --help
        Show this help message.  Use this flag with any command to get more 
        information about that command.

    -v --version
        Show version information and exit.

    -q --quiet
        Remove footnotes from the protocol.  This option only applies if the 
        command specifies a protocol to display.

    -x --force-text
        Force the protocol to be printed in human-readable format (rather than 
        the binary format used to communicate through pipes) even if stdout is 
        not a TTY.  This option should not be necessary in normal usage.

Examples:

    Create a protocol for cloning by inverse PCR.  First do PCR, then ligate 
    with KLD, then send the full protocol to the printer.

        $ alias sw=stepwise
        $ sw pcr | sw kld | sw lpr

    Show all possible commands:

        $ stepwise ls
"""
    try:
        Inform(stream_policy='header')
        args = docopt(
                main.__doc__,
                version=__version__,
                options_first=True,
        )

        command = args['<command>']
        plugins = {
                x.name: x
                for x in iter_entry_points('stepwise.commands')
        }

        if command in plugins:
            plugins[command].load()()

        else:
            io_stdin = ProtocolIO.from_stdin()
            io_cli = ProtocolIO.from_cli(
                    args['<command>'],
                    args['<args>'],
                    quiet=args['--quiet'],
                    show_error_header=not io_stdin.errors,
            )
            io_stdout = ProtocolIO.merge(io_stdin, io_cli)
            io_stdout.to_stdout(args['--force-text'])
            sys.exit(io_stdout.errors)

    except StepwiseError as err:
        err.terminate()


def ls():
    """\
List protocols known to stepwise.

Usage:
    stepwise ls [-d|--dirs] [-p|--paths] [<protocol>]

Options:
    -d --dirs
        Show the directories that will be search for protocols, rather than the 
        protocols themselves.

    -p --paths
        Don't organize paths by directory.
"""
    from itertools import groupby
    from operator import itemgetter
    from .protocol import find_protocol_paths, find_protocol_dirs

    args = docopt(ls.__doc__)

    def by_type(x):
        type_order = {
                'parent': 1,
                'path': 2,
                'plugin': 3,
        }
        return type_order[x['type']]

    def by_name(x):
        if x['type'] == 'parent':
            return -len(x['name'])

        if x['type'] == 'path':
            return config.search.path.data.index(str(x['dir'])),

        return x['name']

    def by_relpath(x):
        return x['relpath']

    def by_type_then_name_then_relpath(x):
        return by_type(x), by_name(x), by_relpath(x)

    paths = find_protocol_paths(args['<protocol>'])
    paths = sorted(paths, key=by_type_then_name_then_relpath)
    indent = '' if args['--paths'] else '  '

    for type, dirs in groupby(paths, by_type):
        for name, subpaths in groupby(dirs, itemgetter('name')):

            if not args['--paths']:
                print(name)
            if args['--dirs']:
                continue

            for path in subpaths:
                print(f'{indent}{path["relpath"].with_suffix("")}')

            if not args['--paths']:
                print()

def edit():
    """\
Edit the specified protocol using $EDITOR.

Usage:
    stepwise edit <protocol>
"""
    from .protocol import find_protocol_path

    args = docopt(edit.__doc__)
    path = find_protocol_path(args['<protocol>'])
    cmd = os.environ['EDITOR'], path['path']
    subp.run(cmd)

def which():
    """\
Show the full path to the specified protocol.

Usage:
    stepwise which <protocol>
"""
    from .protocol import find_protocol_paths

    args = docopt(which.__doc__)
    paths = find_protocol_paths(args['<protocol>'])

    for path in paths:
        print(path['path'])

def lpr():
    usage = f"""\
Write the protocol to a file and print a paper copy.

Usage:
    stepwise lpr [options]

Options:
    -f --force
        Overwrite existing files.

    -F --no-file
        Only print the protocol and don't write it to a file.

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
    io = ProtocolIO.from_stdin()

    # Write the protocol to a file.
    if not args['--no-file']:
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


