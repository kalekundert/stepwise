********
Stepwise
********

.. image:: https://img.shields.io/pypi/v/stepwise.svg
   :target: https://pypi.python.org/pypi/stepwise

.. image:: https://img.shields.io/pypi/pyversions/stepwise.svg
   :target: https://pypi.python.org/pypi/stepwise

.. image:: https://img.shields.io/readthedocs/stepwise.svg
   :target: https://stepwise.readthedocs.io/en/latest/?badge=latest

.. image:: https://img.shields.io/github/workflow/status/kalekundert/stepwise/Test%20and%20release/master
   :target: https://github.com/kalekundert/stepwise/actions

.. image:: https://img.shields.io/coveralls/kalekundert/stepwise.svg
   :target: https://coveralls.io/github/kalekundert/stepwise?branch=master

Stepwise is a program for authoring, planning, executing, and sharing 
scientific protocols.  There are two main benefits it seeks to provide:

1. Automate tedious calculations/remembering small details.  For example, 
   calculating how to setup master mixes, remembering which antibiotics to use 
   with which plasmids, adding fragments to a DNA assembly reaction in the 
   ideal molar ratios, choosing annealing temperatures and extension times for 
   PCR reactions, etc.  Stepwise can automatically work out all of these 
   details and many more like them.

2. Record every step of every experiment.  We all know that we should keep 
   careful notes of everything we do in lab, but having to repeatedly write 
   down similar details for similar experiments is tedious and prone to 
   ambiguities or inconsistencies.  Stepwise helps by filling in all the little 
   details after you specify the few important ones.

**Warning: this software is still very much a work in progress!**

If stepwise seems like it might be useful to you, I'd encourage you to give it 
a try!  I use it every day, and it's certainly functional.  However, it's not 
yet finished, and it's certainly not yet polished.  Let me know (preferably by 
opening an issue in the `bug tracker`_) if you have a hard time understanding 
how anything is supposed to work, or if you encounter a cryptic error message, 
or anything like that.  I ultimately want to make this into a broadly useful 
tool for as many scientists as possible, and getting feedback from other people 
will really help with that.

Example
=======
An example makes the benefits mentioned above more clear.  Here's the command 
for a protocol to construct two plasmids, named "p216" and "p217"::

  $ sw make p216 p217

This protocol needs to know what these plasmids are, and you would provide that 
information via an Excel spreadsheet or similar; see FreezerBox_ for more info.  
Below are some of the relevant entries from this spreadsheet:

Plasmids and fragments:

====  =====  ====================================  ==================================
Name  Ready  Synthesis                             Cleanup
====  =====  ====================================  ==================================
p216      n  gibson f169,f172                      transform; sequence o266; miniprep
p217      n  gibson f169,f173                      transform; sequence o266; miniprep
f169      n  pcr template=p186 primers=o359,sr71   spin-cleanup
f172      y  order vendor=IDT
f173      y  order vendor=IDT
====  =====  ====================================  ==================================

Oligos:

====  ====================
Name  Sequence
====  ====================
o359  CAACATTTCCGTGTCGCCCT
sr71  CCGGTTGTACCTATCGAGTG
====  ====================

Briefly, these tables describe how to make each construct.  For example, p216 
is made by doing a Gibson assembly with fragments f169 and f172.  In turn, f169 
is made by doing PCR with p186 as a template and o359 and sr71 as primers.  

From just the names of the constructs to make, the information in these 
spreadsheets, and sequence information read from SnapGene or GenBank files, 
stepwise produces the following protocol::

  $ sw make p216 p217
   1. Prepare 10x primer mix [1]:
  
      Reagent   Stock    Volume
      ─────────────────────────
      water             9.00 µL
      o359     100 µM   0.50 µL
      sr71     100 µM   0.50 µL
      ─────────────────────────
                       10.00 µL
  
   2. Setup 1 PCR reaction [2,3]:
  
      Reagent           Stock    Volume
      ─────────────────────────────────
      water                    15.00 µL
      p186           20 pg/µL   5.00 µL
      primer mix          10x   5.00 µL
      Q5 master mix        2x  25.00 µL
      ─────────────────────────────────
                               50.00 µL
  
   3. Run the following thermocycler protocol:
  
      - 98°C for 30s
      - Repeat 35x:
        - 98°C for 10s
        - 63°C for 20s
        - 72°C for 4 min
      - 72°C for 2 min
      - 4°C hold
  
   4. Label the product: f169
  
   5. Purify using QIAquick PCR purification kit
      (28104) [4,5]:
  
      - Perform all spin steps at 17900g.
      - Add 5 volumes PB to the crude DNA.
      - If not yellow: Add 0.2 volumes 3M sodium
        acetate, pH=5.0.
      - Load on a QIAquick column.
      - Spin 30s; discard flow-through.
  
      - Add 750 µL PE.
      - Spin 30s; discard flow-through.
      - Spin 1m; discard flow-through.
      - Add 50 µL EB.
      - Wait at least 1m.
      - Spin 30s; keep flow-through.
  
   6. Setup 2 Gibson assemblies [6]:
  
      Reagent               Stock   Volume     2.2x
      ─────────────────────────────────────────────
      Gibson master mix        2x  2.50 µL  5.50 µL
      f169               65 ng/uL  1.60 µL  3.51 µL
      f172,f173          10 ng/µL  0.90 µL
      ─────────────────────────────────────────────
                                   5.00 µL  4.10 µL/rxn
  
   7. Incubate at 50°C for 15 min.
  
   8. Label the products: p216, p217
  
   9. Transform the following plasmids: p216, p217 [7]
  
      - Pre-warm 2 LB+Carb plates.
      - For each transformation:
  
        - Thaw 25 µL competent MACH1 cells on ice.
        - Add 1 µL plasmid.
        - Gently flick to mix.
  
        - Plate 25 µL cells.
        - Incubate at 37°C for 16h.
  
  10. Sequence the following plasmids:
  
      Plasmid  Primers
      ────────────────
      p216     o266
      p217     o266
  
  11. Miniprep.
  
  Notes:
  [1] For resuspending lyophilized primers:
      100 µM = 10 µL/nmol
  
  [2] https://tinyurl.com/y27ralt4
  
  [3] For diluting template DNA to 20 pg/µL:
      Dilute 1 µL twice into 7*sqrt([DNA]) µL
  
  [4] https://tinyurl.com/xr8ruvr9
  
  [5] Column capacity: 10 µg
  
  [6] https://tinyurl.com/ychbvkra
  
  [7] https://tinyurl.com/2cesd2hv

Note that we only had to specify the really meaningful details, like which 
constructs to make, which templates/primers to use for PCR, etc.  Stepwise 
figured out everything else automatically, including:

- Realizing that f169 needs to be made before p216 or p217.

- Realizing that f172 and f173 *don't* need to be made, because they are marked 
  as "ready".

- Choosing all of the PCR parameters, including volumes for every reagent and a 
  temperatures/times for every thermocycler step.  Q5 polymerase is used in 
  this example because that is what I order, but it easy to configure other 
  vendors/mixes.  The annealing temperature and extension times are based on 
  the sequences of the template and the primers.

- Realizing that both assemblies share the f169 fragment, and so it can be 
  included in a master mix.

- Estimating the concentration of the f169 fragment based on the typical yield 
  from a PCR reaction and the typical recovery from a silica spin column.

- Choosing all of the Gibson assembly parameters, most notably fragment volumes 
  that give the recommended molar ratio of backbone to insert.
  
- Which antibiotics to use when transforming the plasmids.  This comes from 
  searching the sequence of the plasmids for known antibiotic resistance genes.

Installation
============
Install stepwise from ``pip``::

  $ pip install stepwise

You may also want to install some related packages.  First is `Stepwise — 
Molecular Biology <swmb>`_, which is a collection of pre-programmed protocols 
relating to molecular biology, e.g. PCR, Gibson/Golden Gate assembly, in vitro 
transcription, etc.::

  $ pip install stepwise_mol_bio

Second is FreezerBox_, which allows you to record useful information about your 
DNA/protein constructs (e.g. sequence, molecular weight, cloning strategy, 
etc.) in a way that is accessible to stepwise::

  $ pip install freezerbox

Getting started
===============
Stepwise aims to be something you can use for every single protocol you 
perform.  However, that's a big commitment.  It's easier to get started by just 
using stepwise for a few tasks that it really excels at:

- ``sw make``: See the example above.  This command is great for routine 
  cloning.  The basic workflow is to record your cloning steps in a spreadsheet 
  as you plan them, then to have stepwise generate a protocol once all of your 
  primers etc. have arrived.  Requires `FreezerBox`_.

- ``sw future/reactions``: This command calculates the best way to use master 
  mixes to setup groups of related reactions.  It really shows its worth in 
  complex situations that call for 3-4 master mixes.  It knows how to make a 
  little bit extra of each mix, and can account for all sorts of complicated 
  reaction setups.

Quick hint: There isn't yet any online documentation for stepwise, but each 
command has pretty extensive usage information if you use the ``-h`` flag.  For 
example::

  $ sw future/reactions -h

.. _`bug tracker`: https://github.com/kalekundert/stepwise/issues
.. _FreezerBox: https://github.com/kalekundert/freezerbox
.. _swmb: https://github.com/kalekundert/stepwise_mol_bio
