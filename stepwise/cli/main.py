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
        Remove footnotes from the protocol, if applicable.

    -x --force-text
        Force the protocol to be printed in human-readable format (rather than 
        the binary format used to communicate through pipes) even if stdout is 
        not a TTY.  This option should not be necessary in normal usage.

Examples:

    Create a protocol for cloning by inverse PCR.  First do PCR, then ligate 
    with KLD, then print a paper copy of the full protocol:

        $ alias sw=stepwise
        $ sw pcr | sw kld | sw go

    Show all available protocols:

        $ stepwise ls
"""

import sys, inspect
import docopt
from stepwise import ProtocolIO, StepwiseError, __version__

COMMANDS = {}

def main():
    try:
        load_commands()
        args = docopt.docopt(
                __doc__.format(commands=list_commands()),
                version=__version__,
                options_first=True,
        )

        if args['<command>'] in COMMANDS:
            command = COMMANDS[args['<command>']]
            sig = inspect.signature(command)
            possible_kwargs = [
                    ('quiet', '--quiet'),
                    ('force_text', '--force-text'),
            ]
            kwargs = {
                    k1: args[k2]
                    for k1, k2 in possible_kwargs
                    if k1 in sig.parameters
            }
            sys.argv = [sys.argv[0], args['<command>'], *args['<args>']]
            command(**kwargs)

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

def command(f):
    COMMANDS[f.__name__] = f
    return f

def load_commands():
    # The order these modules are imported in defines the order that the 
    # associated subcommands will appear in the help text.
    from . import ls
    from . import which
    from . import edit
    from . import note
    from . import go
    from . import stash
    from . import metric
    from . import config

def list_commands():
    """
    Return a nicely formatted list of all the subcommands installed on this 
    system, to incorporate into the usage text.
    """
    from stepwise import tabulate
    from inform import indent

    # Make the table.

    def get_brief(func):
        doc = func.__doc__ or inspect.getmodule(func).__doc__ or "No summary"
        return doc.strip().split('\n')[0]

    rows = [
            [f'{name}:', get_brief(func)]
            for name, func in COMMANDS.items()
    ]
    table = tabulate(rows, truncate='x-', max_width=-4)
    return indent(table, leader='    ', first=-1)


