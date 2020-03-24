#!/usr/bin/env python3

import pytest, toml, inspect
from pathlib import Path
from functools import lru_cache

TEST_DIR = Path(__file__).parent

def parametrize_via_toml(relpath):

    def decorator(f):
        # The path is relative to the file the caller is defined in.
        module = inspect.getmodule(f)
        test_path = Path(module.__file__)
        toml_path = test_path.parent / relpath

        all_raw_params = cached_load(toml_path)
        try: raw_params = all_raw_params[f.__name__]
        except KeyError: raise ParametrizeViaTomlError(f"no parameters found for {f.__name__!r}") from None
        raw_args = set.union(*(set(x) for x in raw_params)) - {'id'}

        # Make sure there aren't any missing/extra parameters:
        for params in raw_params:
            if missing := raw_args - set(params):
                missing_str = ', '.join(f"'{x}'" for x in missing)
                raise ValueError(f"{toml_path}: {f.__name__}: missing parameter(s) {missing_str}")

        args = list(raw_args)
        params = [
                pytest.param(*(x[k] for k in args), id=x.get('id', None))
                for x in raw_params
        ]
        return pytest.mark.parametrize(args, params)(f)

    return decorator

@lru_cache
def cached_load(path):
    return toml.load(path)

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

class ParametrizeViaTomlError(Exception):
    pass

