#!/usr/bin/env python3

import stepwise
import pytest
import parametrize_from_file

from pytest import approx
from pytest_unordered import unordered, UnorderedList
from parametrize_from_file import Namespace, defaults, cast, error, error_or
from voluptuous import Schema, Invalid, Coerce, And, Or, Optional
from unittest.mock import Mock, MagicMock
from contextlib import nullcontext
from pathlib import Path
from math import inf

TEST_DIR = Path(__file__).parent
parametrize = pytest.mark.parametrize

Int = Coerce(int)
Float = Coerce(float)

class Params:

    @classmethod
    def parametrize(cls, f):
        args = cls.args

        params = []
        for k, v in cls.__dict__.items():
            if k.startswith('params'):
                params.extend(v)

        # Could also check to make sure parameters make sense.

        return pytest.mark.parametrize(args, params)(f)

with_py = Namespace(inf=inf)
with_sw = with_py.fork(
        'import stepwise',
        'from stepwise import *',
        TEST_DIR=TEST_DIR,
)
