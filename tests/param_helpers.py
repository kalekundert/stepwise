#!/usr/bin/env python3

import stepwise
import pytest
import parametrize_from_file
import math

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


class do_with:

    def __init__(self, globals=None, **kw_globals):
        self.globals = globals or {}
        self.globals.update(kw_globals)

    def all(self, module):
        try:
            keys = module.__all__
        except AttributeError:
            keys = module.__dict__

        self.globals.update({
                k: module.__dict__[k]
                for k in keys
        })
        return self

class eval_with(do_with):

    def __call__(self, src):
        try:
            if isinstance(src, list):
                return [self(x) for x in src]
            elif isinstance(src, dict):
                return {self(k): self(v) for k, v in src.items()}
            else:
                return eval(src, self.globals)

        except Exception as err:
            raise Invalid(str(err)) from err

class exec_with(do_with):

    def __init__(self, get, globals=None, **kw_globals):
        super().__init__(globals, **kw_globals)
        self.get = get

    def __call__(self, src):
        globals = self.globals.copy()

        try:
            exec(src, globals)
        except Exception as err:
            raise Invalid(str(err)) from err

        if callable(self.get):
            return self.get(globals)
        else:
            return globals[self.get]

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

def error_or(expected):
    schema = {}

    # Either specify an error or an expected value, not both.
    # KBK: This doesn't work for some reason.
    #schema[Or('error', *expected, only_one=True)] = object

    schema[Optional('error', default='none')] = error

    def check(schema):
        # This function basically just reimplements `Or`, but with a better 
        # error message.  The error message for `Or` is confusing because it 
        # only mentions the first option and not the second.  That's especially 
        # bad in this case, where the first option is basically an internal 
        # implementation detail.  This function changes the error message so 
        # that only the second option is mentioned, which is the least 
        # confusing in this case.
        # 
        # It's worth noting that the real problem is that voluptuous checks 
        # default values.  I can't imagine a case where this is actually 
        # useful. I might think about making a PR for that.

        def do_check(x):
            if isinstance(x, MagicMock):
                return x
            return Schema(schema)(x)
        return do_check

    schema.update({
        Optional(k, default=MagicMock()): check(v)
        for k, v in expected.items()
    })
    return schema

# Something to think about: I'd like to put a version of this function in the 
# `parametrize_from_file` package.  I need a general way to specify the local 
# variables, though.  And to `eval()` the exception type...

def error(x):
    if x == 'none':
        return nullcontext()

    err_eval = eval_stepwise
    if isinstance(x, str):
        err_type = err_eval(x)
        err_messages = []
    else:
        err_type = err_eval(x['type'])
        err_messages = x.get('message', [])
        if not isinstance(err_messages, list):
            err_messages = [err_messages]

    # Normally I'd use `@contextmanager` to make a context manager like this, 
    # but generator-based context managers cannot be reused.  This is a problem 
    # for tests, because if a test using this context manager is parametrized, 
    # the same context manager instance will need to be reused multiple times.  
    # The only way to support this is to implement the context manager from 
    # scratch.

    class expect_error:

        def __enter__(self):
            self.raises = pytest.raises(err_type)
            self.err = self.raises.__enter__()

        def __exit__(self, *args):
            if self.raises.__exit__(*args):
                for msg in err_messages:
                    self.err.match(msg)
                return True

    return expect_error()

eval_stepwise = eval_with(
        stepwise=stepwise,
        TEST_DIR=TEST_DIR,
).all(stepwise)
eval_pytest = eval_with().all(pytest)
eval_python = eval_with(inf=math.inf)
