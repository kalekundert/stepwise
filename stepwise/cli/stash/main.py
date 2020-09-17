#!/usr/bin/env python3

"""\
Save protocols for later use.

Usage:
    stepwise stash [add] [-m <message>] [-c <categories>] [-d <ids>]
    stepwise stash [ls] [-a] [-c <categories>] [-d <ids> | -D]
    stepwise stash edit [<id>] [-m <message>] [-c <categories>] [-d <ids>] [-x]
    stepwise stash peek [<id>]
    stepwise stash pop [<id>]
    stepwise stash drop [<ids>]
    stepwise stash restore <ids>
    stepwise stash clear
    stepwise stash reset

Commands:
    [add]
        Read a protocol from stdin and save it for later use.  This command is 
        meant to be used at the end of pipelines (like `stepwise go`) and is 
        the default command if stdin is connected to a pipe.

    [ls]
        List protocols that have been saved for later use.  This is the default 
        command if stdin is not connected to a pipe.  By default, every stashed 
        protocol that hasn't been completed will be included in the output.

    edit [<id>]
        Provide new annotations (e.g. message, categories, dependencies) for 
        the indicated protocol.  If stdin is connected to a pipe, it will be 
        read to update the protocol itself.

    peek [<id>]
        Display the indicated protocol, but do not mark it as completed (i.e. 
        continue to show it with `stash ls`).

    pop [<id>]
        Display the indicated protocol, then mark it as completed (i.e. stop 
        showing it with `stash ls`).

    drop [<ids>]
        Mark the indicated protocols as completed.

    restore <ids>
        Mark the indicated protocols as not completed.

    clear
        Mark every stashed protocol as completed.

    reset
        Permanently delete every completed protocol, and reset the ID numbers 
        to count consecutively from 1.  Be careful before running this command; 
        it is destructive and cannot be undone!

Arguments:
    <id>
        A number that identifies which stashed protocol to use.  The <id> for 
        each stashed protocol is displayed by the `ls` command.  If only one 
        protocol is stashed, the <id> does not need to be specified.  For 
        commands that accept multiple ids (i.e. <ids>), use commas to separate 
        individual ids and hyphens to specify ranges of ids.

Options:
    -m --message <text>
        A brief description of the protocol to help you remember what it's for. 
        The message will be displayed by the `list` command.

    -c --categories <str>
        A comma-separated list of categories that apply to a protocol.  The 
        categories can be whatever you want, e.g. names of projects, 
        collaborations, techniques, etc.

        Use this option when adding/editing a protocol to specify which 
        categories it belongs to.  Use this option when listing stashed 
        protocols to display only protocols belonging to the specified 
        categories.

    -d --dependencies <ids>
        A comma-separated list of the id numbers of other stashed protocols 
        that must be completed before this one.

        Use this option when adding/editing a protocol to specify its 
        dependencies.  Use this option when listing protocols to view only 
        those protocols that depend on the specified ids.

    -D --show-dependents
        Include protocols that have incomplete dependencies when displaying the 
        stash.

    -a --all
        List all stashed protocols, complete and incomplete.  This can be 
        useful if you want to refer back to an old protocol.

    -x --explicit
        When editing a stashed protocol, indicate that any annotations that are 
        not specified (e.g. message, categories, dependencies) should be unset.  
        This differs from the default, where only values that are specified are 
        updated.

Note that stashed protocols are not meant to be stored indefinitely.  It is 
possible (although hopefully unlikely) that upgrading either stepwise or 
python could corrupt the stash.
"""

import docopt
from inform import fatal
from stepwise import ProtocolIO
from ..main import command

@command
def stash(quiet, force_text):
    # Defer importing `sqlalchemy`.
    from . import model

    args = docopt.docopt(__doc__)
    id = model.parse_id(args['<id>'])
    ids = model.parse_ids(args['<ids>'])
    message = args['--message']
    categories = model.parse_categories(args['--categories'])
    dependencies = model.parse_dependencies(args['--dependencies'])

    with model.open_db() as db:
        if args['ls']:
            model.list_protocols(
                    db,
                    categories=categories,
                    dependencies=dependencies,
                    include_dependents=args['--show-dependents'],
                    include_complete=args['--all'],
            )

        elif args['edit']:
            model.edit_protocol(
                    db, id,
                    protocol=_protocol_from_stdin(),
                    message=message,
                    categories=categories,
                    dependencies=dependencies,
                    explicit=args['--explicit'],
            )

        elif args['peek']:
            model.peek_protocol(
                    db, id,
                    quiet=quiet,
                    force_text=force_text,
            )

        elif args['pop']:
            model.pop_protocol(
                    db, id,
                    quiet=quiet,
                    force_text=force_text,
            )

        elif args['drop']:
            model.drop_protocols(db, ids)

        elif args['restore']:
            model.restore_protocols(db, ids)

        elif args['clear']:
            model.clear_protocols(db)

        elif args['reset']:
            model.reset_protocols(db)

        else:
            protocol = _protocol_from_stdin()

            if not protocol:
                if args['add']: fatal("no protocol specified.")
                model.list_protocols(
                        db,
                        categories=categories,
                        dependencies=dependencies,
                        include_dependents=args['--show-dependents'],
                        include_complete=args['--all'],
                )
            else:
                model.add_protocol(
                        db, protocol,
                        message=message,
                        categories=categories,
                        dependencies=dependencies,
                )

def _protocol_from_stdin():
    io = ProtocolIO.from_stdin()
    if io.errors:
        fatal("protocol has errors, not stashing.")
    return io.protocol

