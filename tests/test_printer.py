#!/usr/bin/env python3

from stepwise.printer import *
from stepwise import PrinterWarning
from utils import *

def test_repr():
    options = PrinterOptions(content_width=53)
    assert repr(options) == 'PrinterOptions(content_width=53)'

@parametrize_via_toml('test_printer.toml')
def test_check_for_long_lines(text, content_width, err):
    options = PrinterOptions(content_width=content_width)

    if err is False:
        check_for_long_lines(text, options)
    else:
        with pytest.raises(PrinterWarning, match=err):
            check_for_long_lines(text, options)

@parametrize_via_toml('test_printer.toml')
def test_make_pages(text, page_height, pages):
    options = PrinterOptions(page_height=page_height)
    assert make_pages(text, options) == pages

@parametrize_via_toml('test_printer.toml')
def test_add_margin(margin_width, pages_before, pages_after):
    options = PrinterOptions(margin_width=margin_width)
    assert add_margin(pages_before, options) == pages_after
