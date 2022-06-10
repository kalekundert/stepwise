#!/usr/bin/env python3

import stepwise
import pytest
import parametrize_from_file
import math

from pytest import approx
from parametrize_from_file import Namespace, error_or, defaults, cast
from voluptuous import Schema, Invalid, Coerce, And, Or, Optional
from unittest.mock import Mock, MagicMock
from contextlib import nullcontext
from pathlib import Path

TEST_DIR = Path(__file__).parent
parametrize = pytest.mark.parametrize

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

def eval_db(reagents):
    db = freezerbox.Database()
    schema = Schema(
            empty_ok({
                str: eval_freezerbox,
            }),
    )

    for tag, reagent in schema(reagents).items():
        db[tag] = reagent

    return db

def empty_ok(x):
    return Or(x, And('', lambda y: type(x)()))


with_py = Namespace(
        inf=math.inf,
)
with_sw = Namespace(
        'import stepwise',
        'from stepwise import *',
        TEST_DIR=TEST_DIR,
)
