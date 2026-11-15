chiplet-cosim
=============

.. include:: /common.inc
.. include:: /tools/_staged_engines.inc

``chiplet-cosim`` simulates several dies together, as the system file connects
them, to show that the assembly behaves as intended before anything is built.
It reads the ``.chiplet`` document and the views each die's flow wrote
(gate-level netlists, or transistor netlists for a mixed-signal case),
generates the Verilog top that wires them, runs the system under cocotb with
Icarus Verilog (and ngspice for mixed-signal blocks), and writes one
``cosim-verdict`` record that says what passed and what was not checked.

It is for designers who want a functional check across die boundaries, and for
flows that want that check recorded beside their other results. It is a
checker, not a producer: it never writes a model, never edits the document and
never blocks the flow whose output it reads.

chiplet-cosim |chiplet-cosim-version| ships in the ADK-Tools image as the
``chiplet-cosim`` command, staged as ``/opt/adk-tools/staging/chiplet-cosim``.
It is licensed GPL-3.0-or-later; a few copied fixtures and two modules keep
Apache-2.0, and ``docs/LICENSING.md`` in the staged tree lists them.

.. warning::
   chiplet-cosim is a |current-status| at alpha maturity: its commands and
   record versions may change between versions. A verdict covers the
   simulated behaviour of the views it read and nothing else. Each record
   lists what it does not claim: timing, LVS, supply hookup, interposer
   electrical behaviour, and for mixed-signal runs device accuracy and
   corners.

From a packaging-flow run
-------------------------

To co-simulate a finished :doc:`/tools/10_packaging_flow` run, point it at the
run's folder that holds ``manifest.json`` (``runs/<stamp>/run`` in
packaging-flow's layout) and at a view store: an absolute path to a folder with
one eda-views record per die, named by the die's layout sha256.

.. code-block:: bash

    chiplet-cosim select <run> --view-store <store>
    chiplet-cosim from-run <run> --output <new folder> --view-store <store>

``select`` says whether the run's dies form a case it can simulate, without
running anything. ``from-run`` copies what it needs out of the run, checks
every copy against the run's manifest, simulates, and prints one ``VERDICT``
line; the record lands in the output folder.

From your own case description
------------------------------

To simulate from a case description of your own, lock it, plan it (which
checks everything and starts nothing), and run it:

.. code-block:: bash

    python -m chiplet_cosim.cosim lock <cosim.yaml> --document <system.chiplet>
    python -m chiplet_cosim.cosim plan <cosim.yaml> --document <system.chiplet> --work <new folder>
    python -m chiplet_cosim.cosim run <cosim.yaml> --document <system.chiplet> --work <new folder>

``chiplet-cosim --help`` lists the other commands, among them drawing the dies
as an Xschem sheet and reading an edited sheet back.

Simulators and models
---------------------

The simulators come from a Nix devshell named by ``COSIM_DEVSHELL``, a store
path that a case's lock pins: Icarus Verilog and ``vvp``, cocotb, and for
mixed-signal cases ngspice with ``d_cosim``. The image sets ``COSIM_DEVSHELL``
to ``/opt/adk-tools/cosim-devshell``, a link to that store path; none of the
devshell is on ``PATH``, and chiplet-cosim starts it itself.

The PDK models are read under ``PDK_ROOT``: an ``ihp-sg13g2`` models entry
resolves to ``$PDK_ROOT/ihp-sg13g2``. A ``gf180mcuD`` models entry reads its
root from ``COSIM_GF180_ROOT`` and from nothing else. The image sets both.

Further reference
-----------------

The staged tree's ``docs/`` folder holds the rest: ``usage.md`` for the common
paths through the commands, ``commands.md`` for every command and argument,
``reference.md`` for what each command does in detail, its exits and the
verdict record's contract, ``cosim-setup.md`` and ``cosim-readings.md`` for
mixed-signal cases, and ``DEVELOPMENT.md`` for the test suite.
