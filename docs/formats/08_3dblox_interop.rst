3Dblox interoperability
=======================

.. include:: /common.inc

3Dblox and ``.chiplet`` describe the same thing, a multi-die physical assembly,
bound to two different abstraction levels. An exploration-level model and a
mask-level model of one assembly are both useful, so the relationship the
specification defines is interop rather than rivalry: a field-by-field mapping,
a proposed reference field, and one rule about which file is authoritative.

This page describes the mapping. :doc:`/adk/07_chiplet2dbx` documents the
exporter in the ADK that implements it.

.. note::

    The mapping is an **informative appendix** to the ``.chiplet``
    specification. Nothing in it changes the on-disk format;
    ``format_version`` stays ``"1.0"``. Where the appendix and the format
    specification or the coordinate-frame contract could appear to differ,
    those documents govern.


What 3Dblox is
--------------

3Dblox was originated by TSMC and is being standardised as **IEEE P3537**. It
describes multi-die physical assemblies through three file kinds:

- **``.3dbv``**, chiplet definitions: ``ChipletDef`` entries with a per-die
  technology, design area and thickness, named bond regions, and linkage to
  place-and-route views (LEF, DEF, Verilog, Liberty).
- **``.3dbx``**, the assembly: a ``Design`` with chiplet instances
  (``ChipletInst``, carrying 3D placement and orientation), region-to-region
  connections, and netlist linkage.
- **``.bmap``**, per-bump maps binding individual bump instances to ports and
  nets.

An open-source implementation exists in **OpenROAD** under BSD-3: a multi-die
database, ``read_3dbx`` ingestion, an automatic assembly linter
(``check_3dblox``, with seven checks covering floating components, 3D overlap,
connection-region validity, bump alignment, internal-extension usage, logical
connectivity against a declared netlist, and alignment markers), and a 3D
viewer. That linter is the reason an export is worth producing: it is a second,
independently written opinion about an assembly the ADK has already checked at
the mask level.

The abstraction split is the whole story. 3Dblox binds an assembly to the P&R
abstraction for multi-die EDA and design-space exploration, and references no
artwork files. ``.chiplet`` binds it to the mask level: GDS and OASIS bodies,
``.lyp`` layer properties, per-layer interconnect metallurgy, and fab DRC
parameters, for assembly checking and fabrication hand-off.


The shared core
---------------

Both formats express multi-die assemblies with a per-die technology; 2D
placement plus z; die thickness; flip and mounting orientation; die outlines;
black-box dies; assembly-level nets; and explicit units and resolution. That
overlap is what makes a mechanical export possible at all.


Forward mapping, .chiplet to 3Dblox
-----------------------------------

The export is **lossy by declaration**: the fields listed further down have no
target and are dropped deliberately, not by accident.

.. list-table:: Field-by-field mapping
    :header-rows: 1
    :widths: 30 30 40
    :class: adk-wide-table

    * - ``.chiplet`` source
      - 3Dblox target
      - Notes
    * - ``die`` component
      - ``ChipletDef`` in the ``.3dbv`` plus an instance in the ``.3dbx``
      - One def per distinct die, one instance per placement.
    * - ``dimensions.width`` / ``height``
      - design area
      -
    * - ``dimensions.thickness``
      - def thickness
      - **Always** the physical thickness. Never derived from a visualisation
        stackup.
    * - ``position`` (geometric centre)
      - instance placement
      - 3Dblox places by corner. Convert centre to corner through the outline
        before emitting.
    * - ``orientation: face_up`` (default)
      - ``R0``
      -
    * - ``orientation: flip_chip``
      - ``MZ``, the flipped mounting
      - See the flip section below.
    * - ``orientation: face_down``
      - none
      - Deliberately unmapped. An exporter that needs it must pin and verify
        its own convention.
    * - ``rotation.z``
      - ``R0`` / ``R90`` / ``R180`` / ``R270``
      - **Only multiples of 90 degrees.** Any other angle must fail the export
        loudly, never round silently.
    * - ``connection`` stack ``total_height()``
      - connection thickness
      - The exact value. See the z section below.
    * - Die and interposer bounding boxes
      - front-side four-corner bond regions
      - Polygonal boundary detail collapses to the bbox.
    * - ``netlist``
      - structural Verilog (optional)
      - Enables the logical-connectivity lint.
    * - ``die_array``
      - unrolled individual instances
      -
    * - ``technologies`` entries
      - per-die technology
      - Requires an external technology LEF per technology, which is not
        derivable from the ``.chiplet`` file.
    * - Black-box pad coordinates
      - candidate ``.bmap`` rows
      - Each pad shape on a vocabulary layer yields one candidate row,
        coordinates only. Bump cell type and port or net binding are not
        derivable from the pad vocabulary.

Flip and z-rotation compose into a **single** 3Dblox orientation value. A die
that is both flipped and rotated must be emitted as one composed orientation,
the flipped variant of the rotation, not as two independent attributes. An
exporter must emit the composed value, verify pad positions, and fail loudly if
the target vocabulary lacks the combination it needs.


What does not map, and why
--------------------------

Dropped by declaration
~~~~~~~~~~~~~~~~~~~~~~

These exist in ``.chiplet`` and have no 3Dblox target, because 3Dblox sits at
the P&R abstraction and does not reference artwork:

1. **Per-layer interconnect metallurgy.** ``connection_stacks`` carries a name,
   material, height and diameter per layer, and derives the die z from the
   stack. 3Dblox has a scalar connection thickness, so the stack collapses to
   one number.
2. **Interconnect method identity and provenance**, that is the
   ``interconnect`` adapter and technology axis and the
   ``interconnect_methods.json`` sidecar.
3. **Fab DRC parameter linkage**: the fab parameters and pitch rules that feed
   a parameterised assembly-DRC flow.
4. **Mask artwork linkage**: GDS and OASIS bodies with ``.lyp`` layer
   properties. 3Dblox references no artwork files; its region schema carries a
   ``gds_layer`` layer-id attribute, which the open implementation parses and
   ignores, but no field references a GDS or OASIS file.
5. **Polygonal boundary manifests**, arbitrary polygons with content hashes.
   3Dblox bond regions are four-corner rectangles.
6. **Black-box pad vocabulary** for closed-PDK dies, that is pad layers usable
   without the die's own layer-properties file.
7. **Assembly-level wire-bond ``io_pads``** and **typed physical interfaces**
   (``micro_bump``, ``copper_pillar``, ``tsv``, ``wire_bond``, with pitch,
   diameter and height).
8. **``die_array``** components. The mapping specifies unrolling into individual
   instances, but no ADK tool implements it, and ``chiplet2dbx`` rejects the
   component type.
9. **Part-description linkage**, ``cdxml_ref``.
10. **Process-safety semantics**: the canonical coordinate frame with a
    declared ``anchor``, the coordinate leak guard, and the ``_metadata``
    intermediate-file marker.
11. The opaque **``flow``** block.

Not expressible in .chiplet v1.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The gap runs the other way too. 3Dblox expresses these, and ``.chiplet`` v1.0
does not:

1. **Named bond regions with a side**, front, back or internal, plus an
   internal-extension variant, with coordinates and a layer.
2. **Per-bump maps** (``.bmap``) binding each bump instance to a port and a
   net. ``.chiplet`` carries pad *vocabulary* and interface *physics*, not a
   per-bump table.
3. **Hierarchical sub-assemblies**, where an assembly is a component of a
   larger one. The open implementation derives a flattened "unfolded" view from
   them.
4. **Seal-ring and scribe** descriptions.
5. **Shrink** factors.
6. **Path assertions**, declared route-path checks across the assembly.
7. A **formal orientation group**, rotations by 90 degrees combined with
   mirrors. The genuinely missing delta in ``.chiplet`` is mirror-X and
   mirror-Y; the common cases are expressible today through ``rotation.z`` and
   ``orientation: flip_chip``.
8. **LEF, DEF, Verilog, Liberty and SDC linkage**. This one is a non-goal for
   ``.chiplet`` by design: it is precisely the abstraction-level split.
9. A **linter-enforced invariant** that a connection's declared thickness
   equals the exact z gap between the connected surfaces. In ``.chiplet`` the
   same equality holds by construction whenever the z-mounting rule computes
   the die z; see below for the explicit-z caveat.

External inputs an export needs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two things the ``.chiplet`` file cannot supply: one technology LEF per die
technology, and bump masters defined in the **die's** technology, not the
substrate's, for bump-level checks. Without per-die DEFs the dies export as
black boxes, and the geometric consistency lints still run.


Conventions that a naive converter gets wrong
---------------------------------------------

These are the three places where a converter produces a model that looks right
and either fails the target linter or, worse, passes with wrong geometry.

Connection thickness is the stack height, exactly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``.chiplet`` z-mounting rule is
``z_die = mounting_surface + connection.total_height()``, so the stack's
``total_height()`` **is** the vertical gap between the attachment surface and
the die bottom. OpenROAD's linter asserts that a connection's declared
thickness equals that gap exactly. So emit
``thickness := connection.total_height()``, never a rounded or nominal value,
and never a gap re-derived from body outlines.

Two caveats follow from the frame contract's fallback rules. First, the
equality is only guaranteed when the die's z defers to auto-calculation. A
``.chiplet`` may carry an explicit ``position.z``, which readers honour as-is,
so an exporter must verify that
``z_die == mounting_surface + total_height()`` and fail loudly on a mismatch
rather than emit a thickness inconsistent with the actual gap. Second, when a
die's ``connection`` id does not resolve to a stack, there is no thickness
source at all, and the export must likewise fail loudly.

The attachment surface is not the maximum z
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``mounting_surface`` resolves to the technology's attachment surface, the pad
top through the passivation opening, which is generally **not** the substrate's
maximum z. Passivation can rise above it: on the reference interposer stackup
the attachment surface sits at 13.83 um while the passivation top lies above
that.

A converter that derives the die-to-substrate gap from an outline maximum z
instead of the attachment surface disagrees with ``total_height()`` by the
passivation height, and fails the exact-equality check. Use the
attachment-surface and stack semantics of the contract, always. See
:doc:`/formats/03_coordinate_frames`.

Flip is a mounting intent, not a shared mirror convention
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``orientation: flip_chip``, a die mounted with its active side toward the
substrate, corresponds to the 3Dblox flipped orientation ``MZ``. The **intent**
maps cleanly. The 2D **realisation** does not: this ecosystem realises the flip
as a layout mirror when it emits 2D views, while 3Dblox composes a formal 3D
orientation with a corner anchor.

An exporter must therefore map the intent and then **verify that pad and bump
coordinates land at identical absolute positions** under the target tool's
orientation-plus-anchor composition. Do not assume the mirror axes agree. In
practice this means pre-mirroring bump coordinates in x for ``flip_chip`` dies,
because the target's flipped orientation leaves bump x and y unchanged.

``face_down`` records a distinct mounting intent whose geometric realisation
the format deliberately leaves to the writer, so it is left unmapped for the
same reason. An exporter that needs it must pin an explicit composition and
verify pad positions against it.

Physical thickness has one source
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A die's physical thickness is ``dimensions.thickness``, always. Visualisation
stackups, render slabs and display-only substrate heights are aesthetic and
must never leak into an exported model.


The reverse direction
---------------------

3Dblox to ``.chiplet`` is coarse and of limited use. A ``.chiplet`` derived
from 3Dblox has no GDS or OASIS bodies, no metallurgy and no DRC parameters, so
it feeds neither a mask-level viewer nor an assembly-DRC flow. It is a
placement skeleton to be enriched by hand. The forward direction is the
productive one, and it is the one the ADK implements.


The 3dblox_ref proposed extension
---------------------------------

A ``die`` or ``die_array`` may cite the 3Dblox ``ChipletDef`` that describes
the same physical die at the P&R abstraction level, so that a mask-level
assembly and a P&R-level view of the same die stay linked without either
duplicating the other.

.. code-block:: yaml

    3dblox_ref:
      chiplet: "cpu_die"              # ChipletDef name inside the .3dbv
      uri: "./views/cpu_die.3dbv"     # path or URL to the .3dbv (optional)
      sha256: "<hex>"                 # content hash for provenance (optional)

At least one of ``chiplet`` or ``uri`` should be present so that the reference
resolves. All keys are strings.

The field is **not part of the v1.0 schema**. It is proposed, optional and
additive: a reader that does not understand it must ignore it, and its presence
never changes placement, the coordinate frame or z-mounting. Today the Python
reference reader preserves it because it keeps the full mapping, while the C++
struct reader does not round-trip it. Treat it as opt-in metadata.

The reference is deliberately **component level only**. An assembly-level
reference, to a ``.3dbx`` that re-states placements and connections for the
whole assembly, is explicitly **not** proposed. Two machine-readable placement
sources for one assembly would create a source-of-truth ambiguity that a
die-level or part-level reference does not have.


One assembly, one authoritative placement source
------------------------------------------------

The ``.chiplet`` file is authoritative for placement and z-mounting. A
``.3dbx`` produced by the mapping above is a **derived export artefact**, to be
regenerated rather than edited.

This is not a preference about tooling; it is what keeps the two models from
disagreeing silently. Edit the ``.3dbx`` and you have two files that both claim
to say where the dies are, with no mechanism to decide which is right and no
check that would notice the divergence.

A project that keeps a derived export alongside its ``.chiplet`` may record the
export step in the opaque ``flow`` block, which exists for exactly this kind of
build provenance. The only proposed schema hook is the component-level
``3dblox_ref`` above.


The exporter in the ADK
-----------------------

``chiplet2dbx`` implements this mapping. It emits dies as black-box
``ChipletDef`` entries (design area, thickness, and full-outline front and back
bond regions, with no cell LEF, DEF or Verilog), the interposer as a
``substrate`` def, and each die's connection stack as a ``Connection`` whose
thickness is the stack's exact total height.

The technology LEF the mapping lists as an external input is the one thing
``chiplet2dbx`` supplies itself rather than asking for: it generates one
minimal LEF per distinct ``.chiplet`` technology, units only and no layers, and
references it as each def's ``APR_tech_file``. That is the smallest thing that
satisfies the target: its database reads every chip's technology DBU without a
null check, and the tech-LEF filename is the identity its loader dedupes
technologies on. A real technology LEF, with layers, is still an external input
for anything beyond the geometric lints.

It refuses to guess. It verifies the z-consistency rule and fails loudly on a
mismatch, on any rotation that is not a multiple of 90 degrees, on
``face_down``, on an unknown orientation token, and on a connection that does
not resolve to a stack with layers. It never rounds silently.

Optionally the export becomes bump aware: given the per-die ``*.pins.json``
artefacts from ``gds_to_kicad``, each die's def gains a ``.bmap`` of bump
centres in the def-local frame, plus a per-method bump macro LEF rendered by
the interconnect PDK's generator. Because a bump map is a property of the
``ChipletDef`` and not of the instance, dies that share artwork but differ in
connection method or net binding split into separate defs.

:doc:`/adk/07_chiplet2dbx` covers the command line, the generated files and the
failure modes in detail. :doc:`/formats/07_pin_lists` describes the pin-list
artefact the bump-aware mode consumes.
