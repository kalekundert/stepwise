#!/usr/bin/env python3

from param_helpers import *
from stepwise import unanimous

@parametrize_from_file(
        schema=[
            cast(items=eval, kwargs=with_py.eval, expected=eval),
            defaults(kwargs={}),
            error_or('expected'),
        ],
)
def test_unanimous(items, kwargs, expected, error):
    with error:
        assert unanimous(items, **kwargs) == expected


