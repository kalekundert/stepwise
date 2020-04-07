#!/usr/bin/env python3

from more_itertools import only

def tabulate(rows, header=None, footer=None, alignments=None):
    table_unfmt = _concat_rows(rows, header, footer)
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
    if header:
        table_fmt.insert(1, rule)
    if footer:
        table_fmt.insert(-1, rule)

    return '\n'.join(table_fmt)


def _concat_rows(rows, header, footer):
    table = []

    def append(row):
        table.append([str(x) for x in row])

    if header:
        append(header)

    for row in rows:
        append(row)

    if footer:
        append(footer)

    return table

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
