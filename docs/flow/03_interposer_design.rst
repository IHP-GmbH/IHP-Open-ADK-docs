Designing the interposer
========================

.. include:: /common.inc

The interposer is authored as a KiCad board: a few metal layers, vias between
them, pads at the top for the dies and pads at the edge for the outside world,
and routing in between, at feature sizes three orders of magnitude below a PCB.
That scale is why the flow uses the ADK KiCad build rather than upstream KiCad.
This page covers setting up the board,
placing the dies, routing, and running the design-time assembly checks.
:doc:`/tools/01_kicad_adk_mod` describes the fork itself.

Before you start
----------------

You need:

* the chiplet footprints and symbols from :doc:`/flow/02_die_to_kicad`, in the
  project library;
* an interposer technology on disk, reachable through
  ``INTERPOSER_PDK_ROOT``;
* an interconnect technology on disk, reachable through
  ``INTERCONNECT_PDK_ROOT``, if any die is attached by bumps or pillars.

Inside the tools image all three roots are already set. Outside it, see
:doc:`/install/03_environment`.

Start from the template board
-----------------------------

The interposer technology ships a template board at
``libs.tech/kicad/interposer_template.kicad_pcb``. Copy it into your project's
``kicad/`` directory under your board name and open it with the ADK KiCad
build.

Starting from the template matters for one specific reason. The HYP-to-GDS
converter maps board copper layers onto interposer metals **by name**. A board
that keeps KiCad's default copper names leaves all its routing on layers the
technology does not recognise. When most of the routing lands on unmapped
layers the exporter aborts; when only some of it does, it warns and continues,
which is worse. The template ships the renames already applied:

.. list-table::
    :header-rows: 1
    :widths: 30 30 40

    * - KiCad layer
      - Renamed to
      - Position in the stack
    * - ``F.Cu``
      - ``TopMetal2``
      - Top metal, carries the die attachment pads and the I/O pads
    * - ``In1.Cu``
      - ``TopMetal1``
      - Thick upper metal
    * - ``In2.Cu``
      - ``Metal5``
      - Thin metal
    * - ``B.Cu``
      - ``Metal4``
      - Thin metal, bottom of the retained stack

To apply the renames to an existing board instead, open
*Board Setup > Board Editor Layers* and enter the metal names as the
user-defined layer names.

The template also ships a small example mesh on ``Metal5``, a few traces on the
other metals and the four vias that connect them. Keep them while you find your
feet, then delete them. They are a reference, not part of your design.

Draw the outline
----------------

Draw the interposer outline on ``Edge.Cuts``, as a closed polygon.

This is not optional and not cosmetic. The exporter derives the interposer
dimensions from the outline bounding box, and it warns about components placed
outside it. The HyperLynx writer refuses to run without a closed outline, and
the resulting error message, ``Hyperlynx writer aborted``, is the single most
common export failure.

The reference design's interposer is about 6492 by 5602 um.

Project text variables
----------------------

Three board-level variables tell the export and the assembly DRC how to resolve
the technologies. Set them in *Board Setup > Text Variables*. The template
ships none of them pre-populated.

.. list-table::
    :header-rows: 1
    :widths: 26 74

    * - Variable
      - Meaning
    * - ``INTERPOSER_LYP``
      - Path to the interposer layer-properties file. Write it in the portable
        form ``${INTERPOSER_PDK_ROOT}/libs.tech/klayout/tech/intm4tm2.lyp``:
        consumers expand ``${INTERPOSER_PDK_ROOT}`` through the shared
        discovery chain, so the board stays portable between machines. When
        the variable is unset, readers fall back to the same discovery.
    * - ``INTERPOSER_ADAPTER``
      - The ADK interposer adapter the assembly DRC should use. Defaults to
        ``intm4tm2``; set it only to override.
    * - ``INTERCONNECT_ADAPTER``
      - Optional interconnect method identifier, the second adapter axis. It is
        validated against the interconnect manifest at export time. Per-die
        overrides live in a footprint field, not here.

.. note::
   ``KICAD_CHIPLET_PYTHON`` can also be set as a project text variable. It
   names the interpreter that runs the export worker, and it is useful when
   the plugin's own virtual environment is missing. The dialog field for it
   takes precedence and is the only override that applies without restarting
   KiCad.

The reference design sets exactly one variable, ``INTERPOSER_LYP``, and lets
both adapters fall back to their defaults.

Register the project libraries
------------------------------

The chiplet footprints and symbols belong to the project, not to a global
library. Register them with ``${KIPRJMOD}`` paths so the project relocates
cleanly:

.. code-block:: text

    (fp_lib_table
      (version 7)
      (lib (name "my_design")(type "KiCad")
           (uri "${KIPRJMOD}/my_design.pretty")(options "")(descr ""))
    )

and the matching ``sym-lib-table`` entry pointing at
``${KIPRJMOD}/my_design.kicad_sym``.

Draw the schematic
------------------

The schematic is optional for geometry but not for connectivity: it is what
gives the board its netlist, and the netlist is what the exported ``.hyp``
carries into the GDS. Place one symbol per die, one per I/O pad, wire the nets,
and assign footprints.

Because gds2kicad uses the pad name as the KiCad pad number and the same string
as the symbol pin number, pins map onto pads by silicon name. A pin that does
not resolve means the symbol and the footprint came from different revisions of
the die.

Place the dies
--------------

Place each die footprint on the board and set two fields per die instance.
These are per-instance fields on the board, not properties of the library
footprint, and the export dialog reads and writes them, so the board remains
the source of truth.

.. list-table::
    :header-rows: 1
    :widths: 26 74

    * - Field
      - Meaning
    * - ``CONNECTION``
      - The interconnect method for this die, for example ``cupillar_opt1`` or
        ``sbump_sac305``. It selects the connection stack, and with it the die's
        z position, the 3D bodies rendered downstream, and the pitch and
        spacing numbers the interconnect rules will check. Left unset, the die
        follows the assembly-wide default chosen in the export dialog.
    * - ``DIE_THICKNESS_UM``
      - The physical z extent of the silicon die body, in micrometres. It lands
        in the ``.chiplet`` as ``components[].dimensions.thickness``.

``DIE_THICKNESS_UM`` deserves a moment. It is **not** the interconnect
thickness: the stack height of the attachment method comes from the
interconnect manifest and is fab data, not something you set on the board. The
die body extends upward from the seating plane the stack defines.

.. warning::
   Leaving ``DIE_THICKNESS_UM`` empty is not free. The die exports with
   ``thickness: 0.0``, which the 3Dblox exporter rejects outright and which
   downstream viewers and the multiphysics helper each silently replace with a
   different guess. The export warns about every die that ships a zero, and
   about values outside roughly 50 to 2000 um, which are almost always
   millimetres or nanometres typed into a micrometre field. 750 um is a typical
   SG13G2 die.

A die whose footprint was generated with ``--flip-chip`` already carries
``ORIENTATION`` as ``flip_chip``, and the export propagates that into the
``.chiplet`` and into the per-layer mirroring of the die geometry.

Place the I/O pads
------------------

Place one I/O pad footprint per external connection at the interposer edge.
The export scans the board for footprints carrying an ``IO_CLASS`` property,
renders them into the interposer GDS and injects them under the interposer
component in the ``.chiplet``. Nothing else is needed to make them appear
downstream. The reference design places 35 wire-bond pads, 100 by 100 um.

Route
-----

Routing is ordinary KiCad routing on layers with unusual numbers. The reference
design uses per-metal net classes, because KiCad carries a track width and a
clearance per net class rather than per layer:

.. list-table::
    :header-rows: 1
    :widths: 28 24 24 24

    * - Net class
      - Track width
      - Clearance
      - Via
    * - ``Metal4_Metal5``
      - 0.2 um
      - 0.21 um
      - 6 um / 3 um drill
    * - ``TopMetal1``
      - 1.64 um
      - 1.64 um
      - 6 um / 3 um drill
    * - ``TopMetal2``
      - 2 um
      - 2 um
      - 6 um / 3 um drill

Assign each net the class matching the metal it will be routed on. This is a
convention rather than an enforced mapping: it gives you a usable live
clearance check while routing, and the technology's own DRC deck is what
actually signs off the metal geometry once the GDS exists.

.. note::
   A 0.2 um track with a 0.21 um clearance is where upstream KiCad stops being
   usable. The fork is hardened for this regime: int64 coordinate arithmetic,
   grids down to the nanometre, rendering that stays correct at extreme zoom,
   adaptive zone fill and six-decimal-place export precision. Nothing in this
   page works on a stock KiCad build.

The interposer technology also ships real-size device footprints, currently the
IntM4TM2 MIM capacitor family. Their pads sit on the two inner copper layers
(``In1.Cu`` for the ``TopMetal1`` plate, ``In2.Cu`` for the ``Metal5`` plate),
so routing to them happens on those inner metals rather than on the outer
copper. That is expected for this metal stack.

.. figure:: /_figures/screenshots/kicad-interposer-routed-fanout.png
    :align: center
    :width: 55%
    :alt: A KiCad canvas showing one die footprint with a dense named pad ring
          at its perimeter, fan-out traces running outward from the pads, and
          square wire-bond I/O pad footprints placed around the die.

    A routed board in the ADK KiCad build, zoomed to a single die. The die
    footprint is at the centre, carrying the named pad ring that ``gds2kicad``
    generated from the die GDS. The traces fan out from those pads to the
    square wire-bond I/O pad footprints placed around it. The pad names are
    silicon names and are too small to read at this width; the view is the
    working zoom level, not the whole board.

Check while you design
----------------------

Two checks run inside KiCad, before any export.

**KiCad's own DRC** checks the board rules: clearances, track widths, unrouted
nets, courtyard collisions.

**The generated ADK assembly rules** check the placement rules the ADK owns.
Generate the section and append it to your project's ``.kicad_dru``:

.. code-block:: bash

    python3 ${ADK_ROOT}/kicad/dru/generate_assembly_dru.py \
        --interposer-adapter intm4tm2 \
        --out assembly_rules.kicad_dru

The generated block is small on purpose, and its header says why:

.. code-block:: text

    # Coverage:
    #   * ASM.a (chiplet boundary overlap) -- enforced by KiCad's native
    #     courtyard collision check; no rule emitted here.
    #   * ASM.b (chiplet-to-chiplet spacing) -- emitted below.
    #   * ASM.e (chiplet minimum area) and ASM.f (attachment geometry inside
    #     chiplet) have no clean KiCad DRU equivalent and are enforced
    #     post-layout only by the ADK KLayout deck (adk/klayout/drc).

So one rule is emitted, chiplet-to-chiplet spacing, expressed as a courtyard
clearance:

.. code-block:: text

    (rule "ASM.b - Chiplet min spacing"
      (constraint courtyard_clearance (min 50um))
      (condition "A.Type == 'Footprint' && B.Type == 'Footprint'"))

.. note::
   The 50 um default is an ADK engineering default. It is not a foundry rule
   and carries no recorded provenance from one. Override it through the rule
   parameters or an adapter if your assembly process says otherwise. The
   interconnect pitch and spacing defaults are different in this respect: those
   do trace to the bumping vendor's Cu-pillar table. See
   :doc:`/adk/03_asm_rules` and :doc:`/adk/04_ixn_rules`.

The generator and the KLayout deck read the same rule-parameter registry and
apply adapter overrides identically, so the number you see while routing is the
number the post-layout deck will check. :doc:`/adk/06_kicad_dru` covers
regeneration, adapter overrides and how to keep the file in step with the ADK
release you are pinned to.

What is not checked here
------------------------

The design-time checks are a mirror of a subset of the assembly rules, and the
mirror is deliberately incomplete:

* minimum chiplet area and attachment-geometry containment have no clean KiCad
  expression and run only post-layout;
* the interconnect pitch and spacing rules operate on the as-drawn bumps, which
  do not exist until the export generates them;
* the interposer technology's own fabrication rules run on the GDS, not on the
  board.

A board that passes KiCad DRC is ready to export, not verified.
:doc:`/flow/06_verification_stages` lays out which check runs when.

Next
----

Continue with :doc:`/flow/04_export`.
