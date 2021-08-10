#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from inform import format_range
from stepwise import ProtocolIO, UsageError, tabulate, config_dirs
from . import pickler

from sqlalchemy import func, Table, Column, ForeignKey, Integer, DateTime, String, Boolean, PickleType
from sqlalchemy.orm import relationship, aliased
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

stash_categories = Table(
        'stash_categories', Base.metadata,
        Column('stash_pk', Integer, ForeignKey('stash.pk')),
        Column('category_pk', Integer, ForeignKey('categories.pk')),
)
stash_dependencies = Table(
        'stash_dependencies', Base.metadata,
        Column('upstream_pk', Integer, ForeignKey('stash.pk')),
        Column('downstream_pk', Integer, ForeignKey('stash.pk')),
)

class Stash(Base):
    __tablename__ = 'stash'

    pk = Column(Integer, primary_key=True)
    id = Column(Integer, index=True, unique=True)
    date_added = Column(DateTime, default=datetime.now)
    is_complete = Column(Boolean, default=False)
    message = Column(String)
    protocol = Column(PickleType(pickler=pickler))

    categories = relationship(
            'Category',
            secondary=stash_categories,
            backref='protocols',
    )
    upstream_deps = relationship(
            'Stash',
            secondary=stash_dependencies,
            primaryjoin=(pk == stash_dependencies.c.downstream_pk),
            secondaryjoin=(pk == stash_dependencies.c.upstream_pk),
            backref='downstream_deps',
    )

    def __repr__(self):
        return f"Stash(id={self.id!r})"

    @property
    def io(self):
        return ProtocolIO(self.protocol, errors=isinstance(self.protocol, str))


class Category(Base):
    __tablename__ = 'categories'

    pk = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Category(name={self.name!r})"

@contextmanager
def open_db(path=None):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if not path:
        path = Path(config_dirs.user_data_dir) / 'stash.sqlite'
        path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f'sqlite:///{path}', echo=False)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    try:
        yield session
        session.commit()
    except SystemExit:
        session.commit()
        raise
    except:
        session.rollback()
        raise
    finally:
        session.close()

def list_protocols(db, *, categories=None, dependencies=None, include_dependents=False, include_complete=False):
    stash = find_protocols(
            db,
            categories=categories,
            dependencies=dependencies,
            include_dependents=include_dependents,
            include_complete=include_complete,
    )
    if not stash:
        if categories or dependencies:
            print("No matching protocols found.")
        else:
            print("No stashed protocols.")
        return

    rows = []
    header = ["#", "Err", "Dep", "Name", "Category", "Message"]
    truncate = list('---x-x')
    align = list('>^><<<')

    for row in stash:
        rows.append([
            row.id,
            '!' if row.io.errors else '',
            format_range(
                x.id
                for x in row.upstream_deps
                if not x.is_complete
            ),
            row.protocol.pick_slug() if not row.io.errors else '',
            ','.join(x.name for x in sorted(row.categories, key=lambda x: x.pk)),
            row.message or '',
        ])

    def remove_empty_col(col):
        i = header.index(col)
        if not any(x[i] for x in rows):
            del header[i]
            del truncate[i]
            del align[i]
            for row in rows:
                del row[i]

    remove_empty_col("Err")
    remove_empty_col("Dep")
    remove_empty_col("Category")

    print(tabulate(rows, header, truncate=truncate, align=align))

def find_protocols(db, *, categories=None, dependencies=None, include_dependents=False, include_complete=False):
    query = db.query(Stash).order_by(Stash.id)

    if categories:
        query = query\
                .join(Stash.categories)\
                .filter(Category.name.in_(categories))

    if dependencies:
        Upstream = aliased(Stash)
        query = query\
                .outerjoin(Stash.upstream_deps.of_type(Upstream))\
                .filter(Upstream.id.in_(dependencies))

    if not include_dependents and not dependencies and not include_complete:
        # Select just those upstream dependencies that are incomplete.
        dep = db.query(stash_dependencies)\
                .join(Stash, Stash.pk == stash_dependencies.c.upstream_pk)\
                .filter(Stash.is_complete == False)\
                .subquery()

        # Select rows that aren't present as downstream dependencies in the 
        # above query.  This is an anti-join.
        query = query\
                .outerjoin(dep, Stash.pk == dep.c.downstream_pk)\
                .filter(dep.c.downstream_pk == None)

    if not include_complete:
        query = query.filter(Stash.is_complete == False)

    return query.all()

def add_protocol(db, protocol, *, message=None, categories=None, dependencies=None):
    protocol.date = None
    row = Stash(
            id=get_next_id(db),
            categories=get_or_create_categories(db, categories),
            message=message,
            protocol=protocol,
            upstream_deps=get_protocols(db, dependencies),
    )
    db.add(row)
    return row

def edit_protocol(db, id=None, protocol=None, *, message=None, categories=None, dependencies=None, explicit=False):
    row = get_protocol(db, id)
    if message or explicit:
        row.message = message
    if categories or explicit:
        row.categories = get_or_create_categories(db, categories)
    if dependencies or explicit:
        if row.id in (dependencies or []):
            raise UsageError(f"Cannot add '{row.id}' as a dependency of itself.")
        row.upstream_deps = get_protocols(db, dependencies)
    if protocol:
        protocol.date = None
        row.protocol = protocol
    return row

def peek_protocol(db, id=None):
    return get_protocol(db, id)

def pop_protocol(db, id=None):
    row = peek_protocol(db, id)
    row.is_complete = True
    return row

def drop_protocols(db, ids):
    for id in ids:
        row = get_protocol(db, id)
        row.is_complete = True

def restore_protocols(db, ids):
    for id in ids:
        row = get_protocol(db, id)
        row.is_complete = False

def clear_protocols(db):
    for row in db.query(Stash).all():
        row.is_complete = True

def reset_protocols(db):
    # Use `db.delete()` rather than `query.delete()` because the latter does 
    # not respect in-python delete cascades, which are used here to update the 
    # association table.  Also, `query.delete()` is not compatible with joins.

    for row in db.query(Stash).filter_by(is_complete=True).all():
        db.delete(row)

    for i, row in enumerate(db.query(Stash).order_by(Stash.id), 1):
        row.id = i

    stale_categories = db.query(Category)\
            .outerjoin(stash_categories)\
            .filter(stash_categories.c.stash_pk == None)\
            .all()

    for category in stale_categories:
        db.delete(category)

def get_protocol(db, id=None):
    if id is None:
        try:
            return db.query(Stash).filter_by(is_complete=False).one()
        except NoResultFound:
            raise UsageError("No stashed protocols")
        except MultipleResultsFound:
            raise UsageError("Multiple stashed protocols, please specify an id")

    else:
        try:
            return db.query(Stash).filter_by(id=id).one()
        except NoResultFound:
            raise UsageError(f"No stashed protocol with id '{id}'")
        except MultipleResultsFound:  # pragma: no cover
            # Database constraints should prevent this from ever occurring.
            raise AssertionError(f"Multiple stashed protocols with id '{id}'.  This should never happen!  Please report a bug: <https://github.com/kalekundert/stepwise/issues>")

def get_protocols(db, ids):
    # Get each protocol individually (as opposed to getting them all in one 
    # query) to make sure that an error is raised if we're given an invalid id.
    return [
            get_protocol(db, id)
            for id in ids or []
    ]

def get_or_create_categories(db, names):
    if not names:
        return []

    categories = db.query(Category).filter(Category.name.in_(names)).all()

    existing_names = {x.name for x in categories}
    missing_names = [x for x in names if x not in existing_names]

    for name in missing_names:
        category = Category(name=name)
        categories.append(category)
        db.add(category)

    return categories

def get_next_id(db):
    curr_id = db.query(func.max(Stash.id)).scalar()

    # The max() function returns None if there are no rows in the table, so we
    # have to handle this case specially.
    return 1 if curr_id is None else curr_id + 1

