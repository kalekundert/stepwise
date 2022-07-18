#!/usr/bin/env python3

import stepwise
import pytest
import parametrize_from_file

from pytest import approx
from pytest_unordered import unordered, UnorderedList
from pytest_tmp_files import tmp_file_type
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

@tmp_file_type('xlsx')
def make_xlsx_file(path, meta):
    import csv, io, openpyxl
    wb = openpyxl.Workbook()

    def iter_worksheets():
        for i, title in enumerate(meta['sheets']):
            if i == 0:
                wb.active.title = title
                yield wb.active
            else:
                yield wb.create_sheet(title)

    for ws in iter_worksheets():
        content = meta['sheets'][ws.title]
        content_io = io.StringIO(content)

        for i, row in enumerate(csv.reader(content_io), 1):
            for j, value in enumerate(row, 1):
                ws.cell(i, j).value = value

    wb.save(path)

