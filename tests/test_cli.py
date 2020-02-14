#!/usr/bin/env python3

import pytest, sys, re
from utils import *

DATE = r'\w+ \d{1,2}, \d{4}'

@pytest.mark.slow
@parametrize_via_toml('test_cli.toml')
def test_main(cmd, env, stdout, stderr, return_code):
    p = tty_capture(cmd, env=env, shell=True)
    assert p.returncode == return_code

    print(p.stdout)
    print(p.stderr, file=sys.stderr)

    check_output(stdout, p.stdout)
    check_output(stderr, p.stderr)


def tty_capture(cmd, stdin=None, env={}, **kwargs):
    """Capture stdout and stderr of the given command with the given stdin, 
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

    p = subp.Popen(
        cmd,
        bufsize=1,
        stdin=si,
        stdout=so,
        stderr=se, 
        close_fds=True,
        env={**os.environ, 'COLUMNS': '80', **env},
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

def check_output(pattern, actual):
    print(pattern)
    pattern = pattern.format(DATE=DATE).strip()
    actual = actual.replace('\r', '')
    assert re.match(pattern, actual, flags=re.DOTALL)

