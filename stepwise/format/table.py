#!/usr/bin/env python3

from math import ceil, inf
from textwrap import shorten
from shutil import get_terminal_size
from itertools import repeat, zip_longest
from more_itertools import only
from inform import plural
from .format import Formatter
from .lists import _replace_list
from .misc import preformatted

_style = {
        'pad': 2,
        'rule': '─',
        'placeholder': '…',
}

class table(Formatter):

    def __init__(
            self,
            rows,
            header=None,
            footer=None,
            *,
            format=None,
            align=None, 
            truncate=None,
            max_width=None,
            style=_style,
    ):
        self.rows = rows
        self.header = header
        self.footer = footer
        self.format = format
        self.align = align
        self.truncate = truncate
        self.max_width = max_width
        self.style = style

    def __eq__(self, other):
        return (
            type(self) == type(other) and
            self.rows == other.rows and
            self.header == other.header and
            self.footer == other.footer and
            self.format == other.format and
            self.align == other.align and
            self.truncate == other.truncate and
            self.max_width == other.max_width and
            self.style == other.style
        )

    def format_text(self, width, **kwargs):
        truncate_width = kwargs.get('truncate_width')

        table = tabulate(
                rows=self.rows,
                header=self.header,
                footer=self.footer,
                format=self.format,
                align=self.align,
                truncate=self.truncate,
                max_width=self.max_width,
                page_width=kwargs.get('truncate_width'),
                style=self.style,
        )
        return preformatted(table).format_text(width, **kwargs)

    def replace_text(self, pattern, repl, **kwargs):

        def replace_row(row):
            return _replace_list(row, pattern, repl, **kwargs)

        if self.header:
            self.header = replace_row(self.header)

        self.rows = [replace_row(row) for row in self.rows]

        if self.footer:
            self.footer = replace_row(self.footer)


def tabulate(
        rows,
        header=None,
        footer=None,
        *,
        format=None,
        align=None, 
        truncate=None,
        max_width=None,
        page_width=None,
        style=_style,
):
    """
    Format tabular information.

    Arguments:
        rows (list of lists): The content of the table.
        header (list of str or True): Text to display above each column.  If 
            ``True``, the first row will be interpreted as the header.
        footer (list of str or True): Text to display below each column.  If 
            ``True``, the last row will be interpreted as the footer.
        format (list of callables): Functions that can be used to convert the 
            cells in each column to strings.  Each function should take one 
            argument (the value to convert) and return a string.
        align (str): Whether each column should be left ('<'), center ('^'), or 
            right ('>') aligned.  By default, columns will be right-aligned if 
            they appear to contain numeric values, and left-aligned otherwise.
        truncate (str): Whether each column can be truncated ('x') or not ('-') 
            to help fit the table within the given `max_width`.
        max_width (int): The maximum width of the table to strive for by 
            truncating columns.  This maximum can be exceeded if `truncate` is 
            not specified, or if the columns specified by `truncate` cannot are 
            too narrow to make up the difference.
        style (dict): Miscellaneous parameters used to render the table.

    Return:
        table (str): The formatted table.

    Example:
        >>> import stepwise
        >>> header = ['Reagent', 'Volume']
        >>> rows = [['enzyme', '1 µL'], ['buffer', '2 µL']]
        >>> stepwise.tabular(rows, header)
        Reagent  Volume
        ───────────────
        enzyme   1 µL
        buffer   2 µL

    """
    table_unfmt, i_header, i_footer = _concat_rows(
            rows,
            header,
            footer,
            format,
    )
    col_widths, table_width = _measure_cols(
            table_unfmt,
            truncate,
            _eval_max_width(max_width, page_width),
            style['pad'],
    )
    col_alignments = align or _auto_align(rows)

    def format_row(row):
        cells = [
                format_cell(*args)
                for args in zip(row, col_widths, col_alignments)
        ]
        pad = style['pad'] * ' '
        return pad.join(cells).rstrip()

    def format_cell(cell, width, align):
        if len(cell) > width:
            if ' ' in cell:
                cell = shorten(cell, width=width, placeholder=style['placeholder'])
            else:
                dots = style['placeholder']
                cell = cell[:width - len(dots)] + dots
        return f'{cell:{align}{width}}'


    table_fmt = [
        format_row(x)
        for x in table_unfmt
    ]

    # Add the footer first, because it won't affect the header index.
    rule = style['rule'] * table_width
    if footer:
        table_fmt.insert(i_footer, rule)
    if header:
        table_fmt.insert(i_header, rule)

    return '\n'.join(table_fmt)


def _concat_rows(rows, header, footer, format):
    """
    Attach the given `header` and `footer` to the given `rows` to create a 
    complete table.

    Some additional processing is done as well.  The given `format` are 
    used to convert all the values in the table to strings.  Rows containing 
    newlines are split into multiple rows.
    """
    table = []

    if header is True:
        header = rows[0]
        rows = rows[1:]

    if footer is True:
        footer = rows[-1]
        rows = rows[:-1]

    def process(row, format=None, *, valign='top'):
        if not format:
            format = [str] * len(row)
        if len(format) != len(row):
            raise ValueError(f"given {plural(format):# formatter/s}, expected {len(row)}")

        row = [fmt(x) for x, fmt in zip(row, format)]
        row = _split_row(row, valign)
        table.extend(row)

    if header:
        process(header, valign='bottom')

    i_header = len(table)

    for row in rows:
        process(row, format)

    i_footer = len(table)

    if footer:
        process(footer)

    return table, i_header, i_footer

def _split_row(row, align='top'):
    """
    Resolve any newlines in the given row.
    """
    align_funcs = {
            'top': lambda x: x,
            'bottom': reversed,
    }
    f = align_funcs[align]

    cells_rev = [f(x.split('\n')) for x in row]
    rows_rev = zip_longest(*cells_rev, fillvalue='')
    return list(f([list(x) for x in rows_rev]))

def _auto_align(rows):
    """
    Provide a reasonable default alignment for each column.

    Columns that appear to contain numeric values (i.e. numbers with or without 
    units) are right-aligned, while all other columns are left-aligned.
    """

    def is_col_numeric(xs):
        return all(map(is_numeric, xs))

    def is_numeric(x):
        from stepwise import Quantity

        try: float(x)
        except ValueError: pass
        else: return True

        try: Quantity.from_anything(x)
        except ValueError: pass
        else: return True

        return False

    return [
            '>' if is_col_numeric(col) else '<'
            for col in zip(*rows)
    ]

def _eval_max_width(max_width, page_width):
    if not page_width:
        page_width = get_terminal_size().columns - 1

    if not max_width:
        return page_width

    if max_width < 0:
        return page_width + max_width

    return max_width

def _measure_cols(table, truncate, max_width, pad):
    """
    Determine the width of each column.

    In general, the width of a column is the width of the widest cell in that 
    column.  However, the columns indicated by `truncated` may be shortened to 
    keep the table within the given `max_width`.
    """
    num_cols = _count_cols(table)
    col_widths = [
            max(len(x) for x in xs)
            for xs in zip(*table)
    ]

    if truncate and num_cols != len(truncate):
        raise ValueError(f"table has {plural(num_cols):# column/s}, but truncation specified for {len(truncate)}: {truncate!r}")

    sum_col_widths = lambda: sum(col_widths) + pad * max(num_cols - 1, 0)
    table_width = sum_col_widths()
    overfull_width = table_width - max_width

    if max_width > 0 and (overfull_width <= 0 or not truncate):
        return col_widths, table_width

    trunc_cols = [i for i, x in enumerate(truncate) if x == 'x']
    if not trunc_cols:
        return col_widths, table_width

    # There's probably a smarter/faster way to do this...

    while overfull_width > 0:
        widest_col = max(
                trunc_cols, 
                key=lambda i: col_widths[i],
        )
        col_widths[widest_col] -= 1
        overfull_width -= 1

    return col_widths, sum_col_widths()

def _count_cols(table):
    """
    Return the number of columns in the table.

    A `ValueError` is raised if different rows in the table have different 
    numbers of columns.
    """
    return only(
            x := {len(x) for x in table},
            default=0,
            too_long=ValueError(f"rows have different numbers of columns: {','.join(str(x) for x in sorted(x))}"),
    )

