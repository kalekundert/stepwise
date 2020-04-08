#!/usr/bin/env python3

import pytest, sys, re
from utils import *

DATE = r'\w+ \d{1,2}, \d{4}'

@pytest.mark.slow
@parametrize_via_toml('test_cli.toml')
def test_main(cmd, env, stdout, stderr, return_code):
    check_command(cmd, stdout, stderr, return_code, env)

@pytest.mark.slow
def test_stash():
    # Test `ls` and `add`:
    check_command('stepwise stash clear')
    check_command('stepwise stash ls', '^No stashed protocols.$')
    check_command('stepwise stash', '^No stashed protocols.$')

    check_command('stepwise custom A | stepwise stash add')
    check_command('stepwise custom B | stepwise stash -c b')
    check_command('stepwise custom BC | stepwise stash -c b,c')
    check_command('stepwise custom D | stepwise stash -m "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam justo sem, malesuada ut ultricies ac, bibendum eu neque."')

    check_command('stepwise stash', '''\
#  Name    Category  Message
───────────────────────────────────────────────────────────────────────────────
1  custom
2  custom  b
3  custom  b,c
4  custom            Lorem ipsum dolor sit amet, consectetur adipiscing elit.…

''')

    check_command('stepwise stash -c b', '''\
#  Name    Category  Message
────────────────────────────
2  custom  b
3  custom  b,c
''')

    check_command('stepwise stash -c c', '''\
#  Name    Category  Message
────────────────────────────
3  custom  b,c
''')

    # Test `peek`:
    check_command('stepwise stash peek 1', '''\
{DATE}

\\$ stepwise custom A

1\\. A
''')

    # Test `pop`:
    check_command('stepwise stash pop 1', '''\
{DATE}

\\$ stepwise custom A

1\\. A
''')

    check_command('stepwise stash ls', '''\
#  Name    Category  Message
───────────────────────────────────────────────────────────────────────────────
2  custom  b
3  custom  b,c
4  custom            Lorem ipsum dolor sit amet, consectetur adipiscing elit.… 
''')

    # Test `drop`:
    check_command('stepwise stash drop 2')
    check_command('stepwise stash ls', '''\
#  Name    Category  Message
───────────────────────────────────────────────────────────────────────────────
3  custom  b,c
4  custom            Lorem ipsum dolor sit amet, consectetur adipiscing elit.… 
''')

    check_command('stepwise stash drop 3')
    check_command('stepwise stash ls', '''\
#  Name    Message
───────────────────────────────────────────────────────────────────────────────
4  custom  Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam justo…
''')

    # Test `label`:
    check_command('stepwise stash label 4')
    check_command('stepwise stash ls', '''\
#  Name    Message
──────────────────
4  custom
''')

    check_command('stepwise stash label 4 -c d')
    check_command('stepwise stash ls', '''\
#  Name    Category  Message
────────────────────────────
4  custom  d
''')

    check_command('stepwise stash label 4 -m "Lorem ipsum"')
    check_command('stepwise stash ls', '''\
#  Name    Message
──────────────────────
4  custom  Lorem ipsum
''')

    # Test implicit id:
    check_command('stepwise stash peek', '''\
{DATE}

\\$ stepwise custom D

1\\. D
''')

    check_command('stepwise stash pop', '''\
{DATE}

\\$ stepwise custom D

1\\. D
''')

    # Test `clear`:
    check_command('stepwise stash clear')
    check_command('stepwise stash', '^No stashed protocols.$')


def check_command(cmd, stdout='^$', stderr='^$', return_code=0, env={}):
    p = tty_capture(cmd, env=env, shell=True)

    print(cmd, file=sys.stderr)
    check_output(p.stderr, stderr, sys.stderr)

    print(cmd)
    check_output(p.stdout, stdout, sys.stdout)

    assert p.returncode == return_code

def check_output(captured, expected, file=sys.stdout):
    expected = expected.format(DATE=DATE).strip()
    captured = captured.replace('\r', '')

    print(repr(captured), file=file)
    print(repr(expected), file=file)

    assert re.match(expected, captured, flags=re.DOTALL)

def tty_capture(cmd, stdin=None, env={}, **kwargs):
    """
    Capture stdout and stderr of the given command with the given stdin, 
    with stdin, stdout and stderr all being TTYs.

    Based on:
    https://stackoverflow.com/questions/52954248/capture-output-as-a-tty-in-python
    https://gist.github.com/hayd/4f46a68fc697ba8888a7b517a414583e
    """
    import os, pty, select, errno
    import subprocess as subp

    mo, so = pty.openpty()
    me, se = pty.openpty()  
    mi, si = pty.openpty()  

    home = Path(__file__).parent / 'dummy_home'
    p = subp.Popen(
        cmd,
        bufsize=1,
        stdin=si,
        stdout=so,
        stderr=se, 
        close_fds=True,
        env={**os.environ, 'COLUMNS': '80', 'HOME': str(home), **env},
        **kwargs,
    )
    for fd in [so, se, si]:
        os.close(fd)
    if stdin is not None:
        os.write(mi, stdin.encode())

    timeout = 0.04  # seconds
    readable = [mo, me]
    result = {mo: b'', me: b''}
    try:
        while readable:
            ready, _, _ = select.select(readable, [], [], timeout)
            for fd in ready:
                try:
                    data = os.read(fd, 512)
                except OSError as e:
                    if e.errno != errno.EIO:
                        raise
                    # EIO means EOF on some systems
                    readable.remove(fd)
                else:
                    if not data: # EOF
                        readable.remove(fd)
                    result[fd] += data

    finally:
        for fd in [mo, me, mi]:
            os.close(fd)
        if p.poll() is None:
            p.kill()
        p.wait()

    return subp.CompletedProcess(
            cmd,
            p.returncode,
            stdout=result[mo].decode(),
            stderr=result[me].decode(),
    )

