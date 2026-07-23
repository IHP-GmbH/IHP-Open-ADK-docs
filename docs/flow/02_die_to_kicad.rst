From die GDS to KiCad
=====================

.. include:: /common.inc

KiCad cannot read GDSII. Before a die can be placed on an interposer board it
has to exist as a KiCad footprint and, if you want a schematic, as a KiCad
symbol.

gds2kicad reads the pad geometry and the text labels straight out of the
layout instead, so the KiCad part matches the silicon. This page is the task
walkthrough. :doc:`/tools/03_gds2kicad` is the reference for the individual
tools and every flag they accept.

.. note::
   Inside the tools image the whole thing is one command, ``gds-to-kicad``,
   which opens the unified GUI. Its five tabs cover the same ground as this
   page: Extract Pins, Pin List Editor, Symbol Designer, Footprint Generator,
   History. The GUI drives the same engine as the command line, so you can
   move between them freely. The commands below use
   ``${GDS_TO_KICAD_ROOT}``, which the image sets for you.

What you are producing
----------------------

Three artefacts, with three different consumers.

.. list-table::
    :header-rows: 1
    :widths: 22 34 44

    * - Artefact
      - What it holds
      - Who consumes it
    * - ``<die>.kicad_mod``
      - The die outline, one pad per external I/O with its real shape, a
        courtyard, and traceability properties naming the source GDS
      - ``pcbnew``, to place and route the die; the Chiplet Export plugin, to
        find the die layout and to generate bumps from the pads
    * - ``<die>.kicad_sym``
      - One pin per external I/O, arranged on the four sides of a rectangle,
        each with a name and an electrical type
      - ``eeschema``, to draw the assembly schematic and derive the netlist
    * - ``<die>.pins.json``
      - Pad name, electrical type, symbol side and pad geometry in database
        units
      - The symbol generator, the pad-review workflow, and Cu-pillar
        generation, which needs the pad centres

The pin list is worth keeping under version control alongside the die GDS. It
is the only place the human decisions live: which side of the symbol each pin
sits on, and whether a pin is passive, a power input or an output. A footprint
carries no such semantics, so re-extracting a pin list from a footprint
recovers names and geometry but resets sides to ``left`` and types to
``passive``.

Step 1: look at the GDS before converting it
--------------------------------------------

A converter run with no flags auto-detects the densest pad layer and a text
layer to name it from. On a clean, purpose-built chiplet GDS that is the right
answer. On a full die it is not: routing, fill and guard rings are all denser
than the bond pads, and you will get several hundred "pads" that are not pads.

Ask first:

.. code-block:: bash

    python3 gds_to_kicad.py die.gds --scan-layers

That reports the candidate pad and text layers with their shape counts. To see
how a layer-properties file names those layers:

.. code-block:: bash

    python3 gds_to_kicad.py die.gds --list-layers \
        --lyp-file ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp

Step 2: say where the pads are
-------------------------------

There is no PDK baked into gds2kicad, no ``--pdk`` flag and no PDK discovery.
You state the pad layer explicitly, in one of three ways, in this order of
precedence:

.. list-table::
    :header-rows: 1
    :widths: 10 40 50

    * - Precedence
      - How
      - Example
    * - 1
      - Raw GDS layer and datatype, ignoring the ``.lyp``
      - ``--pad-layer-number 134/0``
    * - 2
      - Layer name resolved through a KLayout ``.lyp``
      - ``--lyp-file pdks/sg13g2.lyp --layer TopMetal2.drawing``
    * - 3
      - Nothing, auto-detect the densest pad layer
      - (no flags)

Pin names come from a separate text layer, selected the same way with
``--text-layer NAME`` or ``--text-layer-number N/D``.

.. important::
   Two details cost people an afternoon each.

   The flag spelling differs between the two converters: the footprint tool
   uses ``--layer``, the symbol tool uses ``--pad-layer``. The
   ``*-layer-number`` flags are spelled the same in both.

   If you name the pad layer with ``--layer`` and say nothing about text, the
   footprint tool emits **numbered** pads instead of named ones, silently. Add
   ``--text-layer``, ``--text-layer-number`` or ``--auto-text``. The symbol
   tool does not have this problem: it derives ``TopMetal2.text`` from
   ``TopMetal2.drawing`` itself. When both tools auto-detect the pad layer,
   they auto-detect the text layer too.

Four ready ``.lyp`` files ship under ``pdks/``: ``generic.lyp`` (the default, a
pads-only vocabulary for closed chiplets that ship no layer file),
``sg13g2.lyp``, ``sky130.lyp`` and ``interposer.lyp``. Any technology works:
drop its KLayout ``.lyp`` into ``pdks/`` or pass any path with ``--lyp-file``.

Step 3: curate the pads
------------------------

For real silicon this is the normal path, not an advanced fallback. Emit a
review GDS that contains only the pad-layer shapes, delete everything that is
not an external I/O pad in KLayout, and convert from the cleaned result:

.. code-block:: bash

    # 1. emit every pad-layer shape for review
    python3 gds_to_kicad.py die.gds --generate-pad-review review.gds \
        --lyp-file ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp \
        --layer TopMetal2.drawing

    # 2. delete every shape that is not an I/O pad, keeping each pad's name
    #    text on the text layer, and save
    klayout -e -l ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp review.gds

    # 3. build the footprint from the curated layout
    python3 gds_to_kicad.py --from-pad-review review.gds \
        --pin-list pins.json \
        --lyp-file ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp \
        --layer TopMetal2.drawing \
        -o die.kicad_mod

``--pin-list`` is required on the third command. It is the authoritative list
of names, and pads are matched to it by nearest neighbour, with a warning for
anything left unmatched. Repeat ``--lyp-file`` and ``--layer`` there too:
without them the pad layer is auto-detected against the default
``generic.lyp``, and the ``LYP_FILE`` and ``GDS_LAYER`` traceability
properties described below record that default instead of the technology you
actually curated against.

.. tip::
    Curate once and commit the result. In the reference design the full
    ``Metal_Test.gds`` exposes about 474 shapes on ``TopMetal2``, of which 58
    are I/O pads. The curated ``Metal_Test_stripped.gds`` is committed
    alongside the full die, which turns the footprint from a hand-made
    artefact into a one-shot reproducible conversion that the build can
    regenerate and diff.

Step 4: generate the footprint
-------------------------------

.. code-block:: bash

    python3 gds_to_kicad.py Metal_Test_stripped.gds \
        --lyp-file ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp \
        --layer TopMetal2.drawing --text-layer-number 134/25 \
        --flip-chip \
        -o metal_test_chiplet.kicad_mod

The converter reads the top cell, flattens it, pulls box and polygon shapes off
the pad layer and names each pad from the nearest text label. Rectangular pads
become ``smd rect``; anything else becomes ``smd custom`` carrying a
``gr_poly`` primitive, so the real pad shape survives into KiCad rather than
being approximated by a rectangle. A courtyard is drawn around the die outline,
which matters later: the design-time assembly spacing check is expressed as a
courtyard clearance.

``--flip-chip`` mirrors the X coordinates, producing the footprint as seen from
the interposer side. Use it for any die that mounts face down, which is every
die attached by Cu pillars or microbumps. It also stamps ``ORIENTATION`` as
``flip_chip``, and the export carries that through to the ``.chiplet``.

Instead of ``-o``, ``--design-dir DIR`` writes into ``DIR/<design>.pretty/``,
matching the project layout the rest of the flow expects.

Pad numbers are pad names
~~~~~~~~~~~~~~~~~~~~~~~~~

gds2kicad uses the pad name from the GDS text layer as the KiCad pad
*number*:

.. code-block:: text

    (pad "DIV_OUTn" smd custom ...)
    (pad "DIV_Vcc"  smd rect   ...)

KiCad matches schematic pins to footprint pads by pad number, so the symbol
emits the same string as its pin number. The consequence is that a net attaches
to the pad the silicon actually calls ``DIV_Vcc``, with no numbering table to
maintain in between, and a renamed pad in the layout shows up as a broken
connection rather than as a silently wrong one.

Step 5: generate the symbol
----------------------------

Straight from the GDS:

.. code-block:: bash

    python3 gds_to_kicad_symbol.py die.gds \
        --lyp-file ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp \
        --pad-layer TopMetal2.drawing -o die.kicad_sym

Pins are placed automatically, power at the top and bottom, signals left and
right. ``--symbol-name``, ``--footprint-ref`` and ``--max-text-distance`` (the
cutoff in database units for matching a text label to a pad) tune the result.

When the automatic arrangement needs fixing, use the two-step path. Dump an
editable pin list, correct it, and rebuild with no GDS involved:

.. code-block:: bash

    python3 gds_to_kicad_symbol.py die.gds --extract-pins pins.json
    # edit pins.json: names, sides, types
    python3 gds_to_kicad_symbol.py --from-pin-list pins.json -o die.kicad_sym

Each pin in that JSON carries a ``name``, a ``side`` (``left``, ``right``,
``top``, ``bottom``), a ``type`` (``passive``, ``input``, ``output``,
``bidirectional``, ``tri_state``, ``power_in``, ``power_out``,
``unspecified``) and its geometry in database units. The Pin List Editor tab
edits the same file. :doc:`/formats/07_pin_lists` is the schema reference.

Rebuilding from the pin list reproduces the full symbol layout, not just the
pin names, which is what makes the symbol a regenerable artefact rather than a
hand-drawn one.

A die with no GDS
-----------------

When all you have is a pad map from a datasheet, synthesise a stand-in:

.. code-block:: bash

    python3 blackbox_chiplet.py pads.json -o chiplet.gds

The specification is JSON or CSV, chosen by extension. CSV is a header of
``name,x_um,y_um,w_um,h_um`` with one pad per row; JSON adds an optional
explicit ``die`` size and a ``chiplet_name``. Pad ``x`` and ``y`` are centre
coordinates. Without an explicit die size the outline is taken from the pad
extents plus a margin.

Pads, labels and outline are stamped on the canonical generic layers
(``205/0``, ``205/25``, ``206/0``), so the output feeds the converters above
with no layer flags at all. Alongside the GDS the generator writes a
``<stem>.boundaries.json`` manifest carrying the die outline as the chiplet
boundary for the assembly DRC, which is what lets a black-boxed die be checked
for overlap and spacing exactly like a real one. Suppress the manifest with
``--no-manifest``, and see :doc:`/formats/04_boundary_manifest`.

Interposer I/O pads
-------------------

The pads at the interposer edge, where the assembly connects to the outside
world, are not derived from any die. Generate them parametrically:

.. code-block:: bash

    python3 io_pads/generate_io_pad.py --io-class wire_bond --size 100x100

The resulting footprint carries an ``IO_CLASS`` property (and its size), which
is what the export scans for when it extracts the assembly's I/O pads into the
``.chiplet``. The reference design uses 35 such pads, all
``wire_bond``, 100 by 100 um.

Traceability properties
-----------------------

The footprint records where it came from. These properties travel with the
footprint into the board and are read by the export:

.. list-table::
    :header-rows: 1
    :widths: 24 40 36

    * - Property
      - Example value
      - Meaning
    * - ``GDS_FILE``
      - ``../chiplets/Metal_Test.gds``
      - The die layout this footprint was generated from
    * - ``LYP_FILE``
      - ``${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp``
      - The layer-properties file used to resolve the layer name
    * - ``GDS_LAYER``
      - ``TopMetal2.drawing (134/0)``
      - The pad layer, by name and by number
    * - ``ORIENTATION``
      - ``flip_chip``
      - How the die mounts, set by ``--flip-chip``

Both path properties accept ``${VAR}`` references and board-relative paths.
Prefer them over absolute paths: a relative ``GDS_FILE`` such as
``../chiplets/Metal_Test.gds`` resolves against the board, so the project stays
portable and the export reads the die geometry from the project itself rather
than from wherever the tools happen to be installed.

Two further fields are set later, on the board rather than on the library
footprint, and are documented in :doc:`/flow/03_interposer_design`:
``CONNECTION`` (the attachment method for this die) and ``DIE_THICKNESS_UM``
(the physical z extent of the silicon body).

Checking the result
-------------------

Before moving to the board, confirm four things.

**The pad count is what you expect.** Open the footprint in the KiCad footprint
editor and count. If it is in the hundreds for a die with a few dozen I/O pads,
the pad layer selection picked up routing or fill, and step 3 was skipped.

**The pads are named, not numbered.** Pads called ``1``, ``2``, ``3`` mean the
text layer was never resolved. Re-run with an explicit ``--text-layer`` or
``--text-layer-number``.

**The geometry round-trips.** Pull the pin list back out of the footprint and
compare it against the one you built the symbol from:

.. code-block:: bash

    python3 footprint_to_pinlist.py die.kicad_mod -o roundtrip.pins.json

Names and geometry must match. ``side`` and ``type`` will not: a footprint has
no such semantics, so re-extraction defaults them. Compare only the fields a
footprint can carry.

**The symbol and the footprint agree.** Every symbol pin number must exist as a
footprint pad number. Because both are the pad name, a mismatch means the
symbol and the footprint were generated from different revisions of the die.

.. tip::
    Treat all of this as a build step rather than a one-off. The reference
    design regenerates its footprint from the committed stripped GDS, its
    symbol from the committed pin list and its I/O pad parametrically, then
    diffs each against the committed library on every image build. A die that
    changes shows up as a failing diff instead of as a mystery DRC violation
    three stages later.

Next
----

With a footprint, a symbol and a pin list in the project library, continue with
:doc:`/flow/03_interposer_design`.
