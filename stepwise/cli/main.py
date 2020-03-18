#!/usr/bin/env python3

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

import sys
import docopt
from inform import Inform
from pkg_resources import iter_entry_points
from ..protocol import ProtocolIO
from ..utils import StepwiseError
from .. import __version__

def main():
    try:
        Inform(stream_policy='header')
        args = docopt.docopt(
                __doc__,
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

