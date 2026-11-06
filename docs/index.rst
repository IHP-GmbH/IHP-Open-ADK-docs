************************************
IHP Open Assembly Design Kit (ADK)
************************************

.. include:: /common.inc

.. toctree::
    :hidden:

    quickstart
    intro
    install
    examples
    flow
    adk
    formats
    tools
    roadmap
    contrib
    references

Current Status: |current-status|
================================

.. warning::
   The IHP Open ADK is a **preview release**. The interposer process has been
   fabricated several times at IHP, which is a statement about process maturity,
   not about a complete assembly. The kit is not intended for production
   assembly design at this moment.

.. warning::
   This documentation is a work in progress. Pages describing future domains
   state directions, not shipped features.

What the ADK is
===============

The Assembly Design Kit sits one abstraction layer above all PDKs. It owns the
rules and tooling that govern *how chiplets are placed and connected* on an
interposer. The interposer and the chiplet dies remain ordinary PDKs, each
owning its own fabrication rules.

Keeping the PDK's question and the ADK's question apart is what lets one assembly
rule deck check assemblies built on any interposer.
:doc:`intro/01_what_is_the_adk` draws the distinction in full.

Assembly-level verification is therefore a layer of its own, above the signoff
each die and each interposer already runs in its own PDK, and it has two axes
that do not subsume each other. This preview release ships both: the geometric
axis, assembly DRC, as the ADK rule decks, and the connectivity axis, assembly
LVS, as the ``assembly-lvs`` engine in the ADK-Tools image.
:doc:`intro/01_what_is_the_adk` sets out both, and
:doc:`tools/09_assembly_lvs` states what the connectivity check does not
cover.

.. figure:: _figures/fig_what_is_adk.*
    :align: center
    :alt: The ADK as a meta layer above the chiplet, interposer and interconnect PDKs, with the two axes of assembly verification that this release ships, the geometric assembly-DRC axis and the connectivity assembly-LVS axis.
    :width: 90%

    One assembly rule set above many PDKs. The chiplet PDKs, the interposer PDK
    and the interconnect PDK each own their own fabrication rules; the ADK owns
    only what happens between them, and reaches each one through an adapter.

Where to start
==============

.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - If you want to
      - Read
    * - Get running in four steps
      - :doc:`quickstart`
    * - Understand the problem and the approach
      - :doc:`intro/01_what_is_the_adk` and :doc:`intro/02_the_gap`
    * - Get a working toolchain
      - :doc:`install/01_container`
    * - Run the examples of the alpha release
      - :doc:`install/00_release`, then :doc:`examples`
    * - Follow the flow end to end
      - :doc:`flow/01_overview`, then :doc:`flow/08_reference_design`
    * - Check an assembly
      - :doc:`adk/05_run_drc`
    * - Check an assembly's connectivity
      - :doc:`tools/09_assembly_lvs`
    * - Support a new interposer or bumping vendor
      - :doc:`adk/02_adapter_contract`
    * - Read or write the interchange files
      - :doc:`formats/01_chiplet` and :doc:`formats/02_chiplet_components`
    * - Look up a term
      - :doc:`intro/04_glossary`

The ecosystem in one line
=========================

Die GDS becomes KiCad symbols and footprints, the interposer is authored in a
nanometre-capable KiCad fork, the board is exported as a ``.chiplet`` assembly
plus a HyperLynx netlist, the netlist becomes a fabrication-ready GDS, the
assembly is checked by the ADK rule decks, and the result is inspected in 3D.
In a packaging-flow run, assembly LVS also checks the placed assembly's
connectivity against its declared nets.
:doc:`intro/03_ecosystem` names every repository and what it owns.

Scope of this documentation
===========================

This site documents the published preview: the ADK itself, the tools bundled in
the ADK-Tools image, the interchange formats, and the reference design. Work in
progress that is not part of the release is stated as a direction with no
interface commitment, and :doc:`roadmap` collects it.

Other open work is active in the same space and is complementary rather than
competing. :doc:`intro/02_the_gap` sets out where the ADK fits alongside it.

License
=======

The ADK, the interposer PDK, the interconnect PDK and the chiplet format
specification are Apache-2.0. The KiCad fork, the KiCad plugin, gds2kicad,
Chiplet Studio and the ADK-Tools glue are GPL, and assembly-lvs is
GPL-3.0-or-later. :doc:`intro/03_ecosystem` carries the per-repository
breakdown, and the ADK-Tools image ships a ``NOTICE.md`` with the per-component
licence breakdown and the corresponding-source obligation.
