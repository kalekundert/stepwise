#!/usr/bin/env python3

import cProfile as profile, pstats
from stepwise.cli.main import main

with profile.Profile() as pr:
    try: main()
    except: pass

pstats.Stats(pr)\
        .strip_dirs()\
        .sort_stats('cumtime')\
        .print_stats()



