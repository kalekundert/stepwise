#!/usr/bin/env python3

from inform import Error

class StepwiseError(Error):
    pass

class UsageError(StepwiseError):
    pass

class IOError(StepwiseError, IOError):
    pass

class LoadError(IOError):
    pass

class ParseError(LoadError):
    pass

class VersionControlWarning(LoadError):
    pass

class NoProtocolsFound(LoadError):

    def __init__(self, name, search_dirs):
        codicil = f"no protocols matching '{name}' in:\n"
        for dir in search_dirs:
            codicil += f"    {dir['dir']}\n"

        super().__init__(codicil=codicil)

class MultipleProtocolsFound(LoadError):

    def __init__(self, name, hits):
        codicil = f"multiple protocols matching '{name}':\n"
        for hit in hits:
            codicil += f"    {hit['relpath'].with_suffix('')}\n"

        super().__init__(codicil=codicil)

class PrinterWarning(IOError):
    pass
