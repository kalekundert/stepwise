#!/usr/bin/env python3

import sys
import pytest
import stepwise
import pickle

from pathlib import Path
from stepwise.library import _capture_stdout
from stepwise.testing import disable_capture
from param_helpers import *

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

@parametrize_from_file(
        schema=Schema({
            'collections': empty_ok([str]),
            'tag': str,
            'expected': empty_ok([str]),
        }),
)
def test_library_find_entries(collections, tag, expected):
    collection_map = {
            '1': stepwise.PathCollection(COLLECT1_DIR),
            '2': stepwise.PathCollection(COLLECT2_DIR),
    }

    library = DummyLibrary()
    library.collections = [collection_map[x] for x in collections]
    entries = list(x.name for x in library.find_entries(tag))

    assert entries == paths(expected)

    if len(expected) < 1:
        with pytest.raises(stepwise.NoProtocolsFound):
            library.find_entry(tag)

    elif len(expected) > 1:
        with pytest.raises(stepwise.MultipleProtocolsFound):
            library.find_entry(tag)

    else:
        assert library.find_entry(tag).name == path(expected[0])

@parametrize_from_file(
        schema=Schema({
            'name': str,
            'names': empty_ok([str]),
            'expected': eval_python,
        }),
)
def test_collection_is_unique(name, names, expected):
    collection = stepwise.Collection(name)
    collections = [stepwise.Collection(x) for x in names]
    assert collection.is_unique(collections) == expected

def test_path_collection_is_available():
    collection = stepwise.PathCollection(COLLECT1_DIR)
    assert collection.is_available()

    collection = stepwise.PathCollection(COLLECT1_DIR / 'nonexistant')
    assert not collection.is_available()

@parametrize_from_file(
        schema=Schema({
            'tag': str,
            'expected': empty_ok([str]),
        }),
)
def test_path_collection_find_entries(tag, expected):
    collection = stepwise.PathCollection(COLLECT1_DIR)
    entries = list(x.name for _, x in collection.find_entries(tag))

    assert collection.is_available()
    assert entries == paths(expected)

@parametrize_from_file(
        schema=Schema({
            'tag': str,
            'expected': empty_ok([str]),
        }),
)
def test_cwd_collection_find_entries(tag, expected):
    import os

    # Instantiate the collection before changing directories, to ensure that 
    # the collection evaluates the current working directory each time it 
    # searches for entries.
    collection = stepwise.CwdCollection()

    prev_cwd = os.getcwd()
    os.chdir(COLLECT1_DIR)

    entries = list(x.name for _, x in collection.find_entries(tag))

    try:
        assert entries == paths(expected)
    finally:
        os.chdir(prev_cwd)

@parametrize_from_file
def test_entry_full_name(collection_name, entry_name, full_name):
    collection = stepwise.Collection(collection_name)
    entry = stepwise.Entry(collection, entry_name)
    assert entry.full_name == path(full_name)

@parametrize_from_file(
        schema=Schema({
            'relpath': str,
            Optional('args', default=[]): empty_ok([str]),
            'steps': empty_ok([str]),
            Optional('attachments', default=[]): empty_ok([str]),
            Optional('skip_windows', default=''): str,
        }),
)
def test_path_entry_load_protocol(disable_capture, relpath, args, steps, attachments, skip_windows):
    if skip_windows and sys.platform == 'win32':
        pytest.skip(skip_windows)

    collection = stepwise.PathCollection(COLLECT3_DIR)
    entry = stepwise.PathEntry(collection, relpath)

    library = DummyLibrary.from_singleton()
    library.collections = [collection]

    try:
        with disable_capture:
            io = entry.load_protocol(args)

        assert format_steps(io.protocol) == steps
        assert io.protocol.attachments == [
                COLLECT3_DIR / x
                for x in attachments
        ]
    finally:
        stepwise.Library._singleton = None


@parametrize_from_file(
        schema=Schema({
            'tag': str,
            'name': str,
            'expected': eval_python,
        }),
)
def test_match_tag(tag, name, expected):
    from stepwise.library import _match_tag
    assert _match_tag(tag or None, name) == tuple(expected)

@parametrize_from_file(
        schema=Schema({
            'scripts': {str: str},
            Optional('args', default=[]): [str],
            Optional('stdout', default=''): str,
            Optional('stderr', default=''): str,
            Optional('return_code', default=0): Coerce(int),
        }),
)
def test_run_python_script(tmp_path, scripts, args, stdout, stderr, return_code):
    import sys, pickle
    from subprocess import run

    # The following commands are helpful for debugging these tests:
    #
    #   $ cd /tmp/directory/containing/test/scripts
    #   $ py -c 'import sys, pickle, pathlib; pickle.dump((pathlib.Path("main.py"), []), sys.stdout.buffer)' | py wrapper.py | py -c 'import sys, pickle; debug(pickle.load(sys.stdin.buffer))'

    for name, code in scripts.items():
        py_path = tmp_path / f'{name}.py'
        py_path.write_text(code)

    # Run the following in a subprocess, so the stdin redirection doesn't 
    # conflict with pytest.
    wrapper_path = tmp_path / 'wrapper.py'
    wrapper_path.write_text('''\
import sys, pickle
from stepwise.library import _run_python_script

args = pickle.load(sys.stdin.buffer)
p = _run_python_script(*args)
pickle.dump(p, sys.stdout.buffer)
''')

    # Pass the arguments via stdin for they aren't interpreted as text.
    args = (tmp_path / 'main.py', args)
    p1 = run(
            ['python', wrapper_path],
            input=pickle.dumps(args),
            capture_output=True,
    )
    p2 = pickle.loads(p1.stdout)

    print(p1.stdout)
    print(p1.stderr, file=sys.stderr)

    assert p2.returncode == return_code
    assert p2.stdout.decode() == stdout
    assert stderr in p1.stderr.decode()

def test_capture_stdout_python():
    with _capture_stdout() as f:
        print('python')

    assert f.getvalue() == b'python\n'

def test_capture_stdout_subprocess(capfd):
    from subprocess import run

    with capfd.disabled():
        with _capture_stdout() as f:
            run(['echo', 'subprocess'])

    assert f.getvalue() == b'subprocess\n'

def test_capture_stdout_nested():
    with _capture_stdout() as f1:
        print('1')
        with _capture_stdout() as f2:
            print('2')
        print('3')

    assert f1.getvalue() == b'1\n3\n'
    assert f2.getvalue() == b'2\n'

def test_capture_stdout_flush_before_after():
    # It's important that the strings used in this test don't have newlines, 
    # because python flushes stdout at newlines by default.

    sys.stdout.write('before')
    with _capture_stdout() as f:
        sys.stdout.write('inside')
    sys.stdout.write('after')

    assert f.getvalue() == b'inside'

def test_capture_stdout_exceed_pipe_capacity():
    # Make a write that exceeds the size of the pipe buffer, which is 65536 
    # (2¹⁶) bytes on my machine.
    
    data = (2**16 + 1) * 'a'
    with _capture_stdout() as f:
        sys.stdout.write(data)
    assert f.getvalue() == data.encode()

def test_preserve_stdin():
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

def test_from_pickle_january():
    # I ran into a wild bug where the python interpreter would crash when 
    # attempting to load a protocol generated in January from a byte stream.  
    # The issue is that stepwise needs to decide whether or not to use pickle 
    # to decode a byte stream, and it used to do this by just trying to 
    # unpickle the stream and checking for errors.  The problem is that 
    # attempting to unpickle byte streams beginning with "January" doesn't 
    # cause an exception.  It causes huge amounts of memory (>16 GB) to be 
    # allocated, which ultimately causes the interpreter to crash.  To fix 
    # this, I rewrote the code to manually check for the pickle header.  The 
    # purpose of this test is to document this bug and to prevent regressions.
    io = stepwise.ProtocolIO.from_bytes(
            b'January 11, 2021\n'
            b'\n'
            b'1. A'
    )
    assert format_steps(io.protocol) == ['A']

def test_to_stdout(capsysbinary):
    unpickleable_protocol = stepwise.Protocol(steps=[lambda: None])
    io = stepwise.ProtocolIO(unpickleable_protocol)
    io.to_stdout()

    cap = capsysbinary.readouterr()
    io_out = pickle.loads(cap.out)
    assert io_out.protocol == ''
    assert io_out.errors == 1
    assert "AttributeError: Can't pickle local object" in cap.err.decode()


def path(x):
    from os.path import sep
    return x.replace('/', sep)

def paths(xs):
    return [path(x) for x in xs]

def format_steps(p):
    from stepwise import format_text
    from math import inf

    return [format_text(x, inf) for x in p.steps]

