#!/usr/bin/env python3

import pytest
import stepwise
from utils import *

LIBRARY_DIR = TEST_DIR / 'dummy_library'
COLLECT1_DIR = LIBRARY_DIR / 'collection_1'
COLLECT2_DIR = LIBRARY_DIR / 'collection_2'
COLLECT3_DIR = LIBRARY_DIR / 'collection_3'

class DummyLibrary(stepwise.Library):

    def __init__(self, collections=None):
        # Don't load any collections by default.
        self.collections = collections or []

def test_library_singleton():
    lib1 = DummyLibrary.from_singleton()
    lib2 = DummyLibrary.from_singleton()
    assert lib1 is lib2

@parametrize_via_toml('test_library.toml')
def test_library_find_entries(collections, tag, expected):
    collection_map = {
            '1': stepwise.PathCollection(COLLECT1_DIR),
            '2': stepwise.PathCollection(COLLECT2_DIR),
    }

    library = DummyLibrary()
    library.collections = [collection_map[x] for x in collections]
    entries = list(x.name for x in library.find_entries(tag))

    assert entries == expected

    if len(expected) < 1:
        with pytest.raises(stepwise.NoProtocolsFound):
            library.find_entry(tag)

    elif len(expected) > 1:
        with pytest.raises(stepwise.MultipleProtocolsFound):
            library.find_entry(tag)

    else:
        assert library.find_entry(tag).name == expected[0]

@parametrize_via_toml('test_library.toml')
def test_collection_is_unique(name, names, expected):
    collection = stepwise.Collection(name)
    collections = [stepwise.Collection(x) for x in names]
    assert collection.is_unique(collections) == expected

def test_path_collection_is_available():
    collection = stepwise.PathCollection(COLLECT1_DIR)
    assert collection.is_available()

    collection = stepwise.PathCollection(COLLECT1_DIR / 'nonexistant')
    assert not collection.is_available()

@parametrize_via_toml('test_library.toml')
def test_path_collection_find_entries(tag, expected):
    collection = stepwise.PathCollection(COLLECT1_DIR)
    entries = list(x.name for _, x in collection.find_entries(tag))

    assert collection.is_available()
    assert entries == expected

@parametrize_via_toml('test_library.toml')
def test_cwd_collection_find_entries(tag, expected):
    import os
    prev_cwd = os.getcwd()
    os.chdir(COLLECT1_DIR)

    collection = stepwise.CwdCollection()
    entries = list(x.name for _, x in collection.find_entries(tag))

    try:
        assert entries == expected
    finally:
        os.chdir(prev_cwd)

@parametrize_via_toml('test_library.toml')
def test_entry_full_name(collection_name, entry_name, full_name):
    import os
    collection = stepwise.Collection(collection_name)
    entry = stepwise.Entry(collection, entry_name)
    assert entry.full_name == full_name.replace('/', os.sep)

@parametrize_via_toml('test_library.toml')
def test_path_entry_load_protocol(disable_capture, relpath, args, steps, attachments):
    collection = stepwise.PathCollection(COLLECT3_DIR)
    entry = stepwise.PathEntry(collection, relpath)

    library = DummyLibrary.from_singleton()
    library.collections = [collection]

    try:
        with disable_capture:
            io = entry.load_protocol(args)

        assert io.protocol.steps == steps
        assert io.protocol.attachments == [
                COLLECT3_DIR / x
                for x in attachments
        ]
    finally:
        DummyLibrary._singleton = None


@parametrize_via_toml('test_library.toml')
def test_match_entry(tag, name, expected):
    from stepwise.library import _match_tag
    assert _match_tag(tag or None, name) == tuple(expected)

def test_capture_stdout(capfd):
    import ctypes
    from io import BytesIO
    from subprocess import run
    from stepwise.library import _capture_stdout

    libc = ctypes.CDLL(None)

    with capfd.disabled():

        # Don't do all the tests in the same with statement, because the 
        # relative ordering of lines written in different environments (e.g.  
        # python, libc) is not guaranteed to be maintained.  This is because 
        # the different environments might flush at different times.

        with _capture_stdout() as f:
            print('python')
        assert f.getvalue() == b'python\n'

        with _capture_stdout() as f:
            run(['echo', 'subprocess'])
        assert f.getvalue() == b'subprocess\n'

        with _capture_stdout() as f:
            libc.puts(b'libc')
        assert f.getvalue() == b'libc\n'

def test_preserve_stdin():
    import sys
    from subprocess import run

    # Run the following in a subprocess, so we can feed it stdin:
    script = '''\
from subprocess import run
from stepwise.library import _preserve_stdin

with _preserve_stdin():
    run('cat')

print('stdin:', input())
'''
    p = run(
            ['python', '-c', script], 
            input="not for cat",
            capture_output=True,
            text=True,
    )

    # If successful, the `cat` command will *not* have read the input we 
    # provided.  If unsuccessful, it might just hang forever...
    assert p.stdout == "stdin: not for cat\n"
    
def test_check_version_control(tmp_path):
    import subprocess as subp
    from pytest import raises
    from stepwise.library import _check_version_control, VersionControlWarning

    repo = tmp_path / 'repo'
    repo.mkdir()
    protocol = repo / 'protocol'
    protocol.write_text("version 1")

    with raises(VersionControlWarning, match="not in a git repository"):
        _check_version_control(protocol)

    subp.run('git init', cwd=repo, shell=True)

    with raises(VersionControlWarning, match="not committed"):
        _check_version_control(protocol)
    
    subp.run(f'git add {protocol.name}', cwd=repo, shell=True)
    subp.run(f'git commit -m "Initial commit"', cwd=repo, shell=True)

    _check_version_control(protocol)

    protocol.write_text("version 2")

    with raises(VersionControlWarning, match="uncommitted changes"):
        _check_version_control(protocol)


@pytest.fixture
def disable_capture(pytestconfig):
    # Equivalent to `pytest -s`, but temporary.
    # This is necessary because even `capfd.disabled()` leaves stdin in a state 
    # that somehow interferes with the redirection we're trying to do.

    class suspend_guard:

        def __init__(self):
            self.capmanager = pytestconfig.pluginmanager.getplugin('capturemanager')

        def __enter__(self):
            self.capmanager.suspend_global_capture(in_=True)
            pass

        def __exit__(self, _1, _2, _3):
            self.capmanager.resume_global_capture()

    yield suspend_guard()

