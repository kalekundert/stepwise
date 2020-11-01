#!/usr/bin/env python3

import pytest

from stepwise import Protocol, UsageError
from stepwise.cli.stash.model import *
from test_cli import check_command

@pytest.fixture
def empty_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f'sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

@pytest.fixture
def full_db(empty_db):
    """
    Initialize a database with a reasonably diverse set of protocols.
    """
    db = empty_db
    p1 = add_protocol(db, Protocol(steps=["X"]), message='M')
    p2 = add_protocol(db, Protocol(steps=["Y"]), categories=['A'])
    p3 = add_protocol(db, Protocol(steps=["Z"]), dependencies=[1])

    # Manually change the id numbers to catch bugs any bugs resulting from 
    # using ids where primary keys are expected or vice versa.
    p1.id, p2.id, p3.id = 11, 12, 13

    db.commit()
    return db

def query_helper(*cols):
    return lambda db: ul([x._asdict() for x in db.query(*cols).all()])

def ul(x):
    """
    Convert a <list of dicts> into a <set of frozensets of tuples>.  This 
    allows for order-independent comparisons of <lists of dicts>.
    """
    return {frozenset(d.items()) for d in x}

stash_rows = query_helper(Stash.pk, Stash.id, Stash.is_complete)
category_rows = query_helper(Category.pk, Category.name)
stash_category_rows = query_helper(
        stash_categories.c.stash_pk,
        stash_categories.c.category_pk,
)
stash_dependency_rows = query_helper(
        stash_dependencies.c.upstream_pk,
        stash_dependencies.c.downstream_pk,
)

def test_api_add(empty_db):
    db = empty_db
    rows = query_helper(
            Stash.id,
            Stash.is_complete,
            Stash.message,
    )

    assert rows(db) == ul([])

    p1 = add_protocol(db, Protocol(steps=["X"]))
    assert get_protocol(db, 1).protocol.steps == ["X"]
    assert rows(db) == ul([
            dict(id=1, is_complete=False, message=None),
    ])

    p2 = add_protocol(db, Protocol(steps=["Y"]), message="A")
    assert get_protocol(db, 2).protocol.steps == ["Y"]
    assert rows(db) == ul([
            dict(id=1, is_complete=False, message=None),
            dict(id=2, is_complete=False, message="A"),
    ])

def test_api_add_categories(empty_db):
    db = empty_db

    assert stash_rows(db) == ul([])
    assert stash_category_rows(db) == ul([])
    assert category_rows(db) == ul([])

    # - Add the protocol.
    # - Add an association table entry.
    # - Add a category.
    add_protocol(db, Protocol(), categories=['A'])
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # - Add the protocol.
    # - Add an association table entry.
    # - Reuse the existing category.
    add_protocol(db, Protocol(), categories=['A'])
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # - Add the protocol.
    # - Add two association table entrys.
    # - Add one category, reuse the other.
    add_protocol(db, Protocol(), categories=['A', 'B'])
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
            dict(pk=3, id=3, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=2, category_pk=1),
            dict(stash_pk=3, category_pk=1),
            dict(stash_pk=3, category_pk=2),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
    ])

def test_api_add_dependencies(empty_db):
    db = empty_db

    assert stash_rows(db) == ul([])
    assert stash_dependency_rows(db) == ul([])

    # No dependencies:
    add_protocol(db, Protocol())
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([])

    # One dependency:
    add_protocol(db, Protocol(), dependencies=[1])
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
    ])

    # Two dependencies:
    add_protocol(db, Protocol(), dependencies=[1,2])
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
            dict(pk=3, id=3, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
            dict(upstream_pk=1, downstream_pk=3),
            dict(upstream_pk=2, downstream_pk=3),
    ])

    # Fail to create self-dependency:
    with pytest.raises(UsageError, match="No stashed protocol with id '11'"):
        add_protocol(db, Protocol(), dependencies=[11])

def test_api_edit_message(empty_db):
    db = empty_db
    stash_rows = query_helper(Stash.pk, Stash.id, Stash.message)

    p1 = add_protocol(db, Protocol(), message='M')
    p2 = add_protocol(db, Protocol(), categories=['A'], dependencies=[p1.id])
    p1.id, p2.id = 11, 12
    db.commit()

    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message='M'),
            dict(pk=2, id=12, message=None),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # Change message:
    edit_protocol(db, 11, message='N')
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message='N'),
            dict(pk=2, id=12, message=None),
    ])

    # Remove message:
    edit_protocol(db, 11, explicit=True)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message=None),
    ])

    # Add message:
    edit_protocol(db, 11, message='O')
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message='O'),
            dict(pk=2, id=12, message=None),
    ])

    # Keep other annotations:
    edit_protocol(db, 12, message='P')
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message='O'),
            dict(pk=2, id=12, message='P'),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # Drop other annotations:
    edit_protocol(db, 12, message='Q', explicit=True)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message='O'),
            dict(pk=2, id=12, message='Q'),
    ])
    assert stash_category_rows(db) == ul([])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

def test_api_edit_categories(empty_db):
    db = empty_db
    stash_rows = query_helper(Stash.pk, Stash.id, Stash.message)

    p1 = add_protocol(db, Protocol(), categories=['A'])
    p2 = add_protocol(db, Protocol(), message='M', dependencies=[p1.id])
    p1.id, p2.id = 11, 12
    db.commit()

    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # Change category:
    edit_protocol(db, 11, categories=['B'])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=2),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
    ])

    # Remove category:
    edit_protocol(db, 11, explicit=True)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
    ])
    assert stash_category_rows(db) == ul([])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
    ])

    # Add categories:
    edit_protocol(db, 11, categories=['A', 'B'])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=1, category_pk=2),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
    ])

    # Keep other annotations:
    edit_protocol(db, 12, categories=['A'])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=1, category_pk=2),
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
    ])

    # Drop other annotations:
    edit_protocol(db, 12, categories=['B'], explicit=True)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message=None),
    ])
    assert stash_dependency_rows(db) == ul([])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=1, category_pk=2),
            dict(stash_pk=2, category_pk=2),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
    ])

def test_api_edit_dependencies(empty_db):
    db = empty_db
    stash_rows = query_helper(Stash.pk, Stash.id, Stash.message)

    p1 = add_protocol(db, Protocol())
    p2 = add_protocol(db, Protocol(), message='M', categories=['A'])
    p3 = add_protocol(db, Protocol(), dependencies=[p1.id])
    p1.id, p2.id, p3.id = 11, 12, 13
    db.commit()

    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
            dict(pk=3, id=13, message=None),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=3),
    ])

    # Change dependency
    edit_protocol(db, 13, dependencies=[12])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
            dict(pk=3, id=13, message=None),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=2, downstream_pk=3),
    ])

    # Remove dependency
    edit_protocol(db, 13, explicit=True)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
            dict(pk=3, id=13, message=None),
    ])
    assert stash_dependency_rows(db) == ul([])

    # Add dependencies
    edit_protocol(db, 13, dependencies=[11])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
            dict(pk=3, id=13, message=None),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=3),
    ])

    # Don't allow self-dependencies:
    with pytest.raises(UsageError, match="Cannot add '13' as a dependency of itself"):
        edit_protocol(db, 13, dependencies=[13])

    # Keep other annotations:
    edit_protocol(db, 12, dependencies=[11])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message='M'),
            dict(pk=3, id=13, message=None),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=3),
            dict(upstream_pk=1, downstream_pk=2),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # Drop other annotations:
    edit_protocol(db, 12, dependencies=[13], explicit=True)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, message=None),
            dict(pk=2, id=12, message=None),
            dict(pk=3, id=13, message=None),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=3),
            dict(upstream_pk=3, downstream_pk=2),
    ])
    assert stash_category_rows(db) == ul([])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

def test_api_edit_protocol(empty_db):
    db = empty_db

    add_protocol(db, Protocol(steps=["A"]))
    assert get_protocol(db).protocol.steps == ["A"]

    # Keep the existing protocol (since no new protocol is specified):
    edit_protocol(db)
    assert get_protocol(db).protocol.steps == ["A"]

    # Replace the existing protocol:
    edit_protocol(db, protocol=Protocol(steps=["B"]))
    assert get_protocol(db).protocol.steps == ["B"]

def test_api_peek(full_db, capsys):
    db = full_db
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    peek_protocol(db, 11, force_text=True)
    assert "1. X" in capsys.readouterr().out
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

def test_api_pop(full_db, capsys):
    db = full_db
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    pop_protocol(db, 11, force_text=True)
    assert "1. X" in capsys.readouterr().out
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

def test_api_drop(full_db):
    db = full_db
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    # Ok to drop nothing; no effect
    drop_protocols(db, [])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    # Ok to drop one protocol.
    drop_protocols(db, [11])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    # Ok to drop twice in a row: no effect
    drop_protocols(db, [11])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    # Ok to drop multiple protocols.
    drop_protocols(db, [12,13])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=True),
            dict(pk=3, id=13, is_complete=True),
    ])

def test_api_restore(full_db):
    db = full_db

    clear_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=True),
            dict(pk=3, id=13, is_complete=True),
    ])

    # Ok to restore nothing.
    restore_protocols(db, [])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=True),
            dict(pk=3, id=13, is_complete=True),
    ])

    # Ok to restore one protocol.
    restore_protocols(db, [11])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=True),
            dict(pk=3, id=13, is_complete=True),
    ])

    # Ok to restore twice in a row: no effect
    restore_protocols(db, [11])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=True),
            dict(pk=3, id=13, is_complete=True),
    ])

    # Ok to restore multiple protocols.
    restore_protocols(db, [12,13])
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

def test_api_clear(full_db):
    db = full_db

    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    clear_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=True),
            dict(pk=2, id=12, is_complete=True),
            dict(pk=3, id=13, is_complete=True),
    ])

def test_api_reset(full_db):
    db = full_db

    assert stash_rows(db) == ul([
            dict(pk=1, id=11, is_complete=False),
            dict(pk=2, id=12, is_complete=False),
            dict(pk=3, id=13, is_complete=False),
    ])

    # No protocols deleted, id numbers updated.
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
            dict(pk=3, id=3, is_complete=False),
    ])

    # Protocol deleted, id numbers updated:
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=2, id=1, is_complete=False),
            dict(pk=3, id=2, is_complete=False),
    ])

def test_api_reset_categories_1(empty_db):
    db = empty_db
    add_protocol(db, Protocol(), categories=['A'])
    add_protocol(db, Protocol(), categories=['A'])
    db.commit()

    # Check that the tables were setup correctly.
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # - Delete the protocol, update id numbers.
    # - Delete the association table entry.
    # - Keep the category.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=2, id=1, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=2, category_pk=1),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # - Delete the protocol.
    # - Delete the association table entry.
    # - Delete the category.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([])
    assert stash_category_rows(db) == ul([])
    assert category_rows(db) == ul([])

def test_api_reset_categories_2(empty_db):
    db = empty_db
    add_protocol(db, Protocol(), categories=['A', 'B'])
    add_protocol(db, Protocol(), categories=['A', 'B'])
    add_protocol(db, Protocol(), categories=['B', 'C'])
    db.commit()

    # Check that the tables were setup correctly.
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
            dict(pk=3, id=3, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=1, category_pk=1),
            dict(stash_pk=1, category_pk=2),
            dict(stash_pk=2, category_pk=1),
            dict(stash_pk=2, category_pk=2),
            dict(stash_pk=3, category_pk=2),
            dict(stash_pk=3, category_pk=3),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ])

    # - Delete the protocol, update id numbers.
    # - Delete two association table entries.
    # - Keep both categories.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=2, id=1, is_complete=False),
            dict(pk=3, id=2, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=2, category_pk=1),
            dict(stash_pk=2, category_pk=2),
            dict(stash_pk=3, category_pk=2),
            dict(stash_pk=3, category_pk=3),
    ])
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ])

    # - Delete the protocol, update id numbers.
    # - Delete two association table entries.
    # - Delete one category, keep the other.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=3, id=1, is_complete=False),
    ])
    assert stash_category_rows(db) == ul([
            dict(stash_pk=3, category_pk=2),
            dict(stash_pk=3, category_pk=3),
    ])
    assert category_rows(db) == ul([
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ])

    # - Delete the protocol.
    # - Delete two association table entries.
    # - Delete both categories.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([])
    assert stash_category_rows(db) == ul([])
    assert category_rows(db) == ul([])

def test_api_reset_dependencies_1(empty_db):
    # Dependency graph: 1 → 2 → 3

    db = empty_db
    p1 = add_protocol(db, Protocol())
    p2 = add_protocol(db, Protocol(), dependencies=[p1.id])
    p3 = add_protocol(db, Protocol(), dependencies=[p2.id])
    db.commit()

    # Check that the tables were setup correctly:
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
            dict(pk=3, id=3, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
            dict(upstream_pk=2, downstream_pk=3),
    ])

    # - Delete a downstream protocol, update id numbers.
    # - Delete the association table entry.
    drop_protocols(db, [3])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
    ])

    # - Delete an upstream protocol, update id numbers.
    # - Delete the association table entry.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=2, id=1, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([])

def test_api_reset_dependencies_2(empty_db):
    # Dependency graph: 1 → 2
    #                   ↓   ↓
    #                   3 → 4

    db = empty_db
    p1 = add_protocol(db, Protocol())
    p2 = add_protocol(db, Protocol(), dependencies=[p1.id])
    p3 = add_protocol(db, Protocol(), dependencies=[p1.id])
    p4 = add_protocol(db, Protocol(), dependencies=[p2.id, p3.id])
    db.commit()

    # Check that the tables were setup correctly:
    assert stash_rows(db) == ul([
            dict(pk=1, id=1, is_complete=False),
            dict(pk=2, id=2, is_complete=False),
            dict(pk=3, id=3, is_complete=False),
            dict(pk=4, id=4, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=1, downstream_pk=2),
            dict(upstream_pk=1, downstream_pk=3),
            dict(upstream_pk=2, downstream_pk=4),
            dict(upstream_pk=3, downstream_pk=4),
    ])

    # Delete an upstream protocol, update id numbers.
    # Delete two association table entries.
    drop_protocols(db, [1])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=2, id=1, is_complete=False),
            dict(pk=3, id=2, is_complete=False),
            dict(pk=4, id=3, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([
            dict(upstream_pk=2, downstream_pk=4),
            dict(upstream_pk=3, downstream_pk=4),
    ])

    # Delete a downstream protocol.
    # Delete two association table entries.
    drop_protocols(db, [3])
    reset_protocols(db)
    assert stash_rows(db) == ul([
            dict(pk=2, id=1, is_complete=False),
            dict(pk=3, id=2, is_complete=False),
    ])
    assert stash_dependency_rows(db) == ul([])

@pytest.mark.parametrize(
        'params', [
            # Categories
            dict(
                complete=[],
                kwargs=dict(categories=['A']),
                hits=[12],
            ),
            dict(
                complete=[],
                kwargs=dict(categories=['B']),
                hits=[],
            ),

            # Dependencies
            dict(
                complete=[],
                kwargs=dict(),
                hits=[11,12],
            ),
            dict(
                complete=[],
                kwargs=dict(dependencies=[11]),
                hits=[13],
            ),
            dict(
                complete=[],
                kwargs=dict(dependencies=[12]),
                hits=[],
            ),
            dict(
                complete=[],
                kwargs=dict(include_dependents=True),
                hits=[11,12,13],
            ),
            # Completed
            dict(
                complete=[11],
                kwargs=dict(),
                hits=[12,13],
            ),
            dict(
                complete=[11],
                kwargs=dict(include_complete=True),
                hits=[11,12,13],
            ),
            dict(
                complete=[12],
                kwargs=dict(categories=['A']),
                hits=[],
            ),
            dict(
                complete=[12],
                kwargs=dict(categories=['A'], include_complete=True),
                hits=[12],
            ),
            dict(
                complete=[13],
                kwargs=dict(dependencies=[11]),
                hits=[],
            ),
            dict(
                complete=[12],
                kwargs=dict(dependencies=[11], include_complete=True),
                hits=[13],
            ),
        ]
)
def test_api_find_protocols(full_db, params):
    db = full_db
    drop_protocols(db, params['complete'])
    hits = find_protocols(db, **params['kwargs'])
    assert [x.id for x in hits] == params['hits']

def test_api_find_protocols_dependencies(empty_db):
    # Extra tests for the specific case where a protocol has two dependencies, 
    # one of which is completed.  This is a bit tricky to get right.
    db = empty_db
    p1 = add_protocol(db, Protocol())
    p2 = add_protocol(db, Protocol())
    p3 = add_protocol(db, Protocol(), dependencies=[p1.id, p2.id])
    p1.id, p2.id, p3.id = 11, 12, 13
    db.commit()

    hits = find_protocols(db)
    assert {x.id for x in hits} == {p1.id, p2.id}

    drop_protocols(db, [p1.id])
    hits = find_protocols(db)
    assert {x.id for x in hits} == {p2.id}

    drop_protocols(db, [p2.id])
    hits = find_protocols(db)
    assert {x.id for x in hits} == {p3.id}

def test_api_get_protocol(empty_db):
    db = empty_db

    with pytest.raises(UsageError, match="No stashed protocols"):
        get_protocol(db)

    with pytest.raises(UsageError, match="No stashed protocol with id '1'"):
        get_protocol(db, 1)

    add_protocol(db, Protocol, message='A')

    p1 = get_protocol(db)
    assert p1.id == 1
    assert p1.message == 'A'
    p1 = get_protocol(db, 1)
    assert p1.id == 1
    assert p1.message == 'A'

    add_protocol(db, Protocol, message='B')

    with pytest.raises(UsageError, match="Multiple stashed protocols"):
        get_protocol(db)

    p1 = get_protocol(db, 1)
    assert p1.id == 1
    assert p1.message == 'A'
    p2 = get_protocol(db, 2)
    assert p2.id == 2
    assert p2.message == 'B'

def test_api_get_protocols(full_db):
    db = full_db

    assert get_protocols(db, []) == []

    ps = get_protocols(db, [11])
    assert len(ps) == 1
    assert ps[0].id == 11

    ps = get_protocols(db, [11, 13])
    assert len(ps) == 2
    assert ps[0].id == 11
    assert ps[1].id == 13

    with pytest.raises(UsageError, match="No stashed protocol with id '1'"):
        get_protocols(db, [1])
    with pytest.raises(UsageError, match="No stashed protocol with id '1'"):
        get_protocols(db, [1, 11])

def test_api_get_or_create_categories(empty_db):
    db = empty_db

    def f(db, names):
        categories = get_or_create_categories(db, names)
        db.flush()  # Make sure primary keys are assigned.
        return [dict(pk=x.pk, name=x.name) for x in categories]

    # Ok to request no categories:
    assert f(db, []) == []
    assert category_rows(db) == ul([])

    # Create a category:
    assert f(db, ['A']) == [
            dict(pk=1, name='A'),
    ]
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # Get a category without creating it:
    assert f(db, ['A']) == [
            dict(pk=1, name='A'),
    ]
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
    ])

    # Create two categories:
    assert f(db, ['B', 'C']) == [
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ]
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ])

    # Get two categories without creating them:
    assert f(db, ['B', 'C']) == [
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ]
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
    ])

    # Get one category and create another:
    assert f(db, ['C', 'D']) == [
            dict(pk=3, name='C'),
            dict(pk=4, name='D'),
    ]
    assert category_rows(db) == ul([
            dict(pk=1, name='A'),
            dict(pk=2, name='B'),
            dict(pk=3, name='C'),
            dict(pk=4, name='D'),
    ])

def test_api_get_next_id(empty_db):
    db = empty_db

    assert get_next_id(db) == 1

    p = add_protocol(db, Protocol())
    assert get_next_id(db) == 2

    p.id = 10
    assert get_next_id(db) == 11


@pytest.fixture
def empty_stash():
    check_command('stepwise stash clear')
    check_command('stepwise stash reset')

@pytest.fixture
def full_stash(empty_stash):
    check_command('stepwise step X | stepwise stash -m M')
    check_command('stepwise step Y | stepwise stash -c A')
    check_command('stepwise step Z | stepwise stash -d 1')


@pytest.mark.slow
def test_cli_ls_empty(empty_stash):
    check_command('stepwise stash ls', '^No stashed protocols.$')
    check_command('stepwise stash', '^No stashed protocols.$')

@pytest.mark.slow
def test_cli_ls_full(full_stash):
    check_command('stepwise stash ls -D', '''\
#  Dep  Name  Category  Message
───────────────────────────────
1       step            M
2       step  A
3    1  step
''')

@pytest.mark.slow
def test_cli_ls_categories(empty_stash):
    check_command('stepwise step X | stepwise stash -c A')
    check_command('stepwise step Y | stepwise stash -c A,B')

    check_command('stepwise stash ls', '''\
#  Name  Category  Message
──────────────────────────
1  step  A
2  step  A,B
''')

    check_command('stepwise stash ls -c A', '''\
#  Name  Category  Message
──────────────────────────
1  step  A
2  step  A,B
''')

    check_command('stepwise stash ls -c B', '''\
#  Name  Category  Message
──────────────────────────
2  step  A,B
''')

    check_command('stepwise stash ls -c C', '''\
No matching protocols found.
''')

@pytest.mark.slow
def test_cli_ls_dependencies(empty_stash):
    check_command('stepwise step 1 | stepwise stash')
    check_command('stepwise step 2 | stepwise stash -d 1')
    check_command('stepwise step 3 | stepwise stash -d 1')
    check_command('stepwise step 4 | stepwise stash -d 2,3')

    check_command('stepwise stash -D', '''\
#  Dep  Name  Message
─────────────────────
1       step
2    1  step
3    1  step
4  2,3  step
''')

    check_command('stepwise stash', '''\
#  Name  Message
────────────────
1  step
''')

    check_command('stepwise stash -d 1', '''\
#  Dep  Name  Message
─────────────────────
2    1  step
3    1  step
''')

    check_command('stepwise stash -d 2', '''\
#  Dep  Name  Message
─────────────────────
4  2,3  step
''')

    check_command('stepwise stash -d 3', '''\
#  Dep  Name  Message
─────────────────────
4  2,3  step
''')

    check_command('stepwise stash -d 4', '''\
No matching protocols found.
''')

    # Complete a dependency:
    check_command('stepwise stash drop 1')

    check_command('stepwise stash -D', '''\
#  Dep  Name  Message
─────────────────────
2       step
3       step
4  2,3  step
''')

    check_command('stepwise stash', '''\
#  Name  Message
────────────────
2  step
3  step
''')

@pytest.mark.slow
def test_cli_ls_completed(empty_stash):
    check_command('stepwise step 1 | stepwise stash')
    check_command('stepwise step 2 | stepwise stash')
    check_command('stepwise stash drop 2')

    check_command('stepwise stash ls', '''\
#  Name  Message
────────────────
1  step
''')

    check_command('stepwise stash ls -a', '''\
#  Name  Message
────────────────
1  step
2  step
''')

@pytest.mark.slow
def test_cli_add(empty_stash):
    # Tested adequately by the `full_stash` fixture.
    pass

@pytest.mark.slow
def test_cli_edit(empty_stash):
    check_command('stepwise step X | stepwise stash')
    check_command('stepwise step Y | stepwise stash')
    check_command('stepwise stash -a', '''\
#  Name  Message
────────────────
1  step
2  step
''')
    check_command('stepwise stash peek 1', '''\
{DATE}

\\$ stepwise step X

1\\. X
''')
    
    check_command('stepwise stash edit 1 -m M')
    check_command('stepwise stash -a', '''\
#  Name  Message
────────────────
1  step  M
2  step
''')

    check_command('stepwise stash edit 1 -c A')
    check_command('stepwise stash -a', '''\
#  Name  Category  Message
──────────────────────────
1  step  A         M
2  step
''')

    check_command('stepwise stash edit 1 -d 2')
    check_command('stepwise stash -a', '''\
#  Dep  Name  Category  Message
───────────────────────────────
1    2  step  A         M
2       step
''')

    check_command('stepwise step Z | stepwise stash edit 1')
    check_command('stepwise stash -a', '''\
#  Dep  Name  Category  Message
───────────────────────────────
1    2  step  A         M
2       step
''')
    check_command('stepwise stash peek 1', '''\
{DATE}

\\$ stepwise step Z

1\\. Z
''')

    check_command('stepwise stash edit 1 -x -m N')
    check_command('stepwise stash -a', '''\
#  Name  Message
────────────────
1  step  N
2  step
''')

    check_command('stepwise stash edit 1 -x -c B')
    check_command('stepwise stash -a', '''\
#  Name  Category  Message
──────────────────────────
1  step  B
2  step
''')

    check_command('stepwise stash edit 1 -x -d 2')
    check_command('stepwise stash -a', '''\
#  Dep  Name  Message
─────────────────────
1    2  step
2       step
''')

@pytest.mark.slow
def test_cli_peek(full_stash):
    check_command('stepwise stash peek 1', '''\
{DATE}

\\$ stepwise step X

1\\. X
''')
    check_command('stepwise stash -D', '''\
#  Dep  Name  Category  Message
───────────────────────────────
1       step            M
2       step  A
3    1  step
''')

@pytest.mark.slow
def test_cli_pop(full_stash):
    check_command('stepwise stash pop 1', '''\
{DATE}

\\$ stepwise step X

1\\. X
''')
    check_command('stepwise stash', '''\
#  Name  Category  Message
──────────────────────────
2  step  A
3  step
''')

    # Can still view a popped protocol, even though it's not listed anymore.
    check_command('stepwise stash pop 1', '''\
{DATE}

\\$ stepwise step X

1\\. X
''')

@pytest.mark.slow
def test_cli_drop_restore(full_stash):
    check_command('stepwise stash drop 1')
    check_command('stepwise stash', '''\
#  Name  Category  Message
──────────────────────────
2  step  A
3  step
''')
    check_command('stepwise stash -a', '''\
#  Name  Category  Message
──────────────────────────
1  step            M
2  step  A
3  step
''')

    check_command('stepwise stash restore 1')
    check_command('stepwise stash -D', '''\
#  Dep  Name  Category  Message
───────────────────────────────
1       step            M
2       step  A
3    1  step
''')

@pytest.mark.slow
def test_cli_clear(full_stash):
    check_command('stepwise stash clear')
    check_command('stepwise stash', '^No stashed protocols.$')
    check_command('stepwise stash -a', '''\
#  Name  Category  Message
──────────────────────────
1  step            M
2  step  A
3  step
''')

@pytest.mark.slow
def test_cli_reset(empty_stash):
    check_command('stepwise step 1 | stepwise stash')
    check_command('stepwise step 2 | stepwise stash -c A -d 1')
    check_command('stepwise stash -D', '''\
#  Dep  Name  Category  Message
───────────────────────────────
1       step
2    1  step  A
''')


    # - ID numbers update
    # - Categories and dependencies not confused by changing id numbers.
    check_command('stepwise stash drop 1')
    check_command('stepwise stash reset')
    check_command('stepwise stash -D', '''\
#  Name  Category  Message
──────────────────────────
1  step  A
''')

    check_command('stepwise stash drop 1')
    check_command('stepwise stash reset')
    check_command('stepwise stash -a', '''\
No stashed protocols.
''')

    # - Categories and dependencies don't persist across resets.
    check_command('stepwise step 1 | stepwise stash')
    check_command('stepwise step 2 | stepwise stash')
    check_command('stepwise stash -D', '''\
#  Name  Message
────────────────
1  step
2  step
''')
