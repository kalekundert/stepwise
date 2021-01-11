#!/usr/bin/env python3

"""\
Indicate the conditions to test in the following steps.

Usage:
    reactions <table> [-k <definition>]...

Arguments:
    <table>
        The path to a CSV, TSV, or XLSX file detailing the conditions to test.  
        The table should contain a row for each condition and a column for each 
        reaction.  The first column should list the names of the conditions.  
        The remaining columns should indicate whether or not the corresponding 
        condition applies to the corresponding reaction.

Options:
    -k --key <definition>
        The definition of a shorthand symbol used in the above table.
"""

from docopt import docopt
from stepwise import Protocol, tabulate
from pathlib import Path
from inform import fatal
from warnings import filterwarnings
import pandas as pd

filterwarnings('ignore', "Workbook contains no default style, apply openpyxl's default", UserWarning)
filterwarnings('ignore', "The default value of regex will change from True to False in a future version.", FutureWarning)

args = docopt(__doc__)
path = Path(args['<table>'])
keys = args['--key']

loaders = {
        '.xlsx': lambda p: pd.read_excel(p, header=None, dtype=str),
        '.csv':  lambda p: pd.read_csv(p, header=None, dtype=str),
        '.tsv':  lambda p: pd.read_csv(p, sep='\t', header=None, dtype=str),
}

try:
    df = loaders[path.suffix](path)
except KeyError:
    err = f"""\
Unsupported file extension: *{path.suffix}
Expected one of the following: *.xlsx *.csv *.tsv"""
    fatal(err, culprit=path)
except FileNotFoundError:
    fatal("no such file", culprit=path)

# Add colons to the condition names:
df[0] = df[0].map('{}:'.format)

# Replace hyphens with true minus-signs:
for c in df.columns[1:]:
    df[c] = df[c].str.replace(r'^-$', '−')

table = df.values.tolist()
align = ['<'] + (len(df.columns) - 1) * ['^']
br = '\n'

p = Protocol()
p += f"""\
In the following steps, setup these reactions:

{tabulate(table, align=align)}

{br.join(keys)}
"""

p.print()

