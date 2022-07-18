#!/usr/bin/env python3

"""
Wetlab protocols that follow the Unix philosophy.
"""

__version__ = '0.39.1'

from .protocol import *
from .reaction import *
from .quantity import *
from .format import *
from .library import *
from .printer import *
from .config import *
from .errors import *
from .utils import *

from pathlib import Path
from inform import Inform

Inform(stream_policy='header')

class Builtins:
    protocol_dir = Path(__file__).parent / 'builtins'
    priority = 0
