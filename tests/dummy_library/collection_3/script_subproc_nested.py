#!/usr/bin/env python3

from subprocess import run

# Invoking stepwise via a subprocess is bad practice.  Using `stepwise.load()` 
# does the same thing, and will be much faster because it won't have to start a 
# new process.  However, this behavior is supported in keeping with the 
# principle of least surprise:  it's clear what the user intends, and the same 
# behavior works with shell scripts.
#
# This is also a pretty rigorous test, because stdout will contain a binary 
# pickle.  This cause problems if the parser is looking for a text protocol, or 
# even if it assumes that stdout is utf8-encoded.

run(['stepwise', 'step', 'nested'])

