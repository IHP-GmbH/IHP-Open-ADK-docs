Components and optional blocks
==============================

.. include:: /common.inc

This page continues :doc:`/formats/01_chiplet` with the blocks that describe
what an assembly places, the blocks a file may omit entirely, and a complete
worked file.


The components block
--------------------

An array of component definitions. Each entry is one physical element of the
assembly.

.. list-table:: Component fields
    :header-rows: 1
    :widths: 24 10 16 50
    :class: adk-wide-table

    * - Key
      - Required
      - Default
      - Description
    * - ``id``
      - yes
      -
      - Unique component identifier. Uniqueness is expected by consumers, not
        enforced by the reference reader.
    * - ``type``
      - yes
      -
      - ``die``, ``die_array``, ``interposer`` or ``substrate``.
    * - ``technology``
      - no
      - ``""``
      - Reference to a technology id.
    * - ``anchor``
      - see note
      - ``bbox_center``
      - How the component's mesh is centred: ``gds_origin`` or
        ``bbox_center``. New files must declare it; readers warn and default
        when it is absent.
    * - ``layout``
      - no
      - ``""``
      - Path to the GDS or OASIS layout file.
    * - ``top_cell``
      - no
      - ``""``
      - Top cell name in the layout, single-cell form.
    * - ``cells``
      - no
      -
      - One or more cell names. ``top_cell`` is the single-cell shorthand;
        writers emit ``top_cell`` for one cell and ``cells`` for several.
    * - ``position``
      - no
      - ``{x: 0, y: 0, z: 0}``
      - 3D position of the component's geometric centre in x and y, and its
        seating plane in z, in the canonical frame.
    * - ``rotation``
      - no
      - ``{z: 0}``
      - Rotation about z in degrees.
    * - ``orientation``
      - no
      - ``face_up``
      - Mounting orientation of a die: ``face_up`` or ``flip_chip``.
    * - ``connection``
      - no
      - ``""``
      - Interconnect method id this die mounts on, for example
        ``cupillar_opt1``. Drives per-die z-mounting.
    * - ``dimensions``
      - no
      - ``{width: 0, height: 0, thickness: 0}``
      - Physical size in micrometres.
    * - ``attachment_surface_z``
      - no
      -
      - Interposer only. Z of the die-attachment surface in the
        component-local frame.
    * - ``io_pads``
      - no
      - ``[]``
      - Assembly-level I/O pads, nested under the interposer.
    * - ``array``
      - no
      -
      - Array configuration, ``die_array`` only.
    * - ``metadata``
      - no
      - ``{}``
      - Free-form key/value pairs.

The four component types are the canonical values. The reference reader
requires only a non-empty ``type`` string and does not reject other values, so
a non-canonical type will load but no ADK consumer will know what to do with
it: ``chiplet2dbx``, for example, accepts ``die`` and ``interposer`` only and
requires exactly one interposer.

Geometry: position, dimensions and anchor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``position`` is the component's **geometric centre** in x and y, and its
**seating plane** in z, that is, the bottom face of the placed body. The frame
is the lower-left corner of the interposer top cell's GDS bounding box, y-up,
micrometres. ``dimensions.thickness`` extends the body upward from
``position.z``.

``anchor`` declares how the component's local mesh is built, and it is
independent of ``type``:

- ``gds_origin``: the mesh is built around the component's own GDS ``(0, 0)``.
  This is what ``gds_to_kicad`` produces, so dies use it.
- ``bbox_center``: the mesh is centred on the component's own GDS bounding
  box. Interposers use it.

The reader must take the anchor from this field, never infer it from the
component type. The full contract, the leak guard, and worked arithmetic for
turning a die-local coordinate into an assembly coordinate are in
:doc:`/formats/03_coordinate_frames`.

orientation
~~~~~~~~~~~

``orientation`` records how a die is mounted. The specification document lists
``face_up``, ``flip_chip`` and ``face_down``, and the reference reader keeps
whatever string it finds, but the coordinate-frame contract governs and is
narrower: **only** ``face_up`` and ``flip_chip`` are canonical, and writers must
emit only those. ``face_down`` records a mounting intent whose geometric
realisation the format never pinned down.

The ADK consumers implement the contract, not the looser reading. Both
``pads_vs_pillars`` and ``chiplet2dbx`` reject ``face_down`` and any unknown
token as a hard error rather than guess; an interactive viewer may keep
rendering but must warn, and must never silently render an unknown token
un-mirrored.

An absent ``orientation`` means ``face_up``. The reference C++ writer
suppresses ``face_up`` on output and emits the key only for non-default
values.

``orientation`` is assembly intent. The geometric effect, an x-mirror of the
die artwork applied before ``rotation.z``, is realised by the writer when it
emits the layout, and by any consumer that has to place die-local coordinates.

connection and per-die z-mounting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``connection`` names an entry in ``connection_stacks`` (equivalently, in the
interconnect method registry). Z-mounting is per-die:

.. code-block:: text

    z_die = mounting_surface + connection.total_height()

so one assembly can mix methods. In the reference design U1 sits on
``cupillar_opt1`` (28 + 16 = 44 um) and U2 on ``vendorx_microbump``
(18 + 6 = 24 um) over the same interposer, landing at z 57.83 and 37.83
respectively. A die with no ``connection``, or one whose ``connection`` does
not resolve, falls back to the interposer's mounting surface with zero
connection height. A die with an explicit non-zero ``position.z`` keeps that
value; the reader does not recompute it.

The interposer attachment_surface_z
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``attachment_surface_z`` is the newest field in the schema and applies to the
interposer only. It is the z of the die-attachment surface, the BEOL top
through the passivation opening, expressed in the interposer-local frame. It is
the plane dies mount on:

.. code-block:: text

    z_die = attachment_surface_z + connection height

For the IHP IntM4TM2 interposer the value is ``13.83``: the TopMetal2 bottom
at 10.83 plus its 3.00 thickness.

The field exists to decouple the mount reference from ``dimensions.thickness``.
Before it existed, ``thickness`` had to double as the mount reference, so it
could not also carry the physical substrate body. With
``attachment_surface_z`` present, ``thickness`` means what it means everywhere
else, the physical z-extent of the body (silicon plus BEOL), and the body
extends **downward** from the attachment surface while dies sit above it.

The change is backward compatible. When ``attachment_surface_z`` is absent,
consumers fall back to ``dimensions.thickness`` as the mount reference, which
is its historical meaning, so files written before the field existed still seat
their dies correctly.

.. note::

    Neither fallback ever puts dies at world z = 0. Returning 0 for an
    unresolvable mount reference was a real bug that dropped every die to the
    origin.

io_pads
~~~~~~~

Assembly-level I/O pads, wire-bond pads in practice, are listed under the
interposer component. Each pad is a point in the same canonical frame as
components, so pads do not declare an ``anchor`` of their own.

.. code-block:: yaml

    io_pads:
      - id: J1                 # pad reference
        io_class: wire_bond    # free-form pad class
        net: VDD               # free-form net name
        position: {x: 100.0, y: 100.0}
        size: {x: 80.0, y: 80.0}
        layer: TopMetal2

Unlike ``interfaces[].type``, ``io_class`` is free-form with no closed
vocabulary: ``wire_bond`` is a convention, not an enforced value. ``size`` is
optional, and the reference C++ writer emits it for every pad.

die_array
~~~~~~~~~

A ``die_array`` component replaces ``position`` with an ``array`` block:

.. code-block:: yaml

    array:
      pattern: grid            # "grid", "linear" or "custom"
      count: {x: 2, y: 2}      # integers >= 1
      pitch: {x: 6000, y: 6000}
      start_position: {x: 25000, y: 15000, z: 1100}

``chiplet2dbx`` rejects ``die_array`` components outright: the geometric export
accepts ``die`` and ``interposer`` only. The 3Dblox mapping specifies unrolling
into individual instances, but no ADK tool implements that today, so unroll the
array in the ``.chiplet`` before exporting.


Optional blocks
---------------

interconnect
~~~~~~~~~~~~

Declares the interconnect axis for the assembly. It is recognised **only when
it carries an** ``adapter``; a block without one is ignored. The optional
``technology`` gives the interconnect a PDK-backed identity with the same shape
as a ``technologies`` entry, and is registered under the adapter id so that it
resolves through the ordinary technology lookup.

.. code-block:: yaml

    interconnect:
      adapter: vendorx_microbump
      technology:
        description: "Chiplet attachment (VendorX Microsystems (DEMO / non-IHP))"
        layer_properties: ${INTERCONNECT_PDK_ROOT}/libs.tech/klayout/tech/interconnect.lyp
        dbu: 0.001

Declaring an adapter here is what turns on the interconnect DRC axis
downstream: the orchestrator forwards it as ``--interconnect-adapter``, and a
design that declares none never silently gains the assembly-global IXN pitch
and spacing checks. See :doc:`/adk/04_ixn_rules`.

interfaces
~~~~~~~~~~

A list of typed die-to-die and bond interfaces. Each entry needs an ``id`` and
a ``type``, and the type is checked against a closed vocabulary:
``micro_bump``, ``copper_pillar``, ``tsv``, ``wire_bond``.

.. code-block:: yaml

    interfaces:
      - id: ucie_link_0
        type: micro_bump
        from: {component: U1, surface: top, port_layer: TopMetal2}
        to:   {component: interposer, surface: top, port_layer: Metal5}
        physical: {pitch: 45.0, diameter: 25.0, height: 24.0}

``from``, ``to`` and ``physical`` are optional. The C++ reference validator
rejects an unknown ``type``; the Python reference validator does not check the
vocabulary and will accept one.

netlist
~~~~~~~

An optional assembly netlist, either inline under ``nets`` or by path under
``external_netlist``.

.. code-block:: yaml

    netlist:
      nets:
        - name: VDD
          class: power             # default "signal"
          external: true           # exposed at the assembly boundary
          connections:
            - {component: U1, pin: VDD, layer: TopMetal2}
            - {component: interposer, pin: P12, layer: Metal5}

An otherwise-empty ``netlist`` block is not preserved on write. The netlist is
what lets ``chiplet2dbx`` bind bump rows to nets: without it, bump port and net
columns are emitted as ``-``.

flow
~~~~

An opaque build and flow block. The format leaves its contents entirely
unspecified; readers preserve it verbatim across a load and dump cycle and
re-parse it only if they care. It is the right place to record that a derived
``.3dbx`` export exists and how it was produced.

.. code-block:: yaml

    flow:
      steps:
        - {name: export, tool: kicad}
        - {name: assemble, tool: hyp_to_gds}

_metadata and intermediate files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A writer that cannot yet produce the canonical frame marks its output as
intermediate. KiCad's GUI export is the case that matters: it does not read the
interposer GDS, so it cannot express positions in the interposer's GDS-bbox
frame.

.. code-block:: yaml

    _metadata:
      frame: pcb-bbox-corner
      finalize_required: true
      finalizer: hyp_to_gds.py --update-chiplet-file

A reader must refuse to load a file whose ``_metadata.finalize_required`` is
``true`` unless intermediate files are explicitly allowed. The reference
libraries implement this as a hard error with a message naming the finalizer;
the Python reader takes ``allow_intermediate=True`` to bypass it, and writing an
intermediate document is always permitted. The finalizer converts positions
into the canonical frame and strips the block, so a canonical ``.chiplet``
carries no ``_metadata``.

Proposed extensions: cdxml_ref and 3dblox_ref
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Neither field is part of the v1.0 schema. Both are documented so that the
interop hook is well defined, and both are optional and additive: a reader that
does not understand one must ignore it, and its presence never changes
placement, the coordinate frame or z-mounting.

.. code-block:: yaml

    cdxml_ref:
      mpn: "ACME-PHY-0001"               # manufacturer part number
      opn: "ACME-PHY-0001-R"             # ordering part number (optional)
      version: "1.0"                     # part-document version (optional)
      uri: "./parts/acme_phy.cdxml"      # path or URL (optional)
      sha256: "<hex>"                    # content hash (optional)

    3dblox_ref:
      chiplet: "cpu_die"                 # ChipletDef name inside the .3dbv
      uri: "./views/cpu_die.3dbv"        # path or URL (optional)
      sha256: "<hex>"                    # content hash (optional)

At least one of ``mpn`` or ``uri``, respectively ``chiplet`` or ``uri``, should
be present so that the reference resolves. All keys are strings.

``3dblox_ref`` is deliberately component-level only;
:doc:`/formats/08_3dblox_interop` explains why an assembly-level reference is not
proposed.

Today the Python reference reader preserves both fields, because it keeps the
full mapping; the C++ struct reader does not round-trip them. Treat both as
opt-in metadata until first-class support lands.


A complete example
------------------

The canonical worked example ships with the specification as
``examples/interposer_demo_design.chiplet``. It is a two-die, mixed-method
assembly on an IHP IntM4TM2 interposer: U1 seats on an IHP Cu pillar stack and
U2 on a non-IHP vendor microbump, so the two dies land at different heights
from the same per-die z-mounting rule. Its numbers mirror the coordinate-frame
contract's worked example.

.. code-block:: yaml

    format_version: "1.0"

    assembly:
      name: "IntM4TM2 mixed-method demo (illustrative)"
      description: "Two SG13G2 dies on an IntM4TM2 interposer; mixed interconnect methods"
      units: um

    technologies:
      intm4tm2:
        description: "IHP 130nm IntM4TM2 aluminium BEOL interposer"
        layer_properties: ./tech/intm4tm2.lyp
        dbu: 0.001
      sg13g2:
        description: "IHP SG13G2 130nm BiCMOS die"
        layer_properties: ./tech/sg13g2.lyp
        dbu: 0.001

    connection_stacks:
      cupillar_opt1:
        description: "IHP Cu pillar (CuPillar 28 + SnAgCap 16 = 44 um)"
        layers:
          - {name: CuPillar, material: Cu,   height: 28.0, diameter: 44.0}
          - {name: SnAgCap,  material: SnAg, height: 16.0, diameter: 44.0}
      vendorx_microbump:
        description: "VendorX microbump, non-IHP (Cu 18 + cap 6 = 24 um)"
        layers:
          - {name: VendorXBumpCu,  material: Cu,   height: 18.0, diameter: 40.0}
          - {name: VendorXBumpCap, material: SnAg, height: 6.0,  diameter: 40.0}

    components:
      - id: interposer
        type: interposer
        technology: intm4tm2
        anchor: bbox_center
        layout: ./gds/interposer.gds
        top_cell: INTERPOSER
        position: {x: 3246.156, y: 2801.000, z: 0.0}      # full GDS-bbox centre
        dimensions: {width: 6492.312, height: 5602.001, thickness: 300.0}
        attachment_surface_z: 13.83                       # BEOL-top mount plane
        io_pads:
          - id: J1
            io_class: wire_bond
            net: VDD
            position: {x: 100.0, y: 100.0}
            size: {x: 80.0, y: 80.0}
            layer: TopMetal2
          - id: J2
            io_class: wire_bond
            net: GND
            position: {x: 6392.0, y: 5502.0}
            size: {x: 80.0, y: 80.0}
            layer: TopMetal2

      - id: U1
        type: die
        technology: sg13g2
        anchor: gds_origin
        orientation: flip_chip
        connection: cupillar_opt1                          # IHP Cu pillar
        layout: ./gds/Metal_Test.gds
        top_cell: Metal_Test
        position: {x: 1954.121, y: 2332.483, z: 57.83}     # 13.83 + 44
        dimensions: {width: 730.0, height: 2566.339, thickness: 750.0}
        rotation: {z: 0.0}

      - id: U2
        type: die
        technology: sg13g2
        anchor: gds_origin
        orientation: flip_chip
        connection: vendorx_microbump                      # non-IHP microbump
        layout: ./gds/vendor_die.gds
        top_cell: VENDOR_DIE
        position: {x: 5170.23, y: 2420.27, z: 37.83}       # 13.83 + 24
        dimensions: {width: 730.0, height: 2566.339, thickness: 750.0}
        rotation: {z: 0.0}

Read it in this order:

1. ``attachment_surface_z: 13.83`` fixes the plane dies mount on. The
   interposer's own ``thickness: 300.0`` is the physical body below that plane
   and plays no part in seating the dies.
2. U1's ``connection: cupillar_opt1`` totals 28 + 16 = 44 um, so
   ``z: 57.83 = 13.83 + 44``.
3. U2's ``connection: vendorx_microbump`` totals 18 + 6 = 24 um, so
   ``z: 37.83 = 13.83 + 24``. The two dies share an interposer and an assembly
   but not a height, which is the point of making the rule per-die.
4. The interposer's ``anchor: bbox_center`` and ``position`` at
   ``(3246.156, 2801.000)`` place its bbox centre at half its extent, which is
   what you expect when the origin is that same bbox's lower-left corner.
5. Both dies use ``anchor: gds_origin`` because ``gds_to_kicad`` puts the
   footprint origin at GDS ``(0, 0)``.

The ADK reference design, ``examples/two_die_interposer/`` in |tools-repo|,
is the same topology as actually generated by the flow. It differs from the
illustrative file above in three instructive ways: it carries every published
connection stack whether used or not, it declares the
``interposer:`` and ``interconnect:`` adapter blocks that drive the DRC run,
and its technology paths are written as ``${VAR}`` references so that the file
survives being read from a different checkout.

.. tip::

    Two things in a real exported file look like noise and are not.
    Coordinates such as ``3246.1560000000027`` are the honest float result of a
    bbox halving, not sloppy rounding, and the component order is the exporter's
    traversal order, not a meaningful sequence: readers are key driven and order
    independent.



Where to go next
----------------

- :doc:`/formats/03_coordinate_frames` for the normative frame, anchor and
  z-mounting semantics the geometry fields above summarise.
- :doc:`/formats/01_chiplet` for the root structure, the path convention and
  the reference reader and writer libraries.
- :doc:`/formats/08_3dblox_interop` and :doc:`/adk/07_chiplet2dbx` for the
  3Dblox export.
