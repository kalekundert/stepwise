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

    check_command('stepwise custom A | stepwise stash')
    check_command('stepwise custom B1 | stepwise stash -c b')
    check_command('stepwise custom B2 | stepwise stash -c b')
    check_command('stepwise custom C | stepwise stash add -m "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam justo sem, malesuada ut ultricies ac, bibendum eu neque."')

    check_command('stepwise stash ls', '''\
#  Name    Cat.  Message
───────────────────────────────────────────────────────────────────────────────
1  custom
2  custom  b
3  custom  b
4  custom        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam… 
''')

    check_command('stepwise stash ls -c b', '''\
#  Name    Cat.  Message
────────────────────────
2  custom  b
3  custom  b
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
#  Name    Cat.  Message
───────────────────────────────────────────────────────────────────────────────
1  custom  b
2  custom  b
3  custom        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam… 
''')

    # Test `drop`:
    check_command('stepwise stash drop 3')

    check_command('stepwise stash ls', '''\
#  Name    Cat.  Message
────────────────────────
1  custom  b
2  custom  b
''')

    # Test `clear`:
    check_command('stepwise stash clear')
    check_command('stepwise stash ls', '^No stashed protocols.$')


def check_command(cmd, stdout='^$', stderr='^$', return_code=0, env={}):
    p = tty_capture(cmd, env=env, shell=True)
    assert p.returncode == return_code

    print(cmd)
    check_output(p.stdout, stdout, sys.stdout)

    print(cmd, file=sys.stderr)
    check_output(p.stderr, stderr, sys.stderr)

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

