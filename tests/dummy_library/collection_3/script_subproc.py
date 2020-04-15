#!/usr/bin/env python3

import os
from subprocess import run

os.system('echo "- os.system"')
run(['echo', '- subprocess.run'])

