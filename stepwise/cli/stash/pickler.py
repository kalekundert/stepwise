#!/usr/bin/env python3

import pickle
from inform import fatal
from stepwise import Protocol, pl, pre

dumps = pickle.dumps

def loads(*args, **kwargs):
    try:
        return pickle.loads(*args, **kwargs)
    except Exception as err:
        return f"failed to unpickle stashed protocol:\n{err.__class__.__name__}: {err}"
