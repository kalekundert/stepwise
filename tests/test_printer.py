#!/usr/bin/env python3

from stepwise.printer import *
from stepwise import PrinterWarning
from param_helpers import *

class DummyPrinter(Printer):
    pass

@parametrize_from_file(
        schema=Schema({
            'text_in': [str],
            'text_out': [str],
            'page_width': Coerce(int),
            'margin_width': Coerce(int),
        }),
)
def test_truncate_lines(text_in, text_out, page_width, margin_width):
    printer = DummyPrinter()
    printer.page_width = page_width
    printer.margin_width = margin_width

    assert printer.truncate_lines(text_in) == text_out

@parametrize_from_file(
        schema=Schema({
            'text': [str],
            'content_width': Coerce(int),
            **error_or({}),
        }),
)
def test_check_for_long_lines(text, content_width, error):
    printer = DummyPrinter()
    printer.content_width = content_width

    with error:
        printer.check_for_long_lines(text)

@parametrize_from_file(
        schema=Schema({
            'text': empty_ok([str]),
            'page_height': Coerce(int),
            'pages': empty_ok([[str]]),
        }),
)
def test_make_pages(text, page_height, pages):
    printer = DummyPrinter()
    printer.page_height = page_height

    assert printer.make_pages(text) == pages

@parametrize_from_file(
        schema=Schema({
            'margin_width': Coerce(int),
            'pages_before': empty_ok([[str]]),
            'pages_after': empty_ok([[str]]),
        }),
)
def test_add_margin(margin_width, pages_before, pages_after):
    printer = DummyPrinter()
    printer.margin_width = margin_width

    assert printer.add_margin(pages_before) == pages_after
