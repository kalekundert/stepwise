#!/usr/bin/env python3

from itertools import zip_longest
from more_itertools import only

def tabulate(rows, header=None, footer=None, alignments=None):
    table_unfmt, i_header, i_footer = _concat_rows(rows, header, footer)
    num_cols = _count_cols(table_unfmt)
    col_widths = _measure_cols(table_unfmt)
    col_alignments = alignments or _auto_align(rows)

    pad = 2
    rule = '─' * (sum(col_widths) + pad * (num_cols - 1))
    row_template = (pad * ' ').join(
            '{{!s:{}{}}}'.format(col_alignments[i], col_widths[i])
            for i in range(num_cols)
    )

    table_fmt = [
        row_template.format(*x).rstrip()
        for x in table_unfmt
    ]

    # Add the footer first, because it won't affect the header index.
    if footer:
        table_fmt.insert(i_footer, rule)
    if header:
        table_fmt.insert(i_header, rule)

    return '\n'.join(table_fmt)


def _concat_rows(rows, header, footer):
    table = []

    def append(row, valign='top'):
        extra_rows = _split_row([str(x) for x in row], valign)
        table.extend(extra_rows)

    if header:
        append(header, 'bottom')

    i_header = len(table)

    for row in rows:
        append(row)

    i_footer = len(table)

    if footer:
        append(footer)

    return table, i_header, i_footer

def _split_row(row, align='top'):
    alignments = {
            'top': lambda x: x,
            'bottom': reversed,
    }
    f = alignments[align]

    cells_rev = [f(x.split('\n')) for x in row]
    rows_rev = zip_longest(*cells_rev, fillvalue='')
    return list(f([list(x) for x in rows_rev]))

def _auto_align(rows):
    def is_col_numeric(xs):
        return all(map(is_numeric, xs))

    def is_numeric(x):
        try:
            float(x)
        except ValueError:
            return False
        else:
            return True

    return [
            '>' if is_col_numeric(col) else '<'
            for col in zip(*rows)
    ]

def _count_cols(table):
    return only(
            x := {len(x) for x in table},
            default=0,
            too_long=ValueError(f"rows have different numbers of columns: {','.join(str(x) for x in sorted(x))}"),
    )

def _measure_cols(table):
    return [
            max(len(x) for x in xs)
            for xs in zip(*table)
    ]
