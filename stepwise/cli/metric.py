#!/usr/bin/env python3

import byoc
from stepwise import StepwiseCommand

class Metric(StepwiseCommand):
    """\
Display a table of metric prefixes.

Usage:
    stepwise metric
"""
    __config__ = [
            byoc.DocoptConfig,
    ]
    
    def main(self):
        byoc.load(self)
        print("""\
yotta  Y  10²⁴
zetta  Z  10²¹
exa    E  10¹⁸
peta   P  10¹⁵
tera   T  10¹²
giga   G  10⁹
mega   M  10⁶
kilo   k  10³
          10⁰
milli  m  10⁻³
micro  μ  10⁻⁶
nano   n  10⁻⁹
pico   p  10⁻¹²
femto  f  10⁻¹⁵
atto   a  10⁻¹⁸
zepto  z  10⁻²¹
yocto  y  10⁻²⁴""")
