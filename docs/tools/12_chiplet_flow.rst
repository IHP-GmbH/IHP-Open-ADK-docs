chiplet-die-flow
================

.. include:: /common.inc

``chiplet-die-flow``, the die flow, builds one die of a multi-die system and
hands it over as a **ready die**: the layout, its pin list and a contract that
says what was built and how. It runs LibreLane on your die's configuration,
reads the result back, and writes the files that
:doc:`/tools/10_packaging_flow`, :doc:`/tools/11_interposer_pnr` and
:doc:`/tools/09_assembly_lvs` need to treat the die as a part.

It is for whoever designs a die that goes into an assembly. You keep authoring
your LibreLane project as usual; the die flow adds the step that turns a
finished run into something the rest of the flow can check.

Version 0.1.0 of chiplet-flow ships in the ADK-Tools image as the
``chiplet-die-flow`` command. It is licensed GPL-3.0-or-later.

.. warning::
   The die flow is part of the |current-status|. A ready die records the
   results of its build's checks; it does not qualify the die, and it is not a
   foundry sign-off.

This page covers ``build-die``, ``die-view``, ``emit-ready-die``,
``derive-padring-die`` and ``pad-frame``. ``chiplet-die-flow <command>
--help`` lists every option of a command.

The ready die
-------------

A ready die is a directory of four files that move together:

.. list-table::
    :header-rows: 1
    :widths: 28 72

    * - File
      - What it holds
    * - ``layout.gds``
      - The die layout.
    * - ``pins.json``
      - The die's pad inventory, in the form :doc:`/formats/07_pin_lists`
        describes.
    * - ``build-record.json``
      - The record of the build: the tools and the PDK revision it ran with,
        and the results of its checks.
    * - ``die-contract.json``
      - The die contract, described below.

The directory is relocatable: every path inside is relative to the contract.
A packaging-flow run admits a ready die from its contract and places it. The
two dies of ``two_die_echo_shifted_gf180`` (:doc:`/examples`) are ready dies
of this kind, one built on IHP SG13G2 and one on GF180MCU.

The die contract
----------------

The die contract, schema ``die-output-contract``, is a producer-side
description of a built die. It says which process produced the die, which pad
inventory is authoritative, what each terminal is for, and what verification
was recorded over the die's bytes. It refers to the pad inventory and the
layout by SHA-256 digest rather than by name, so a contract is about specific
bytes; pad geometry is not copied into it, it stays in ``pins.json``.

A contract is not a qualification of the die, not a fabrication approval, and
not a claim that the die is compatible with any assembly. It carries no die
LVS verdict either: that stays in the record of the run that built the die.

The die flow writes contract version 1.1. A contract is read by a strict
reader, ``chiplet_format_io`` from the reference readers of |spec-repo|,
which versions its own boundary as a reader revision. The image
stages reader revision 4, the one packaging-flow 0.1.0 requires; the die flow
accepts revisions 3 and 4. A reader the die flow cannot use stops it with
exit 11 before anything is read.

Building a die
--------------

Your die project is a LibreLane project whose configuration
(``librelane/config.yaml`` unless ``--config`` names another) selects
``meta.flow: Chiplet``. Ask first what a build would be, which starts nothing,
then build it and emit the ready die:

.. RUN-ON-IMAGE: chiplet-die-flow build-die --instance <die> --technology sg13g2 --run-dir <die_project> --plan
.. code-block:: bash

    chiplet-die-flow build-die --instance <die> --technology sg13g2 \
        --run-dir <die_project> --plan
    chiplet-die-flow build-die --instance <die> --technology sg13g2 \
        --run-dir <die_project> --out <build_dir> \
        --opening-purpose aperture --ready-out <ready_die>

``--technology`` is the one your system declares for the die, ``sg13g2`` or
``gf180mcu``. ``<build_dir>`` gets ``build.json``, the record of the build, and
``<ready_die>`` gets the four files. ``--opening-purpose`` states what the bound
pad opening layer is, a passivation ``aperture`` or a ``conductor``. ``--tier``
is ``hermetic`` (no tool started), ``smoke`` (stops after the step
``--smoke-to`` names, with no die GDS) or ``full`` (RTL to GDS, the default).
``build-die`` exits 0 once ``build.json`` is complete, whatever its checks say:
read the record, not the exit code.

Inside the image, ``build-die`` runs the LibreLane the image carries, against
its IHP SG13G2 PDK. A die configured for another PDK finds no such PDK there
and its build fails; build it where its PDK is installed, and bring the ready
die in. The image's Magic is older than the PDK's techfiles require, so a
LibreLane ``Classic`` flow fails there at its Magic stream-out. The
``Chiplet`` flow runs no Magic step.

A LibreLane run you already have becomes a ready die in two steps:

.. RUN-ON-IMAGE: PDK_ROOT=$ADK_NIX_SG13G2_PDK chiplet-die-flow die-view --config <config.yaml> --run-dir <run> -o <view.json> && PDK_ROOT=$ADK_NIX_SG13G2_PDK chiplet-die-flow emit-ready-die --view <view.json> --run-dir <run> --instance <die> --opening-purpose aperture --output <ready_die>
.. code-block:: bash

    PDK_ROOT=$ADK_NIX_SG13G2_PDK chiplet-die-flow die-view \
        --config <config.yaml> --run-dir <run> -o <view.json>
    PDK_ROOT=$ADK_NIX_SG13G2_PDK chiplet-die-flow emit-ready-die \
        --view <view.json> --run-dir <run> \
        --instance <die> --opening-purpose aperture --output <ready_die>

In the tools image, LibreLane builds against the SG13G2 PDK that
``$ADK_NIX_SG13G2_PDK`` names, not the one ``$PDK_ROOT`` names, and
``die-view`` refuses a run whose PDK differs from ``$PDK_ROOT``. Set it on each
command as shown, never with ``export``: KLayout and the assembly DRC read
``$PDK_ROOT`` too.

``die-view`` reads the run and binds the die's pads to its GDS. A run the
configuration did not build is refused. ``emit-ready-die`` writes the four
files, has the strict reader admit the contract again, and prints the digests
of what it wrote. A refusal exits 1 and leaves no directory, except a contract
the reader would not admit, which is kept as the evidence.

Dies the die flow did not build
-------------------------------

Two more commands make a ready die without building one:

- ``derive-padring-die`` takes a full chip with a pad ring made by LibreLane's
  stock Chip flow. It reads the run's final DEF, netlist and GDS, checks each
  bond pad's net against a structural netlist of the top, and writes the same
  four files. The die's DRC, antenna and LVS counts are the run's, quoted;
  nothing inside the die is checked again. A net carried by several ring pads
  is refused today.
- ``pad-frame`` writes a die of which only the size and the pads are known:
  the technology's bond pad at every pad position, the die outline and each
  pad's name. Its build record says ``pad-frame-not-a-circuit`` and holds no
  check counts, and an assembly places such a die only on a person's
  admission.

What a ready die records
------------------------

The build record carries the checks read from the LibreLane run that built the
die: the error counts of the DRC, density and antenna decks with the digest of
the layout each read, the LVS verdict as the build recorded it, and an XOR of
the die view against the layout. A check that does not hold reads ``fail``, and
one the run holds no evidence for is left out for admission to read as a gap.
The record's status is ``built-not-qualified``. The record names the PDK
revision the build resolved. None of this qualifies the die: the record is a
quote of what the build said, bound to the bytes it said it about. A die's
checkpoint in a packaging-flow run reads these records; it does not run a die
check again.

Runs belong to packaging-flow
-----------------------------

The die flow builds one die per command. Chaining dies into an assembly is
packaging-flow's job: it starts ``chiplet-die-flow build-die`` as a process
for each die a run builds. ``run``, ``resume``, ``status`` and ``verify`` here
print one line naming packaging-flow and exit 1. Output from version 0.1.0:

.. RUN-ON-IMAGE: chiplet-die-flow run; echo "exit=$?"
.. code-block:: text

    chiplet-die-flow run: runs are packaging-flow's; use packaging-flow run
    exit=1

Roots
-----

A build reads the PDK under ``PDK_ROOT`` (or ``--pdk-root``), runs LibreLane
through the launcher ``CHIPLET_FLOW_LIBRELANE_LAUNCHER`` names, with its
SHA-256 in ``CHIPLET_FLOW_LIBRELANE_LAUNCHER_SHA256`` (both or neither), and
reads layouts with the interpreter ``CHIPLET_FLOW_PADMAP_PYTHON`` names. The
image sets all of them. ``CHIPLET_FLOW_THREAD_CAP`` caps the threads a build
uses; by default the die flow leaves a share of the host's memory and cores
free.

Exit codes
----------

Codes are never renumbered, only added.

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - 0
      - Success. For ``build-die``: ``build.json`` is complete, whatever its
        checks say.
    * - 1
      - A typed refusal; also ``run``, ``resume``, ``status`` and ``verify``.
    * - 2
      - A command line the parser refuses.
    * - 3
      - ``prepare-die``: the core build failed.
    * - 6
      - The build could not be bound to one run directory.
    * - 7
      - Internal error: one line on standard error names the log with the
        traceback.
    * - 11
      - The installed reader cannot admit a die contract.
    * - 130
      - Interrupted.
