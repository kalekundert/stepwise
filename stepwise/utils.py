#!/usr/bin/env python3

from inform import Error

class StepwiseError(Error):
    pass

class UsageError(StepwiseError):
    pass

class LoadError(StepwiseError):
    pass

class ParseError(LoadError):
    pass

class NoProtocolsFound(LoadError):

    def __init__(self, name, search_dirs):
        self.name = name
        self.search_dirs = search_dirs

    def __str__(self):
        err = f"no protocols matching '{self.name}' in:\n"
        for dir in self.search_dirs:
            err += f"    {dir['dir']}\n"
        return err

class MultipleProtocolsFound(LoadError):

    def __init__(self, name, hits):
        self.name = name
        self.hits = hits

    def __str__(self):
        err = f"multiple protocols matching '{self.name}':\n"
        for hit in self.hits:
            err += f"    {hit['relpath'].with_suffix('')}\n"
        return err
