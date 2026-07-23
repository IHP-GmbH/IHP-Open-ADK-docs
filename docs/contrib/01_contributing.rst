Contributing to the ADK
=======================

.. include:: /common.inc

The ecosystem is spread across several repositories, and the first question is
usually which one a change belongs in. :doc:`/intro/03_ecosystem` has the
ownership table; the short version is that each repository owns exactly one
contract.

Where a change belongs
----------------------

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - If you want to
      - Change
    * - Support a new interposer substrate
      - Add one adapter file to |adk-repo|. Do not modify the rules.
    * - Support a new bumping vendor or method
      - Add an interconnect adapter to |adk-repo|, and the method parameters to
        |interconnect-repo|.
    * - Change what a rule checks
      - |adk-repo|, and update both the KLayout deck and the KiCad DRU
        generator so the two toolchains stay in agreement.
    * - Change a field in the assembly file
      - |spec-repo| first, since it owns the format, then the readers.
    * - Fix a converter, the layout tool or the viewer
      - The relevant tool repository. |tools-repo| only pins revisions.
    * - Pin a new revision of a tool
      - |tools-repo|.

Adding an adapter
-----------------

This is the most common contribution and it is deliberately small. An adapter
declares the abstract inputs the rules need, in terms of one PDK's layers, and
nothing else. It declares no rules, does not touch the chiplet boundary, and
imports no other file.

:doc:`/adk/02_adapter_contract` is the normative specification and includes a
worked example of the shipped IntM4TM2 adapter.

Rules and their two consumers
-----------------------------

The parameter registries in ``config/`` are shared between the KLayout deck and
the KiCad DRU generator, so that the design-time check and the layout check
agree on what they are checking. A change to a rule value belongs in the
registry, not in either consumer.

Not every rule can be mirrored into KiCad. :doc:`/adk/06_kicad_dru` has the
coverage matrix, and a change that widens or narrows that coverage should update
it.

Tests
-----

The ADK test suite is deliberately interposer-agnostic and PDK-free. DRC tests
use a synthetic adapter that declares its attachment region on an arbitrary
layer, and every GDS fixture is synthesised at test time together with its
boundary manifest sidecar. Nothing depends on a committed binary layout or on a
PDK installation.

Run it from the ADK checkout:

.. code-block:: bash

    pytest tests/

Modules that shell out to KLayout skip cleanly when the ``klayout`` command is
not on ``PATH``, so a bare checkout still exercises the pure-Python parts. A
contribution that adds a rule should add a fixture that triggers it and one that
does not.

Two invariants the suite enforces are worth knowing about before you change
anything structural. The ``VERSION`` file and the ``version`` keys in every
``config/*.json`` must agree with the latest released changelog entry. And a run
with no interconnect adapter must produce output identical to the interposer
only path, which is what makes the interconnect axis safe to add to an existing
design.

The container as the integration gate
-------------------------------------

|tools-repo| pins one exact, verified combination of every tool per commit, and
its verify stage decides whether an image is tagged. To try a branch of one tool
against the rest of the pinned stack, check it out in the corresponding submodule
and rebuild. See :doc:`/tools/07_adk_tools_image`.

Commit conventions
------------------

English, concise, imperative mood, matching the existing history. One logical
change per commit. Keep each tool revision bump in its own commit so that a
regression bisects cleanly.
