#!/usr/bin/env python3

import sys, inspect
import appcli
from stepwise import ProtocolIO, StepwiseError, __version__

class Stepwise:
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

    {0.command_briefs}

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
    __config__ = [
            appcli.DocoptConfig(version=__version__, options_first=True),
    ]

    command = appcli.param('<command>', default=None)
    args = appcli.param('<args>', default_factory=list)
    quiet = appcli.param('--quiet', default=False)
    force_text = appcli.param('--force-text', default=False)

    def __init__(self):
        from entrypoints import get_group_named
        self.commands = {
                k: v.load()()
                for k, v in get_group_named('stepwise.commands').items()
        }

    def main(self):
        appcli.load(self)

        try:
            
            if self.command in self.commands:
                app = self.commands[self.command]
                app.quiet = self.quiet
                app.force_text = self.force_text

                # Remove top-level options (e.g. --quiet) from the command 
                # line, so the subcommand doesn't have to deal with them.
                sys.argv = [sys.argv[0], self.command, *self.args]

                app.main()

            else:
                io_cli = ProtocolIO()
                if self.command:
                    io_cli = ProtocolIO.from_library(self.command, self.args)

                if self.quiet and not io_cli.errors:
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
                io_stdout.to_stdout(self.force_text)
                sys.exit(io_stdout.errors)

        except KeyboardInterrupt:
            print()
        except StepwiseError as err:
            err.terminate()

    @property
    def command_briefs(self):
        """
        Return a nicely formatted list of all the subcommands installed on this 
        system, to incorporate into the usage text.
        """
        from stepwise import tabulate
        from inform import indent

        rows = [
                [f'{name}:', getattr(app, 'brief', 'No summary.')]
                for name, app in self.commands.items()
        ]
        table = tabulate(rows, truncate='x-', max_width=-4)
        return indent(table, leader='    ', first=-1)

def main():
    app = Stepwise()
    app.main()
