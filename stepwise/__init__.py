#!/usr/bin/env python3

"""
Wetlab protocols that follow the Unix philosophy.
"""

__version__ = '0.1.0'

from .protocol import *
from .reaction import *
from .cli import *
from .printer import *
from .config import *
from .utils import *

from pathlib import Path
protocol_dirs = [
        Path(__file__).parent / 'builtins'
]
