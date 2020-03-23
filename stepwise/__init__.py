#!/usr/bin/env python3

"""
Wetlab protocols that follow the Unix philosophy.
"""

__version__ = '0.1.0'

from .protocol import *
from .library import *
from .reaction import *
from .printer import *
from .config import *
from .errors import *

from pathlib import Path

class Builtins:
    protocol_dir = Path(__file__).parent / 'builtins'
