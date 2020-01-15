#!/usr/bin/env python3

import shlex
import subprocess as subp
from .config import load_config

class PrinterOptions:

    def __init__(self, **kwargs):
        self.options = kwargs

    def __repr__(self):
        kwargs = ', '.join([f'{k}={repr(v)}' for k,v in self.options])
        return f'PrinterOptions({kwargs})'

    def __getattr__(self, key):
        return self.options[key]

    @classmethod
    def from_config(cls, config, printer=None):
        if printer is None:
            printer = get_default_printer()

        defaults = config.printer.data.get('default', {})
        overrides = config.printer.data.get(printer, {})

        return cls(**defaults, **overrides)

def print_protocol(protocol, printer=None):
    options = load_printer_options(printer)
    check_for_long_lines(protocol, options)
    pages = make_pages(protocol, options)
    pages = add_margin(pages, options)
    print_pages(pages, options)

def load_printer_options(printer=None):
    config = load_config()
    return PrinterOptions.from_config(config, printer)

def check_for_long_lines(text, options):
    lines = str(text).splitlines()
    too_long_lines = []

    for lineno, line in enumerate(lines, 1):
        line = line.rstrip()
        if len(line) > options.content_width:
            too_long_lines.append(lineno)

    if len(too_long_lines) == 0:
        return False
    elif len(too_long_lines) == 1:
        warning = "Warning: line {} is more than {} characters long."
    else:
        warning = "Warning: lines {} are more than {} characters long."

    warning = warning.format(
            pretty_range(too_long_lines),
            options.content_width,
    )
    print(warning, file=sys.stderr)
    return True
    
def make_pages(text, options):
    """
    Split the given protocol into pages by trying to best take advantage of 
    natural paragraph breaks.
    """
    lines = str(text).splitlines()

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
    return ['\n'.join(left_margin + line for line in page) for page in pages]

def print_pages(pages, options):
    """
    Print the given pages.
    """
    from subprocess import Popen, PIPE
    form_feed = ''
    print_cmd = ' | '.join([
            f'paps {options.paps_flags}',
            f'lpr {options.lpr_flags}',
    ])
    lpr = Popen(print_cmd, shell=True, stdin=PIPE)
    lpr.communicate(input=form_feed.join(pages).encode())

def get_default_printer():
    lpstat = shlex.split('lpstat -d')
    p = subp.run(lpstat, capture_output=True, text=True)

    if p.returncode == 0:
        return p.stdout.split(':')[1].strip()
    else:
        return None

