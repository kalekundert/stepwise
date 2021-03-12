#!/usr/bin/env python3

import pickle
from inform import fatal
from stepwise import Protocol, pl, pre

dumps = pickle.dumps

class UnreadableProtocol(Protocol):

    def __init__(self, err):
        super().__init__(steps=['dummy'])
        self.err = err

    def format_text(self, *args, **kwargs):
        fatal(f"failed to unpickle stashed protocol:\n{self.err.__class__.__name__}: {self.err}")

    def pick_slug(self):
        return ''

def loads(*args, **kwargs):
    try:
        return pickle.loads(*args, **kwargs)
    except Exception as err:
        return UnreadableProtocol(err)
