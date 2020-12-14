#!/usr/bin/env python3

from stepwise.printer import *
from stepwise import PrinterWarning
from utils import *

class DummyPrinter:
    pass

@parametrize_via_toml('test_printer.toml')
def test_truncate_lines(text_in, text_out, page_width, margin_width):
    printer = DummyPrinter()
    printer.page_width = page_width
    printer.margin_width = margin_width

    assert truncate_lines(text_in, printer) == text_out

@parametrize_via_toml('test_printer.toml')
def test_check_for_long_lines(text, content_width, err):
    printer = DummyPrinter()
    printer.content_width = content_width

    if err is False:
        check_for_long_lines(text, printer)
    else:
        with pytest.raises(PrinterWarning, match=err):
            check_for_long_lines(text, printer)

@parametrize_via_toml('test_printer.toml')
def test_make_pages(text, page_height, pages):
    printer = DummyPrinter()
    printer.page_height = page_height

    assert make_pages(text, printer) == pages

@parametrize_via_toml('test_printer.toml')
def test_add_margin(margin_width, pages_before, pages_after):
    printer = DummyPrinter()
    printer.margin_width = margin_width

    assert add_margin(pages_before, printer) == pages_after
