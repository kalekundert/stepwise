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

import sys
import docopt
import pickle
import sqlite3
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from inform import Error, fatal
from ..library import ProtocolIO
from ..table import tabulate
from ..config import config_dirs
from ..errors import UsageError

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

def main():
    args = docopt.docopt(__doc__)
    id = parse_id(args['<id>'])
    categories = parse_categories(args['--categories'])
    message = args['--message']

    with open_db() as db:
        if args['ls']:
            list_protocols(db, categories)

        elif args['label']:
            label_protocol(db, id, categories, message)

        elif args['peek']:
            peek_protocol(db, id)

        elif args['pop']:
            pop_protocol(db, id)

        elif args['drop']:
            drop_protocol(db, id)

        elif args['clear']:
            clear_protocols(db)

        else:
            io = ProtocolIO.from_stdin()
            if io.errors:
                fatal("protocol has errors, not stashing.")

            if not io.protocol:
                if args['add']: fatal("no protocol specified.")
                list_protocols(db, categories)
            else:
                add_protocol(db, io.protocol, categories, message)

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
    from shutil import get_terminal_size
    from textwrap import shorten

    stash = load_stash(db)
    categories = set(categories)

    if not stash:
        print("No stashed protocols.")
        sys.exit()

    rows = []
    header = ["#", "Name", "Category", "Message"]
    truncate = list('---x')

    for row in stash.values():
        if not categories or categories.intersection(row.categories):
            rows.append([
                row.id,
                row.protocol.pick_slug(),
                ','.join(row.categories),
                row.message or '',
            ])

    # Remove the "Category" column if it would be empty.
    if not any(x[2] for x in rows):
        del header[2]
        del truncate[2]
        for row in rows:
            del row[2]

    print(tabulate(rows, header, truncate=truncate))

def add_protocol(db, protocol, categories=None, message=None):
    protocol.date = None
    entry = Stash(
            timestamp=datetime.now(),
            categories=categories,
            message=message,
            protocol=protocol,
    )
    db.add(entry)

def label_protocol(db, id=None, categories=None, message=None):
    row = load_protocol(db, id)
    row.categories = categories
    row.message = message

def peek_protocol(db, id=None):
    row = load_protocol(db, id)
    row.protocol.set_current_date()
    ProtocolIO(row.protocol).to_stdout()

def pop_protocol(db, id=None):
    row = load_protocol(db, id)
    row.protocol.set_current_date()
    ProtocolIO(row.protocol).to_stdout()
    db.delete(row)

def drop_protocol(db, id=None):
    row = load_protocol(db, id)
    db.delete(row)

def clear_protocols(db):
    return db.query(Stash).delete()

def load_stash(db):
    return {
            x.id: x
            for x in db.query(Stash).order_by(Stash.timestamp).all()
    }

def load_protocol(db, id):
    stash = load_stash(db)
    
    if len(stash) == 1 and id is None:
        return stash.popitem()[1]

    try:
        return stash[id]
    except KeyError:
        raise UsageError(f"No stashed protocol with id '{id}'.")

def parse_id(id):
    if id is None:
        return None

    try:
        return int(id)
    except ValueError:
        raise UsageError(f"Expected an integer id, not {id!r}.")
        
def parse_categories(categories):
    if categories is None:
        return []
    return [x.strip() for x in categories.split(',')]
    
