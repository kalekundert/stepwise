#!/usr/bin/env python3

import sys
import shlex
import appcli
import autoprop

from inform import warn, format_range
from .config import StepwiseConfig, PresetConfig
from .errors import *

@autoprop
class Printer:
    __config__ = [
            PresetConfig,
            StepwiseConfig,
    ]

    presets = appcli.param(
            StepwiseConfig,
            default_factory=dict,
            pick=list,
    )
    page_height = appcli.param(
            PresetConfig,
            default=56,
    )
    page_width = appcli.param(
            PresetConfig,
            default=78,
    )
    content_width = appcli.param(
            PresetConfig,
            default=53,
    )
    margin_width = appcli.param(
            PresetConfig,
            default=10,
    )
    paps_flags = appcli.param(
            PresetConfig,
            default='--font "FreeMono 12" --paper letter --left-margin 0 --right-margin 0 --top-margin 12 --bottom-margin 12',
    )
    lpr_flags = appcli.param(
            PresetConfig,
            default='-o sides=one-sided',
    )

    def __init__(self, preset=None):
        self.preset = preset or get_default_printer_name()

    def get_name(self):
        return self.preset

    def set_name(self, name):
        self.preset = name

    def truncate_lines(self, lines):
        def do_truncate(line):
            line_width = self.page_width - self.margin_width
            if len(line) > line_width:
                return line[:line_width - 1] + '…'
            else:
                return line

        return [do_truncate(x) for x in lines]

    def check_for_long_lines(self, lines):
        too_long_lines = []

        for lineno, line in enumerate(lines, 1):
            line = line.rstrip()
            if len(line) > self.content_width:
                too_long_lines.append(lineno)

        if len(too_long_lines) == 0:
            return
        elif len(too_long_lines) == 1:
            warning = "line {} is more than {} characters long."
        else:
            warning = "lines {} are more than {} characters long."

        warning = warning.format(
                format_range(too_long_lines),
                self.content_width,
        )
        raise PrinterWarning(warning)
        
    def make_pages(self, lines):
        """
        Split the given content into pages by trying to best take advantage of 
        natural paragraph breaks.

        The return value is a list of "pages", where each page is a list of lines 
        (without trailing newlines).
        """
        pages = []
        current_page = []
        skip_next_line = False

        def add_page(current_page):
            if any(line.strip() for line in current_page):
                pages.append(current_page[:])
            current_page[:] = []

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

                if len(current_page) + (j-i) > self.page_height or j == i+1:
                    skip_next_line = (j == i+1)
                    add_page(current_page)
                elif current_page:
                    current_page.append(line_i)

        add_page(current_page)
        return pages

    def add_margin(self, pages):
        """
        Add a margin on the left to leave room for holes to be punched.
        """
        left_margin = ' ' * self.margin_width + '│ '
        return [[left_margin + line for line in page] for page in pages]

    def print_pages(self, pages):
        """
        Print the given pages.
        """
        from subprocess import Popen, PIPE
        form_feed = ''
        document = form_feed.join(
                ('\n'.join(x) for x in pages)
        ).encode()
        print_cmd = ' | '.join([
                f'paps {self.paps_flags}',
                f'lpr {self.lpr_flags}',
        ])
        lpr = Popen(print_cmd, shell=True, stdin=PIPE)
        lpr.communicate(input=document)

    def print_files(self, files):
        from subprocess import run

        if files:
            lpr = ['lpr', *shlex.split(self.lpr_flags), *files]
            run(lpr)

def format_protocol(protocol, printer=None, **kwargs):
    printer = printer or Printer()
    return protocol.format_text(printer.content_width, **kwargs)

def print_protocol(protocol, printer):
    text = format_protocol(
            protocol, printer,
            truncate_width=printer.page_width - printer.margin_width,
    )
    lines = text.splitlines()
    lines = printer.truncate_lines(lines)

    try:
        printer.check_for_long_lines(lines)
    except PrinterWarning as err:
        err.report(informant=warn)

    pages = printer.make_pages(lines)
    pages = printer.add_margin(pages)

    printer.print_pages(pages)
    printer.print_files(protocol.attachments)

def get_default_printer_name():
    import re
    from subprocess import run

    lpstat = shlex.split('lpstat -d')
    try:
        p = run(lpstat, capture_output=True, text=True)
    except FileNotFoundError:
        return None

    if p.returncode == 0:
        m = re.match(r'system default destination: (.*)$', p.stdout)
        return m.group(1).strip() if m else None
    else:
        return None

