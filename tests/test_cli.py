#!/usr/bin/env python3

import pytest, sys, os, re
from utils import *

DATE = r'\w+ \d{1,2}, \d{4}'

@pytest.mark.slow
@parametrize_via_toml('test_cli.toml')
def test_main(cmd, env, stdout, stderr, return_code):
    check_command(cmd, stdout, stderr, return_code, env)


def check_command(cmd, stdout='^$', stderr='^$', return_code=0, env={}, home=None):
    if home is None:
        home = Path(__file__).parent / 'dummy_home'

    env = {**os.environ, 'COLUMNS': '80', 'HOME': str(home), **env}

    # Stepwise only produces text output if (i) it detects that it is attached 
    # to a TTY or (ii) it is given the `-x` flag.  If neither condition is met, 
    # it produces a binary pickle meant to be consumed by another stepwise 
    # command.
    #
    # For testing, we need text output.  The preferred way to do this is by 
    # making pseudo-TTYs for stdout, stderr, and stdin, since this best mimics 
    # the environment that stepwise is meant to run in.  Unfortunately, the 
    # python package for making pseudo-TTYs does not work on Windows, so on 
    # that platform, instead edit the command to add the `-x` flag.

    if sys.platform != 'win32':
        p = tty_capture(cmd, env=env, shell=True, cwd=str(home))
    else:
        from subprocess import run
        i = cmd.rfind('stepwise') + len('stepwise')
        cmd = cmd[:i] + ' -x' + cmd[i:]
        p = run(cmd, env=env, capture_output=True, text=True, shell=True, cwd=str(home))

    print(cmd, file=sys.stderr)
    check_output(p.stderr, stderr, sys.stderr)

    print(cmd)
    check_output(p.stdout, stdout, sys.stdout)

    assert p.returncode == return_code

def check_output(captured, expected, file=sys.stdout):
    expected = expected.format(DATE=DATE).strip()
    captured = captured.replace('\r', '').strip()

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

    p = subp.Popen(
        cmd,
        bufsize=1,
        stdin=si,
        stdout=so,
        stderr=se, 
        close_fds=True,
        env=env,
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

