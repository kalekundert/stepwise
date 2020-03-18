#!/usr/bin/env python3

"""\
Save protocols for later use.

Usage:
    stepwise stash [add] [-c <categories>] [-m <message>]
    stepwise stash list [-c <categories>]
    stepwise stash peek [<id>]
    stepwise stash pop [<id>]
    stepwise stash drop [<id>]
    stepwise stash clear

Commands:
    [add]
        Read a protocol from stdin and save it for later use.  This command is 
        meant to be used at the end of pipelines, like `stepwise go`.

    list
        Display any protocols that have saved for later use.  

    peek [<id>]
        Write the indicated protocol to stdout, but do not remove it from the 
        stash.  The <id> for each stashed protocol is displayed by the `list` 
        command.  If only one protocol is stashed, the <id> does not need to be 
        specified.

    pop [<id>]
        Write the indicated protocol to stdout and remove it from the stash.  
        See the `peek` command for a description of the <id> argument.

    drop [<id>]
        Remove the indicated protocol from the stash.  See the `peek` command 
        for a description of the <id> argument.

    clear
        Remove all stashed protocols.

Options:
    -c --categories <str>
        A comma-separated list of categories that apply to a protocol.  The 
        categories can be whatever you want, e.g. names of projects, 
        collaborations, techniques, etc.

        Use this option when adding a protocol to specify which categories it 
        belongs to.  Use this option when listing stashed protocols to display 
        only protocols belonging to the specified categories.

    -m --message <text>
        A brief description of the protocol to help you remember what it's for. 
        The message will be displayed by the `list` command.

Note that stashed protocols are not meant to be stored indefinitely.  It is 
possible that upgrading either stepwise or python could corrupt the stash.
"""

import docopt
import pickle
import sqlite3
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from tabulate import tabulate
from inform import Error, fatal
from ..protocol import ProtocolIO
from ..config import config_dirs

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, DateTime, String, PickleType
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator

Base = declarative_base()

class CategoriesType(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        return ','.join(value) if value else None

    def process_result_value(self, value, dialect):
        return parse_categories(value)

class Stash(Base):
    __tablename__ = 'stash'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    categories = Column(CategoriesType)
    message = Column(String)
    protocol = Column(PickleType)

class StashError(Error):
    pass

class UserInputError(StashError):
    pass

def main():
    args = docopt.docopt(__doc__)

    with open_db() as db:
        if args['list']:
            list_protocols(db, parse_categories(args['--categories']))

        elif args['peek']:
            peek_protocol(db, parse_id(args['<id>']))

        elif args['pop']:
            pop_protocol(db, parse_id(args['<id>']))

        elif args['drop']:
            drop_protocol(db, parse_id(args['<id>']))

        elif args['clear']:
            clear_protocols(db)

        else:
            io = ProtocolIO.from_stdin()
            if io.errors:
                fatal("Protocol has errors, not stashing.")
            if not io.protocol:
                fatal("No protocol specified.")

            add_protocol(
                    db,
                    io.protocol,
                    parse_categories(args['--categories']),
                    args['--message'],
            )

@contextmanager
def open_db():
    path = Path(config_dirs.user_data_dir) / 'stash.sqlite'
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def list_protocols(db, categories=[]):
    stash = load_stash(db)
    categories = set(categories)

    table = []
    headers = dict(
            id="#",
            slug="Name",
            categories="Cat.",
            message="Message",
    )

    for i, row in enumerate(stash, 1):
        if not categories or categories.intersection(row.categories):
            table.append(dict(
                id=i,
                slug=row.protocol.pick_slug(),
                categories=','.join(row.categories),
                message=row.message,
            ))

    print(tabulate(table, headers))

def add_protocol(db, protocol, categories=None, message=None):
    protocol.date = None
    entry = Stash(
            timestamp=datetime.now(),
            categories=categories,
            message=message,
            protocol=protocol,
    )
    db.add(entry)

def peek_protocol(db, id=None):
    row = load_protocol(db, id)
    ProtocolIO(row.protocol).to_stdout()

def pop_protocol(db, id=None):
    row = load_protocol(db, id)
    ProtocolIO(row.protocol).to_stdout()
    db.delete(row)

def drop_protocol(db, id=None):
    row = load_protocol(db, id)
    db.delete(row)

def clear_protocols(db):
    return db.query(Stash).delete()

def load_stash(db):
    return db.query(Stash).order_by(Stash.timestamp).all()

def load_protocol(db, id):
    stash = load_stash(db)
    
    if len(stash) == 1 and id is None:
        return stash[0]

    try:
        return stash[id - 1]  # `id` is 1-indexed.
    except IndexError:
        raise UserInputError("No stashed protocol with id '{id}.'", id=id)

def parse_id(id):
    if id is None:
        return None

    try:
        return int(id)
    except ValueError:
        raise UserInputError("Expected an integer id, not {id!r}.", id=id)
        
def parse_categories(categories):
    if categories is None:
        return []
    return [x.strip() for x in categories.split(',')]
    
