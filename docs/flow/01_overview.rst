Overview
========

.. include:: /common.inc
.. include:: /adk/tables/_rule_counts.inc

This page is the map of the whole flow. Read it once before starting, then work
through :doc:`/flow/02_die_to_kicad` onwards.

What goes in and what comes out
-------------------------------

The flow takes three kinds of input:

**Die layouts.**
   One GDSII per chiplet you intend to place. Only the external pad layer and
   the text layer that names those pads are actually consumed, so a stripped
   or black-boxed die works as well as a full one. The dies keep their own
   PDKs, and the flow never checks their internals.

**An interposer technology.**
   A KLayout technology describing the substrate the dies are mounted on:
   layer properties (``.lyp``), a technology file (``.lyt``), a layer map and
   the technology's own fabrication rule decks. |interposer-repo| is the
   reference implementation, the IHP 130 nm IntM4TM2 aluminium BEOL
   interposer.

**An interconnect technology.**
   A manifest of chiplet attachment methods (Cu pillar, solder bump, vendor
   microbump), each with its stack geometry and its pitch and spacing numbers.
   |interconnect-repo| is the reference implementation. It is a separate,
   swappable axis from the interposer: the interposer fabricates the pad
   openings, the interconnect method fills them.

It produces:

* ``<board>.chiplet``, the assembly description that names every component,
  its technology, its position in three dimensions and its attachment method.
* ``<board>_interposer.gds``, the fabrication-oriented interposer layout, and
  ``<board>_complete.gds``, the same layout with every die instance placed
  into it.
* Machine-readable sidecars: a boundary manifest and a pillar manifest next to
  each GDS the converter writes, plus an interconnect-method sidecar next to
  the complete GDS.
* DRC reports: a KLayout ``.lyrdb`` from the ADK assembly deck and a JSON
  summary from the Cu-pillar check.

.. warning::
   The kit is a |current-status|. The assembly checks described here are the
   geometric axis of assembly verification: placement, spacing, minimum area,
   attachment geometry and bump pitch. They do not reconcile the assembled
   layout against a system netlist. That connectivity axis is within the kit's
   scope but is not part of this preview release. They also do not replace the
   per-PDK fabrication DRC that each die and the interposer still need in their
   own technologies.

The flow at a glance
--------------------

.. figure:: /_figures/tikz_designflow.*
    :align: center
    :alt: Three phase panels side by side. Design in KiCad takes die GDS
          files, an interposer technology and an interconnect technology
          through gds2kicad, the KiCad ADK build and the assembly DRU
          generator to a .kicad_pcb. Export and build takes that board
          through the Chiplet Export plugin and hyp_to_gds.py to the
          interposer and complete GDS, the boundary and pillar manifests and
          the finalised .chiplet. Check, view and hand off runs run_drc.py,
          Chiplet Studio and chiplet2dbx.py over those artefacts.
    :width: 85%

    The design flow, from die layouts and an interposer technology
    through to a checked assembly. The eight stages are grouped into three
    phases, and the numbers match the stage table below.

The same pipeline, seen as the files each stage consumes and writes:

.. figure:: /_figures/tikz_artifact_pipeline.*
    :align: center
    :alt: A vertical pipeline in which die GDS files and an interposer
          technology feed gds2kicad, the KiCad ADK build and the export
          writers with hyp_to_gds.py, which then fan out to the ADK assembly
          DRC, Chiplet Studio and chiplet2dbx.
    :width: 90%

    The flow in artefact terms. Each stage names the tool that runs
    it and the files it writes.

The stages
----------

.. list-table::
    :header-rows: 1
    :widths: 4 20 22 26 28

    * - #
      - Tool
      - Input
      - Output
      - Documented in
    * - 1
      - ``gds_to_kicad.py``, ``gds_to_kicad_symbol.py``
      - Die GDS plus a layer-properties file
      - ``.kicad_mod`` footprint, ``.kicad_sym`` symbol, ``<die>.pins.json``
      - :doc:`/flow/02_die_to_kicad`, :doc:`/tools/03_gds2kicad`
    * - 2
      - KiCad ADK build (``pcbnew``)
      - Footprints, symbols, interposer technology
      - ``.kicad_pcb`` assembly board
      - :doc:`/flow/03_interposer_design`, :doc:`/tools/01_kicad_adk_mod`
    * - 3
      - ``generate_assembly_dru.py``
      - ADK rule parameters plus the selected adapters
      - ``.kicad_dru`` section checked live while you route
      - :doc:`/adk/06_kicad_dru`
    * - 4
      - Chiplet Export plugin
      - The loaded ``.kicad_pcb``
      - ``<board>.hyp`` and an intermediate ``.chiplet``
      - :doc:`/flow/04_export`, :doc:`/tools/02_chiplet_export_plugin`
    * - 5
      - ``hyp_to_gds.py`` (run by the same plugin)
      - ``<board>.hyp``, interposer ``.lyp``, interconnect manifest
      - Interposer GDS, complete GDS, manifests, finalised ``.chiplet``
      - :doc:`/flow/05_hyp_to_gds`
    * - 6
      - ``run_drc.py`` (ADK)
      - Complete GDS plus its boundary manifest
      - ``reports/<board>_assembly_drc.lyrdb``
      - :doc:`/adk/05_run_drc`, :doc:`/flow/06_verification_stages`
    * - 7
      - Chiplet Studio
      - ``<board>.chiplet`` and the GDS files it references
      - Interactive 3D and 2D inspection
      - :doc:`/flow/07_view_and_inspect`, :doc:`/tools/04_chiplet_studio`
    * - 8
      - ``chiplet2dbx.py``
      - ``<board>.chiplet``
      - A 3Dblox model for OpenROAD
      - :doc:`/adk/07_chiplet2dbx`, :doc:`/formats/08_3dblox_interop`

Stages 4 and 5 are one action in practice. The export dialog writes the
HyperLynx file and the intermediate ``.chiplet``, then invokes
``hyp_to_gds.py`` as a worker subprocess, and stage 6 runs immediately
afterwards over the complete GDS when that output is enabled. They are listed
separately because they consume and produce different artefacts, and because
``hyp_to_gds.py`` also runs standalone.

The pivot artefact: ``.chiplet``
--------------------------------

The ``.chiplet`` file is the one artefact every tool reads, and it is what makes
the pipeline a pipeline rather than a chain of one-off converters. It is YAML,
human-readable and diffable, and carries four groups of information:

``assembly`` and ``interposer``
    The design name, the working units, and the interposer adapter the
    assembly DRC should use.

``technologies``
    Each technology the assembly touches, with the path to its layer
    properties file and its database unit. Paths may be written with
    ``${VAR}`` references, for example
    ``${INTERPOSER_PDK_ROOT}/libs.tech/klayout/tech/intm4tm2.lyp``, which
    readers expand through the shared discovery chain.

``connection_stacks`` and ``interconnect``
    The attachment methods in play, each expanded to its physical layer stack
    (material, height and diameter per layer). The values are copied from the
    interconnect PDK manifest, so a ``.chiplet`` stays readable even where that
    PDK is not installed.

``components``
    One entry per interposer and per die: technology, layout path, top cell,
    outer dimensions including thickness, position in x, y and z, rotation, and
    for a die its ``connection`` method and its ``orientation``. The interposer
    entry also carries the extracted ``io_pads``.

A die's ``position.z`` is not a free parameter. It is the attachment surface
plus the height of the selected connection stack, and the 3Dblox exporter
refuses assemblies where the two disagree.

The file passes through two states: the KiCad writers emit an intermediate
version carrying a ``_metadata.finalize_required: true`` marker, and
``hyp_to_gds.py`` rewrites it in place once the interposer GDS exists, anchoring
positions to the canonical frame and stripping the marker. Readers refuse a file
that still carries it, so a half-finished export cannot be mistaken for a
finished one.

:doc:`/formats/01_chiplet` and :doc:`/formats/02_chiplet_components` are the
field-by-field reference, and :doc:`/formats/03_coordinate_frames` explains the
frame the finalised file uses.

The shared layer source of truth: ``.lyp``
------------------------------------------

The other thing that holds the flow together is far more mundane: everybody
reads the same KLayout layer-properties files.

* gds2kicad reads a ``.lyp`` to turn ``TopMetal2.drawing`` into GDS layer
  ``134/0`` when it extracts pads, and records which file it used.
* The KiCad board resolves the interposer ``.lyp`` through the
  ``INTERPOSER_LYP`` text variable.
* ``hyp_to_gds.py`` reads the same interposer ``.lyp`` to map board copper
  layers onto interposer metals by name.
* Chiplet Studio reads every ``.lyp`` named in the ``.chiplet``
  ``technologies`` section to colour and stack the layers it renders.

Nothing in the flow hardcodes a layer number for a technology it does not own;
updating a ``.lyp`` is what propagates a layer change. That is also why the ``.chiplet`` records a path to
the layer file rather than a copy of its contents: a stale embedded copy would
be undetectable, a stale path is not.

The one deliberate exception is the chiplet-internal pad vocabulary that the
black-box generator emits (``205/0`` for pad metal, ``205/25`` for pad text,
``206/0`` for the outline). That is a canonical ADK-side registry for dies that
ship no layer file at all, and it is described in :doc:`/adk/09_registries`.

What the assembly checks actually check
---------------------------------------

The rule decks are technology-agnostic: the interposer adapter says *where* on
the substrate attachment may land, and the interconnect adapter says *how
densely* bumps of a given method may be placed there.

That gives |asm-rule-count| assembly rules and |ixn-rule-count| interconnect
rules over the assembled GDS, plus a design-time subset mirrored into KiCad as
a ``.kicad_dru``. :doc:`/adk/01_architecture` explains the split,
:doc:`/adk/03_asm_rules` and :doc:`/adk/04_ixn_rules` list the rules, and
:doc:`/flow/06_verification_stages` explains which check runs when and what
each one cannot see.

Project layout
--------------

The flow expects a design to be laid out with a clean split between authored
source and generated products:

.. code-block:: text

    my_design/
      kicad/       KiCad source you author: .kicad_pro, .kicad_sch, .kicad_pcb,
                   the project .pretty library, .kicad_sym, fp-lib-table
      chiplets/    die GDS inputs and their pin lists
      outputs/     export products: <board>.chiplet + MANIFEST.md at the root,
                   GDS layouts and sidecars under layout/,
                   DRC reports under reports/

``adk-new-project <name>`` scaffolds exactly this, together with a
``.gitignore`` that tracks the light deliverables and ignores the heavy
regenerable ones. The reference design ships in the same shape, so anything
that works there works in a scaffolded project without rewiring.

Where to go next
----------------

.. tip::
    If you want to see the whole flow work before running any of it yourself,
    open the reference design described in :doc:`/flow/08_reference_design`. It
    is a two-die assembly on the IntM4TM2 interposer, regenerated and
    DRC-gated on every build of the tools image, so its outputs are known good.

* No toolchain yet: :doc:`/install/01_container`.
* Toolchain installed, starting from your own dies:
  :doc:`/flow/02_die_to_kicad`.
* Unfamiliar with the vocabulary: :doc:`/intro/04_glossary`.
* Adding a new interposer or a new bumping vendor:
  :doc:`/adk/02_adapter_contract`.
