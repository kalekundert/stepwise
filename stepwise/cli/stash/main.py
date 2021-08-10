#!/usr/bin/env python3

import appcli
from inform import fatal, parse_range
from stepwise import StepwiseCommand, ProtocolIO, read_merge_write_exit

def parse_id(id):
    if id is None:
        return None
    try:
        return int(id)
    except ValueError:
        raise UsageError(f"Expected an integer id, not {id!r}.")

def parse_ids(ids):
    if ids is None:
        return []

    return parse_range(ids, cast=parse_id)
        
def parse_categories(categories):
    if categories is None:
        return []
    return [x.strip() for x in categories.split(',')]
  
def parse_dependencies(dependencies):
    return parse_range(dependencies) if dependencies else []

def protocol_from_stdin():
    io = ProtocolIO.from_stdin()
    if io.errors:
        fatal("protocol has errors, not stashing.")
    return io.protocol

class Stash(StepwiseCommand):
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

    __config__ = [
            appcli.DocoptConfig,
    ]

    add = appcli.param(default=None)
    ls = appcli.param(default=None)
    edit = appcli.param(default=None)
    peek = appcli.param(default=None)
    pop = appcli.param(default=None)
    drop = appcli.param(default=None)
    restore = appcli.param(default=None)
    clear = appcli.param(default=None)
    reset = appcli.param(default=None)

    id = appcli.param(
            '<id>',
            default=None,
            cast=parse_id,
    )
    ids = appcli.param(
            '<ids>',
            default=[],
            cast=parse_ids,
    )
    message = appcli.param(
            '--message',
            default=None,
    )
    categories = appcli.param(
            '--categories',
            default=[],
            cast=parse_categories,
    )
    dependencies = appcli.param(
            '--dependencies',
            default=[],
            cast=parse_dependencies,
    )
    show_dependents = appcli.param('--show-dependents', default=False)
    show_all = appcli.param('--all', default=False)
    explicit = appcli.param('--explicit', default=False)

    def main(self):
        appcli.load(self)

        # Defer importing `sqlalchemy`.
        from . import model

        with model.open_db() as db:
            if self.ls:
                model.list_protocols(
                        db,
                        categories=self.categories,
                        dependencies=self.dependencies,
                        include_dependents=self.show_dependents,
                        include_complete=self.show_all,
                )

            elif self.edit:
                model.edit_protocol(
                        db, self.id,
                        protocol=protocol_from_stdin(),
                        message=self.message,
                        categories=self.categories,
                        dependencies=self.dependencies,
                        explicit=self.explicit,
                )

            elif self.peek:
                row = model.peek_protocol(db, self.id)
                self.show_protocol(row)

            elif self.pop:
                row = model.pop_protocol(db, self.id)
                self.show_protocol(row)

            elif self.drop:
                model.drop_protocols(db, self.ids)

            elif self.restore:
                model.restore_protocols(db, self.ids)

            elif self.clear:
                model.clear_protocols(db)

            elif self.reset:
                model.reset_protocols(db)

            else:
                protocol = protocol_from_stdin()

                if not protocol:
                    if self.add: fatal("no protocol specified.")
                    model.list_protocols(
                            db,
                            categories=self.categories,
                            dependencies=self.dependencies,
                            include_dependents=self.show_dependents,
                            include_complete=self.show_all,
                    )
                else:
                    model.add_protocol(
                            db, protocol,
                            message=self.message,
                            categories=self.categories,
                            dependencies=self.dependencies,
                    )

    def show_protocol(self, row):
        read_merge_write_exit(
                row.io,
                quiet=self.quiet,
                force_text=self.force_text,
        )

