Glossary
========

.. include:: /common.inc

The same physical thing is called different names in different parts of a
heterogeneous integration flow, and several terms that sound interchangeable are
not. This page fixes the vocabulary used across this site.

Assembly concepts
-----------------

.. glossary::

    chiplet
        A die designed to be integrated with other dies in a package rather than
        packaged alone. In this flow a chiplet enters as a GDS layout plus a pin
        list, and is treated as a black box: only its outline, its pads and its
        thickness matter to the assembly.

    die
        Used interchangeably with :term:`chiplet` when referring to a physical
        instance placed on the interposer. Where the distinction matters,
        *chiplet* is the design and *die* is the placed instance.

    interposer
        The carrier substrate that chiplets are mounted on, whose purpose is to
        route between them and out to the package. In this flow the interposer
        is designed as a layout in its own right, against its own PDK, and it
        is the component every other position is measured against.

    assembly
        The complete arrangement: one interposer, the dies placed on it, and the
        attachment structures joining them. The unit that the ADK checks.

    2.5D integration
        Dies placed side by side on a shared interposer, as opposed to 3D
        integration where dies are stacked vertically. Every assembly this
        release supports is 2.5D and single tier.

    tier
        A level of dies at the same mounting height. The current data model has
        no z field on chiplet boundaries, so all dies are on one tier. See
        :doc:`/adk/01_architecture` for what that implies.

    heterogeneous integration
        Combining dies from different processes, nodes or vendors into one
        assembly.

Kits and rules
--------------

.. glossary::

    ADK
        Assembly Design Kit. The rules and tooling governing how chiplets are
        placed and connected on an interposer. Sits above every PDK: each die
        and the interposer are signed off against their own process kits, and
        the ADK is the verification layer for the assembly they form together.

    PDK
        Process Design Kit. The rules and models for manufacturing on one
        process. Owns fabrication rules; owns no assembly rules.

    interposer PDK
        The PDK of the interposer substrate. From the ADK's point of view it is
        an ordinary PDK, distinguished only by being the thing dies are mounted
        onto. See :doc:`/tools/05_openintm4tm2`.

    interconnect PDK
        The registry of attachment methods and their parameters, deliberately
        separate from the interposer PDK so the bumping method can come from a
        different vendor than the substrate. See :doc:`/tools/06_interconnect_pdk`.

    adapter
        A small file that maps the ADK's abstract inputs onto one PDK's concrete
        layers, or supplies one attachment method's parameters. The only place a
        PDK-specific layer number may appear in a rule run. See
        :doc:`/adk/02_adapter_contract`.

    abstract input
        A name a rule refers to without knowing what layer implements it, such
        as ``chiplet_attachment_input``. Adapters bind these to real layers.

    rule axis
        One of the two independent groups of assembly checks. The placement axis
        (``ASM.*``) and the interconnect axis (``IXN.*``) are selected by
        separate adapters and neither depends on the other. Both are geometric,
        so both sit inside :term:`assembly DRC`.

    assembly-level verification
        The checking layer whose unit is the whole assembly, above the signoff
        that each die and the interposer run in their own PDKs. It has two
        axes: a geometric one, :term:`assembly DRC`, and a connectivity one,
        :term:`assembly LVS`. Neither subsumes the other, since legal geometry
        can implement the wrong netlist and correct connectivity can be drawn
        illegally. This preview release ships the geometric axis only.

    assembly DRC
        Design rule checking at the assembly level: relationships between dies
        and the substrate, rather than manufacturability of shapes. Distinct
        from the fabrication DRC each PDK ships. It is the geometric axis of
        :term:`assembly-level verification`, and the axis this preview release
        ships.

    assembly LVS
        The connectivity axis of :term:`assembly-level verification`:
        reconciling the connectivity a system netlist declares between die pins
        against the connectivity the placed assembly realises, where a
        connection is a pad landing on the interconnect beneath it plus the
        interposer routing between those landings. Distinct from per-die LVS,
        which compares one die against its own schematic, and from interposer
        LVS, which asks whether the interposer routing connects its pads as
        drawn. A device-graph comparator does not reach this level; see
        :doc:`/intro/01_what_is_the_adk` for why. In the ADK's scope and on its
        roadmap; not part of this preview release.

Geometry and attachment
-----------------------

.. glossary::

    chiplet boundary
        The mechanical outline of a placed die, as recorded in the boundary
        manifest. It is assembly metadata, not a fabrication layer, and it is
        what the placement rules operate on. See
        :doc:`/formats/04_boundary_manifest`.

    courtyard
        The keep-out area around a component in board-tool vocabulary. KiCad's
        native courtyard collision check is what mirrors the overlap rule on the
        design-time side. See :doc:`/adk/06_kicad_dru`.

    attachment
        The general act of joining a die to the interposer, independent of the
        physical mechanism. The ADK's abstract ``chiplet_attachment_input``
        names the region where this can happen.

    attachment method
        The concrete mechanism and its parameters: Cu pillar, solder bump,
        microbump. A property of the bumping process, not of the substrate, and
        therefore a separate adapter axis.

    Cu pillar
        A copper post attachment method. On the IntM4TM2 interposer the
        attachment region is formed where the passivation opening and the final
        copper pad overlap.

    pillar manifest
        The sidecar recording the as-drawn attachment centres, after any
        collision auto-resolve has moved them. As-drawn, not as-requested. See
        :doc:`/formats/05_pillar_manifest`.

    pitch
        Centre-to-centre distance between adjacent attachment points. KLayout
        has no native pitch check, so the ADK converts it to a spacing. See
        :doc:`/adk/04_ixn_rules`.

    spacing
        Edge-to-edge distance between adjacent shapes.

    flip chip
        Mounting a die face down so its pads meet the substrate directly.
        Requires mirroring the die's coordinates, which propagates through the
        export, the GDS generation and the viewer.

Formats and frames
------------------

.. glossary::

    .chiplet
        The YAML assembly interchange format: what is placed, where, mounted
        how. The pivot artefact of the flow and the authoritative placement
        source. See :doc:`/formats/01_chiplet`.

    boundary manifest
        ``<gds-stem>.boundaries.json``. One polygon per placed chiplet, carried
        beside the assembly GDS.

    canonical frame
        The coordinate frame every placement in a ``.chiplet`` file is expressed
        in: GDS-bbox-corner, the lower-left corner of the interposer's GDS
        bounding box. Several other frames exist inside individual tools and
        never appear in the format. See :doc:`/formats/03_coordinate_frames`.

    anchor
        Which point of a component its recorded position refers to.

    connection stack
        A named sequence of layers with heights that describes how a die is
        mounted above the interposer surface. Its total height is what makes a
        die's z value verifiable.

    DBU
        Database unit. The integer grid a layout is stored on. Boundary polygons
        are authoritative in DBU; the micron copies are provenance.

    ``.lyp``
        A KLayout layer properties file. Shared across the ecosystem as the
        single source of truth for layer names, numbers and display.

    3Dblox
        An assembly description format on the standards track as IEEE P3537,
        with a BSD-3 licensed implementation in OpenROAD. The ADK exports to it
        so OpenROAD's geometry linter can check an assembly. See
        :doc:`/formats/08_3dblox_interop`.

    HyperLynx (``.hyp``)
        A board-level interchange format. Used here to carry routing out of the
        layout tool and into GDS generation.

Tools
-----

.. glossary::

    ADK-Tools
        The container image that pins and builds every tool in the flow, and
        carries the reference design. See :doc:`/tools/07_adk_tools_image`.

    Chiplet Studio
        The 3D assembly viewer and ``.chiplet`` editor.

    gds2kicad
        The converter that turns a die GDS into a KiCad footprint, symbol and
        pin list.

    hyp_to_gds
        The converter that turns board-level routing into fabricable assembly
        geometry, and that emits the boundary and pillar manifests.

    DRU
        KiCad's custom design rule format. The ADK generates a section of it so
        part of the assembly rule set can be checked while laying out.
