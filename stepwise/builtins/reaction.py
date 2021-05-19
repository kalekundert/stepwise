#!/usr/bin/env python3

"""\
Display a reaction table.

Usage:
    reaction <reagent;stock;volume;mm>... [-S <step> | -s <kind>] [-n <rxns>]
        [-v <vol>] [-V <factor>] [-i <info>]... [-x <extra>] [options]

Arguments:
    <reagent;stock;volume;mm>
        A description of a reagent in the reaction.  Each description must 
        consist of the four fields listed above, separated by semi-colons. In 
        greater detail:

        name:
            The name of the reagent.  This can be any string, and will be 
            included verbatim in the reagent table.

        stock:
            The stock concentration of the reagent.  This is optional, but if 
            specified, should include a unit.

        volume:
            The volume of the reagent.  This can be specified in one of two 
            forms.  The first form is simply a value with a unit (e.g. '1 µL'), 
            in which case the reagent will have the specified volume.  The 
            second form is also a value with a unit, but prefixed by the string 
            "to" (e.g. 'to 10 µL').  In this case, the whole reaction will 
            have the specified volume, and the volume of the reagent itself 
            will be the difference between the total volume and the volumes of 
            all the other reagents.  Every reagent must have the same volume 
            unit.

        mm:
            Whether or not to include the reagent in the master mix.  '+' means 
            to include the reagent, '-' or '' means to exclude it.  If this 
            field is not included for any reagent, all reagents will be 
            included in the master mix.

Options:
    -S --step <str>
        The text introducing the reaction.  "Setup {n:# reaction/s}:" is the 
        default.  This string will be formatted with a single parameter `n`, 
        which will be an `inform.plural()` object representing the number of 
        reactions to setup.

    -s --step-kind <str>
        The kind of reaction being setup.  This value will be included in the 
        text introducing the reaction.  For example, if given "PCR", the 
        reaction might be introduced as "Setup 1 PCR reaction" or "Setup 2 PCR 
        reactions" (depending on `--num-reactions`).

        If the given value contains one or more slashes, they will be used to 
        control pluralization.  See `inform.plural()` for details.  If the 
        given value doesn't contain a slash, it will be suffixed with 
        "reaction/s".  Note that this option cannot be used with `--step`, 
        because `--step` overwrites the text introducing the reaction.

    -n --num-reactions <int>        [default: 1]
        The number of reactions to setup.

    -v --volume <expr>
        Scale the reaction to the given volume.  This volume is taken to be in 
        the same unit as all of the reagents.

    -V --volume-factor <expr>
        Multiply the volume of the reaction by the given factor.  This option 
        is applied after the '--volume' flag.

    -i --instruction <str>
        An instruction on how to setup the reaction, e.g. to keep reagents on 
        ice, to use a certain type of tube, etc.  This option can be specified 
        multiple times, and each instruction will be included in a bullet-point 
        list below the reaction table.

    -x --extra-percent <float>
        How much extra master mix to make, as a percentage of the total master 
        mix volume.  The default is 10%.

    --extra-volume <float>
        How much extra master mix to make, given as a specific volume.  This 
        volume is taken to be in the same unit as all the reagents.

    --extra-reactions <float>
        How much extra master mix to make, given as a number of reactions. 

    -X --extra-min-volume <float>
        Scale the master mix such that every reagent has at least this volume.  
        This volume is taken to be in the same unit as all the reagents.
"""

import docopt
import stepwise
from stepwise import paragraph_list, unordered_list
from inform import plural

args = docopt.docopt(__doc__)
reagents = args['<reagent;stock;volume;mm>']

cols = c = {
        'reagent': [],
        'stock_conc': [],
        'volume': [],
        'master_mix': [],
}
use_master_mix = False

for reagent in reagents:
    fields = reagent.split(';')

    if len(fields) == 3:
        reagent, stock_conc, volume = fields
        master_mix = ''
    else:
        reagent, stock_conc, volume, master_mix = fields
        use_master_mix = True

    cols['reagent'].append(reagent)
    cols['stock_conc'].append(stock_conc)
    cols['volume'].append(volume)
    cols['master_mix'].append(master_mix)

if not use_master_mix:
    del cols['master_mix']

rxn = stepwise.MasterMix.from_cols(cols)
rxn.num_reactions = int(args['--num-reactions'])

if x := args['--volume']:
    rxn.hold_ratios.volume = eval(x), rxn.volume.unit
if x := args['--volume-factor']:
    rxn.hold_ratios.volume *= eval(x)
if x := args['--extra-percent']:
    rxn.extra_percent = float(x)
if x := args['--extra-reactions']:
    rxn.extra_reactions = float(x)
if x := args['--extra-volume']:
    rxn.extra_volume = float(x), rxn.volume.unit
if x := args['--extra-min-volume']:
    rxn.extra_min_volume = float(x), rxn.volume.unit

if x := args['--step-kind']:
    kind = x if '/' in x else f'{x} reaction/s'
else:
    kind = 'reaction/s'

if x := args['--step']:
    step = x
else:
    step = f"Setup {{n:# {kind}}}:"

p = stepwise.Protocol()
p += paragraph_list(
        step.format(n=plural(rxn.num_reactions)),
        rxn,
        unordered_list(*args['--instruction']),
)
p.print()
