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

    def __init__(self, name, collections):
        codicil = f"no protocols matching '{name}' in:\n"
        for collection in collections:
            codicil += f"    {collection.name}\n"

        super().__init__(codicil=codicil)


class MultipleProtocolsFound(LoadError):

    def __init__(self, tag, entries):
        codicil = f"multiple protocols matching '{tag}':\n"
        for entry in entries:
            codicil += f"    {entry.name}\n"

        super().__init__(codicil=codicil)


class PrinterWarning(IOError):
    pass
