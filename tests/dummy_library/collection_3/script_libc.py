#!/usr/bin/env python3

import ctypes
libc = ctypes.CDLL(None)

libc.puts(b'- libc')

