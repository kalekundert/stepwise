#!/usr/bin/env python3

import sys, os.path

argv = ','.join([
    os.path.basename(sys.argv[0]),
    *sys.argv[1:],
])

print(f"- argv {argv}")
