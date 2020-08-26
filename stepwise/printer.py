#!/usr/bin/env python3

import sys
import shlex
from inform import warn
from nonstdlib import pretty_range
from .config import load_config
from .errors import *

class PrinterOptions:

    def __init__(self, printer, options):
        self.printer = printer
        self.options = options

    def __repr__(self):
        return f'{self.__class__.__qualname__}(printer={self.printer!r}, options={self.options!r})'

    def __getattr__(self, key):
        return self.options[key]

    @classmethod
    def from_config(cls, config, printer=None):
        if printer is None:
            printer = get_default_printer()

        defaults = config.printer.data.get('default', {})
        overrides = config.printer.data.get(printer, {})
        options = {**defaults, **overrides}

        return cls(printer, options)

def print_protocol(protocol, printer=None):
    options = load_printer_options(printer)

    lines = str(protocol).splitlines()
    lines = truncate_lines(lines, options)

    try:
        check_for_long_lines(lines, options)
    except PrinterWarning as err:
        err.report(informant=warn)

    pages = make_pages(lines, options)
    pages = add_margin(pages, options)

    print_pages(pages, options)
    print_files(protocol.attachments, options)

    return options

def load_printer_options(printer=None):
    config = load_config()
    return PrinterOptions.from_config(config, printer)

def truncate_lines(lines, options):
    def do_truncate(line):
        line_width = options.page_width - options.margin_width
        if len(line) > line_width:
            return line[:line_width - 1] + '…'
        else:
            return line

    return [do_truncate(x) for x in lines]

def check_for_long_lines(lines, options):
    too_long_lines = []

    for lineno, line in enumerate(lines, 1):
        line = line.rstrip()
        if len(line) > options.content_width:
            too_long_lines.append(lineno)

    if len(too_long_lines) == 0:
        return
    elif len(too_long_lines) == 1:
        warning = "line {} is more than {} characters long."
    else:
        warning = "lines {} are more than {} characters long."

    warning = warning.format(
            pretty_range(too_long_lines),
            options.content_width,
    )
    raise PrinterWarning(warning)
    
def make_pages(lines, options):
    """
    Split the given protocol into pages by trying to best take advantage of 
    natural paragraph breaks.

    The return value is a list of "pages", where each page is a list of lines 
    (without trailing newlines).
    """
    pages = []
    current_page = []
    skip_next_line = False

    for i, line_i in enumerate(lines):

        if skip_next_line:
            skip_next_line = False
            continue

        # If the line isn't blank, add it to the current page like usual.

        if line_i.strip():
            current_page.append(line_i)

        # If the line is blank, find the next blank line and see if it fits on 
        # the same page.  If it does, add the blank line to the page and don't 
        # do anything special.  If it doesn't, make a new page.  Also interpret 
        # two consecutive blank lines as a page break.

        else:
            for j, line_j in enumerate(lines[i+1:], i+1):
                if not line_j.strip():
                    break
            else:
                j = len(lines)

            if len(current_page) + (j-i) > options.page_height or j == i+1:
                skip_next_line = (j == i+1)
                pages.append(current_page)
                current_page = []
            else:
                current_page.append(line_i)

    pages.append(current_page)
    return pages

def add_margin(pages, options):
    """
    Add a margin on the left to leave room for holes to be punched.
    """
    left_margin = ' ' * options.margin_width + '│ '
    return [[left_margin + line for line in page] for page in pages]

def print_pages(pages, options):
    """
    Print the given pages.
    """
    from subprocess import Popen, PIPE
    form_feed = ''
    document = form_feed.join(
            ('\n'.join(x) for x in pages)
    ).encode()
    print_cmd = ' | '.join([
            f'paps {options.paps_flags}',
            f'lpr {options.lpr_flags}',
    ])
    lpr = Popen(print_cmd, shell=True, stdin=PIPE)
    lpr.communicate(input=document)

def print_files(files, options):
    from subprocess import run

    if files:
        lpr = ['lpr', *shlex.split(options.lpr_flags), *files]
        run(lpr)

def get_default_printer():
    from subprocess import run

    lpstat = shlex.split('lpstat -d')
    p = run(lpstat, capture_output=True, text=True)

    if p.returncode == 0:
        return p.stdout.split(':')[1].strip()
    else:
        return None

