#!/usr/bin/env python3

import stepwise

p = stepwise.Protocol()
p += "load"
p += stepwise.load("main")
p += stepwise.load("argv 1 2")
p += stepwise.load("import")

p.print()
