#!/usr/bin/env python3

"""\
Generate and display scientific protocols.

Usage:
    stepwise [-qx] [<command>] [<args>...]
    stepwise -h|--help
    stepwise -v|--version

Commands:
    If <command> doesn't match one of the options listed below, stepwise will 
    interpret the command as a protocol to find and display.  If <command> is 
    not specified, a protocol will be read from stdin.  Any given <args> 
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
from ..library import ProtocolIO
from ..errors import StepwiseError
from .. import __version__

def main():
    try:
        # `pkg_resources` is slow to import, so defer until we need it.
        from pkg_resources import iter_entry_points
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
            io_cli = ProtocolIO()
            if args['<command>']:
                io_cli = ProtocolIO.from_library(
                        args['<command>'],
                        args['<args>'],
                )
            if args['--quiet'] and not io_cli.errors:
                io_cli.protocol.clear_footnotes()

            # It's more performant to load the protocol specified on the CLI 
            # before trying to read a protocol from stdin.  The reason is 
            # subtle, and has to do with the way pipes work.  For example, 
            # consider the following pipeline:
            #
            #   sw pcr ... | sw kld ...
            #
            # Although the output from `sw pcr` is input for `sw kld`, the two 
            # commands are started by the shell at the same time and run 
            # concurrently.  However, `sw kld` will be forced to wait if it 
            # tries to read from stdin before `sw pcr` has written to stdout.  
            # With this in mind, it make sense for `sw kld` to do as much work 
            # as possible before reading from stdin.

            io_stdin = ProtocolIO.from_stdin()
            io_stdout = ProtocolIO.merge(io_stdin, io_cli)
            io_stdout.to_stdout(args['--force-text'])
            sys.exit(io_stdout.errors)

    except KeyboardInterrupt:
        print()
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


