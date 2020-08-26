#!/usr/bin/env python3

from stepwise.printer import *
from stepwise import PrinterWarning
from utils import *

def test_repr():
    options = PrinterOptions('PrinterName', dict(content_width=53))
    assert repr(options) == "PrinterOptions(printer='PrinterName', options={'content_width': 53})"

@parametrize_via_toml('test_printer.toml')
def test_truncate_lines(text_in, text_out, page_width, margin_width):
    options = PrinterOptions('PrinterName', dict(
        page_width=page_width,
        margin_width=margin_width,
    ))
    assert truncate_lines(text_in, options) == text_out

@parametrize_via_toml('test_printer.toml')
def test_check_for_long_lines(text, content_width, err):
    options = PrinterOptions('PrinterName', dict(content_width=content_width))

    if err is False:
        check_for_long_lines(text, options)
    else:
        with pytest.raises(PrinterWarning, match=err):
            check_for_long_lines(text, options)

@parametrize_via_toml('test_printer.toml')
def test_make_pages(text, page_height, pages):
    options = PrinterOptions('PrinterName', dict(page_height=page_height))
    assert make_pages(text, options) == pages

@parametrize_via_toml('test_printer.toml')
def test_add_margin(margin_width, pages_before, pages_after):
    options = PrinterOptions('PrinterName', dict(margin_width=margin_width))
    assert add_margin(pages_before, options) == pages_after
