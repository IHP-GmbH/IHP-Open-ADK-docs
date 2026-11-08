Examples
========

.. include:: /common.inc

The worked examples are a repository of their own, adk-examples. Each example
is a folder: a ``system.chiplet`` that describes the assembly, the dies and the
registry copy it reads under ``inputs/``, and its pages. Its first block copies
it into your work directory, and you run it in the container, either block by block from its
``README.md`` or as tasks from VS Code with its ``AUTOMATION.md``. Every
example in a checkout runs in the one image its ``release-lock.json`` names;
:doc:`/install/00_release` gets you that image, which carries every tool a run
needs.

Each README opens with a table that says what the example claims before you
run it: the command, what holds when it passes, how long it takes, and what it
does not claim. When a run disagrees with what a block expects, the block
prints STOP, and you go no further.

.. note::
    The examples are alpha. A page marked Draft has not yet been read against
    a run of this release by hand, and the dies are built but not qualified.
    A verdict covers only the checks that ran. No assembly here has been
    fabricated, and no verdict is a sign-off for fabrication. Run times were
    measured on one computer and are a guide only.

The examples in this release
----------------------------

.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Folder
      - What it shows
    * - ``two_die_echo_shifted_gf180``
      - Two ready dies on one IntM4TM2 carrier, in two technologies: a DRIVER
        on IHP SG13G2 with a level shifter on every lane, and an ECHO on
        GF180MCU at 3.3 V. One run admits the dies from their contracts,
        places them, routes the carrier, writes the GDS, and runs the DRC
        decks, the terminal map, the assembly LVS, the seal-ring presence
        rules and the density deck. It halts for your signature at four
        checkpoints in turn (the dies, the interposer, the assembly and the
        external interface), then writes the verdict and verifies it.
        Co-simulation of the two dies comes in a later release.
    * - ``driver_from_rtl_echo_gf180``
      - The same link with the DRIVER built from its RTL in the run, on IHP
        SG13G2, beside the same ECHO. Draft.

Pages in each folder:

- ``README.md``: the run from the container shell, block by block, each block
  also shipped as a script under ``scripts/``.
- ``AUTOMATION.md``: the same run from VS Code, one task per step, signed from
  the form the run's map opens.
- ``INSPECTION.md``: a signed run, opened and followed net by net through the
  schematic, the system and assembly files, the board and the interposer GDS.

The pages of the three-day workshop built on these examples are in the
``workshop/`` folder of adk-examples, starting at its ``README.md``. They are a
draft until the release the workshop uses.
