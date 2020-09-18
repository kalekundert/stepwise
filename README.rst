********
Stepwise
********

Stepwise is a program for crafting scientific protocols.  Its central idea is 
that it should be easy to create large, complex, single-use protocols by 
piecing together any number of smaller, simpler, multi-use protocols.  This 
modular approach has several benefits:

1. It's *intuitive*.  Although it's good for protocols to contain a 
   fine-grained level of detail (e.g. add 5 µL of solution A, then incubate at 
   37°C for 15 min), it's more natural to think about protocols at a higher 
   level (e.g. do PCR, then run a gel).  

2. It's *concise*.  Having to repeatedly write down similar details for similar 
   experiments is tedious and prone to ambiguities or inconsistencies.  Being 
   able to easily reuse protocols eliminates this redundancy without 
   sacrificing any detail.
   
3. It's *reproducible*.  By lowering the barrier to record every relevant 
   detail for every protocol, it's more likely that others (your future self 
   included) will be able to reproduce your experiments.

More concretely, stepwise is a command-line tool.  Protocols are either text 
files or scripts that produce text output.  Most protocols start off as simple 
text files, and grow into scripts when they're used enough to benefit from the 
extra complexity (e.g. by having optional steps, pre-calculated reagent 
volumes, etc).  Protocols can be combined using Unix pipes, which turns out to 
be a very powerful and flexible approach.  For example, a pipeline can be saved 
as a shell script and subsequently used as a standalone protocol, even in other 
pipelines.  For more information on writing and using protocols, refer to the 
`documentation <https://stepwise.rtfd.io/>`__.

Since protocols are just text files, they can be easily shared using standard 
tools like ``git``.  Below are links to some curated collections of 
commonly-used protocols.  If you are new to stepwise, these collections make it 
easy to get started quickly and productively:

- `Stepwise—Molecular Biology <https://github.com/kalekundert/stepwise_mol_bio>`__
- `PhosphateDB <https://github.com/kalekundert/phosphatedb>`__

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

