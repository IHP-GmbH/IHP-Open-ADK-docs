The ecosystem
=============

.. include:: /common.inc

The IHP Open ADK is one repository in a set that together forms a flow for 2.5D
heterogeneous integration. This page names each repository, says what it
owns, and shows how they fit together. The rule of thumb is that each repository
owns exactly one contract, and nothing owns two.

The repositories
----------------

.. list-table::
    :header-rows: 1
    :widths: 26 16 58

    * - Repository
      - License
      - Owns
    * - |adk-repo|
      - Apache-2.0
      - The assembly rules, the adapter contract, the DRU generator, the 3Dblox
        exporter and the manifest-level checks. This site's primary subject.
    * - |spec-repo|
      - Apache-2.0
      - The ``.chiplet`` format specification, the coordinate-frame contract,
        the JSON Schemas and the reference readers.
    * - |interposer-repo|
      - Apache-2.0
      - The IntM4TM2 interposer technology: layers, KLayout technology, its own
        fabrication DRC, and the Cu-pillar structures.
    * - |interconnect-repo|
      - Apache-2.0
      - The attachment method registry: Cu pillars, solder bumps, microbumps,
        with their parameters and 3D bodies.
    * - |kicad-repo|
      - GPL-3.0-or-later
      - The KiCad fork hardened for sub-micrometre layout and carrying the
        semiconductor exports.
    * - |plugin-repo|
      - GPL-3.0-or-later
      - The pcbnew export plugin, the flow orchestrator, and the HyperLynx to
        GDS converter.
    * - |gds2kicad-repo|
      - GPL-3.0-or-later
      - Conversion of die GDS into KiCad footprints, symbols and pin lists.
    * - |studio-repo|
      - GPL-3.0-or-later
      - The 3D assembly viewer and ``.chiplet`` editor.
    * - packaging-flow
      - GPL-3.0-or-later
      - The flow run: from one ``system.chiplet`` through die admission,
        placement, routing, GDS, DRC and assembly LVS to a verdict, with a
        signature at each checkpoint. See :doc:`/tools/10_packaging_flow`.
    * - interposer-pnr
      - GPL-3.0-or-later; descriptors taken from Apache-2.0 PDKs keep that
        license
      - Placement, bumps and interposer routing as a draft KiCad board, a
        proof of concept, and the routing-technology descriptor contract. See
        :doc:`/tools/11_interposer_pnr`.
    * - chiplet-flow
      - GPL-3.0-or-later
      - One die build with LibreLane, handed over as a ready die with its die
        contract, through the ``chiplet-die-flow`` command. See
        :doc:`/tools/12_chiplet_flow`.
    * - assembly-lvs
      - GPL-3.0-or-later
      - Connectivity of a placed assembly against its declared nets. See
        :doc:`/tools/09_assembly_lvs`.
    * - |tools-repo|
      - GPL-3.0-or-later
      - The container that pins and builds the tools above, plus the
        reference design. It also stages the reference reader of the
        ``.chiplet`` specification that the flow tools read with.

The base process PDK, |pdk-repo|, sits underneath all of this and is documented
separately at https://ihp-open-pdk-docs.readthedocs.io.

.. note::
   The pinned revision of each repository, as documented by this site, is in the
   version matrix on :doc:`/tools/07_adk_tools_image`. That table is generated
   from the submodules this documentation is built against, so it always
   describes the code these pages actually describe.

How they connect
----------------

.. figure:: /_figures/tikz_ecosystem.*
    :align: center
    :alt: The tools of the ecosystem arranged around the assembly flow.
    :width: 80%

    The design tools of the ecosystem around the KiCad path. The flow tools
    in the table above are not drawn.

The same set in data-flow terms, following the files rather than the tools:

.. figure:: /_figures/tikz_ecosystem_dataflow.*
    :align: center
    :alt: Data-flow graph running from the base PDK and the chiplet GDS files, through the interposer PDK and gds2kicad, into the KiCad ADK fork, and on to hyp_to_gds, the ADK assembly DRC and Chiplet Studio, with the .chiplet export finalised by hyp_to_gds, giving the assembly DRC its adapter flags and read by Chiplet Studio.
    :width: 90%

    The ecosystem in data-flow terms. Each repository owns one contract
    and hands one artefact to the next.

Two artefacts hold this together.

The ``.chiplet`` file is the **pivot format**. It records where every component
sits in one shared frame, how each die is mounted in z, its orientation, and
which artwork it refers to. Every tool downstream of layout writes it, reads
it or takes its flags from it, and it remains the authoritative placement source even when a derived view, such as a
3Dblox assembly, is exported from it.

The ``.lyp`` layer property files are the **shared layer source of truth**. The
interposer PDK owns them, and the converter, the layout tool and the viewer all
read the same files rather than each carrying its own layer table.

Who owns which rules
--------------------

.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Rule kind
      - Owner
    * - Can this metal shape be fabricated on this process
      - The relevant PDK. The ADK never touches these.
    * - Can these vias and pads be built on the interposer
      - The interposer PDK.
    * - Is this bump pitch achievable by this attachment method
      - The interconnect PDK provides the numbers, the ADK's IXN axis applies
        them to the assembly.
    * - May this die sit here, at this spacing
      - The ADK's ASM axis.
    * - Do the pads of this die land on the pillars actually drawn
      - The ADK's manifest-level check.

Finding your dependencies
-------------------------

Every tool locates the others through one shared discovery chain rather than
fixed relative paths, and the container sets the roots for you.
:doc:`/install/03_environment` has the full table.

Licensing in practice
---------------------

The ADK, the format specification and both PDKs are Apache-2.0, so a rule deck,
an adapter or a reader can be reused with minimal obligation. The tools built on
KiCad and KLayout are GPL, as their upstreams require, and so are the flow
tools (packaging-flow, interposer-pnr, chiplet-flow and assembly-lvs).

The container image is a mere aggregation of independently licensed components.
Each keeps its own license, and ``NOTICE.md`` in the ADK-Tools repository
carries the per-component breakdown together with the corresponding-source
obligation that applies if you redistribute the image.
