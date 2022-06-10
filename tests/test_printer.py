#!/usr/bin/env python3

from stepwise.printer import *
from stepwise import PrinterWarning
from param_helpers import *

class DummyPrinter(Printer):
    pass

@parametrize_from_file
def test_truncate_lines(text_in, text_out, page_width, margin_width):
    printer = DummyPrinter()
    printer.page_width = int(page_width)
    printer.margin_width = int(margin_width)

    assert printer.truncate_lines(text_in) == text_out

@parametrize_from_file(
        schema=with_sw.error_or(),
)
def test_check_for_long_lines(text, content_width, error):
    printer = DummyPrinter()
    printer.content_width = int(content_width)

    with error:
        printer.check_for_long_lines(text)

@parametrize_from_file
def test_make_pages(text, page_height, pages):
    printer = DummyPrinter()
    printer.page_height = int(page_height)

    assert printer.make_pages(text) == pages

@parametrize_from_file
def test_add_margin(margin_width, pages_before, pages_after):
    printer = DummyPrinter()
    printer.margin_width = int(margin_width)

    assert printer.add_margin(pages_before) == pages_after
