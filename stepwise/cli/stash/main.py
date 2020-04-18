#!/usr/bin/env python3

"""\
Save protocols for later use.

Usage:
    stepwise stash [add] [-c <categories>] [-m <message>]
    stepwise stash [ls] [-c <categories>]
    stepwise stash label [<id>] [-c <categories>] [-m <message>]
    stepwise stash peek [<id>]
    stepwise stash pop [<id>]
    stepwise stash drop [<id>]
    stepwise stash clear

Commands:
    [add]
        Read a protocol from stdin and save it for later use.  This command is 
        meant to be used at the end of pipelines, like `stepwise go`, and is 
        the default command if stdin is connected to a pipe.

    [ls]
        Display any protocols that have saved for later use.  This is the 
        default command if stdin is not connected to a pipe.

    label [<id>]
        Provide new annotations (e.g. message, categories) for the indicated 
        protocol.  Any existing annotations will be overwritten.

    peek [<id>]
        Display the indicated protocol, but do not remove it from the stash.  

    pop [<id>]
        Display the indicated protocol, then remove it from the stash.  

    drop [<id>]
        Remove the indicated protocol from the stash.

    clear
        Remove all stashed protocols.

Arguments:
    <id>
        A number that identifies which stashed protocol to use.  The <id> for 
        each stashed protocol is displayed by the `ls` command.  If only one 
        protocol is stashed, the <id> does not need to be specified.

Options:
    -m --message <text>
        A brief description of the protocol to help you remember what it's for. 
        The message will be displayed by the `list` command.

    -c --categories <str>
        A comma-separated list of categories that apply to a protocol.  The 
        categories can be whatever you want, e.g. names of projects, 
        collaborations, techniques, etc.

        Use this option when adding/labeling a protocol to specify which 
        categories it belongs to.  Use this option when listing stashed 
        protocols to display only protocols belonging to the specified 
        categories.

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
    categories = model.parse_categories(args['--categories'])
    message = args['--message']

    with model.open_db() as db:
        if args['ls']:
            model.list_protocols(db, categories)

        elif args['label']:
            model.label_protocol(db, id, categories, message)

        elif args['peek']:
            model.peek_protocol(db, id, quiet, force_text)

        elif args['pop']:
            model.pop_protocol(db, id, quiet, force_text)

        elif args['drop']:
            model.drop_protocol(db, id)

        elif args['clear']:
            model.clear_protocols(db)

        else:
            io = ProtocolIO.from_stdin()
            if io.errors:
                fatal("protocol has errors, not stashing.")

            if not io.protocol:
                if args['add']: fatal("no protocol specified.")
                model.list_protocols(db, categories)
            else:
                model.add_protocol(db, io.protocol, categories, message)

