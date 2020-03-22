#!/usr/bin/env python3

"""\
Generate and display scientific protocols.

Usage:
    stepwise [-qx] <command> [<args>...]
    stepwise -h|--help
    stepwise -v|--version

Commands:
    If <command> doesn't match one of the options listed below, stepwise will 
    interpret the command as a protocol to find and display.  Any given <args> 
    will be passed to the protocol.

    {commands}

Options:
    -h --help
        Show this help message.  Use this flag with any command to get more 
        information about that command.

    -v --version
        Show version information and exit.

    -q --quiet
        Remove footnotes from the protocol.  This option only applies to the 
        `go` command and protocols.

    -x --force-text
        Force the protocol to be printed in human-readable format (rather than 
        the binary format used to communicate through pipes) even if stdout is 
        not a TTY.  This option should not be necessary in normal usage.

Examples:

    Create a protocol for cloning by inverse PCR.  First do PCR, then ligate 
    with KLD, then send the full protocol to the printer.

        $ alias sw=stepwise
        $ sw pcr | sw kld | sw go

    Show all available protocols:

        $ stepwise ls
"""

import sys
import docopt
from inform import Inform
from pkg_resources import iter_entry_points
from ..protocol import ProtocolIO
from ..errors import StepwiseError
from .. import __version__

def main():
    try:
        Inform(stream_policy='header')

        plugins = {
                x.name: x.load()
                for x in iter_entry_points('stepwise.commands')
        }
        args = docopt.docopt(
                __doc__.format(commands=list_commands(plugins)),
                version=__version__,
                options_first=True,
        )

        command = args['<command>']
        if command in plugins:
            plugins[command]()

        else:
            io_stdin = ProtocolIO.from_stdin()
            io_cli = ProtocolIO.from_library(
                    io_stdin.library,
                    args['<command>'],
                    args['<args>'],
            )
            if args['--quiet']:
                io_cli.protocol.clear_footnotes()
                
            io_stdout = ProtocolIO.merge(io_stdin, io_cli)
            io_stdout.to_stdout(args['--force-text'])
            sys.exit(io_stdout.errors)

    except StepwiseError as err:
        err.terminate()

def list_commands(plugins):
    """
    Return a nicely formatted list of all the subcommands installed on this 
    system, to incorporate into the usage text.
    """
    from shutil import get_terminal_size
    from textwrap import shorten
    from inspect import getmodule

    indent, pad = 4, 2
    max_width = get_terminal_size().columns - 1
    max_command = max(len(x) for x in plugins) + 1
    max_brief = max_width - max_command - pad

    # Make the table.

    desc = ''
    row = f'{" " * indent}{{:<{max_command}}}{" " * pad}{{}}\n'

    for command, plugin in plugins.items():
        usage = plugin.__doc__ or getmodule(plugin).__doc__ or "No summary"
        brief = usage.strip().split('\n')[0]
        desc += row.format(
                command + ':',
                shorten(brief, width=max_brief, placeholder='...'),
        )

    return desc.strip()


