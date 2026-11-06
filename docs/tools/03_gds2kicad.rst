gds2kicad
=========

.. include:: /common.inc

``gds2kicad``, |gds2kicad-repo|, turns a die or chiplet GDSII into the KiCad
parts you need in order to design an interposer around it: a ``.kicad_mod``
footprint, a ``.kicad_sym`` symbol, an editable pin list, and the netlist that
flows back into the assembly format.

It is the first tool in the flow, and :doc:`/flow/02_die_to_kicad` walks through
using it on a real die.

The problem it solves
---------------------

KiCad cannot read GDS, so placing a die on an interposer in pcbnew requires a
footprint, and the only information that footprint needs is already sitting in
the die layout: where the bond pads are, how big they are, what shape they are,
and what they are called.

The usual fallback is to redraw the pads by hand from a datasheet and type pin
names in cell by cell: slow, error-prone in a way that only shows up after
fabrication, and redone every time the die layout changes.

``gds2kicad`` reads the pad geometry and the text labels straight out of the
layout, so the KiCad part matches the silicon by construction rather than by
transcription.

Installing
----------

There is nothing to build. Run the scripts from the clone root. You need
KLayout's Python module to read GDS, and PyQt6 for the GUIs:

.. code-block:: bash

    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt    # PyQt6, PyYAML
    pip install klayout

A system KLayout with its bindings on ``PYTHONPATH`` works too. In the container
none of this applies: run ``gds-to-kicad`` and the GUI opens.

The schematic tools and ``kicad_pcb_to_iopads.py`` import two readers that
ship vendored in the clone, so they need nothing else:
``_vendor/chiplet_format_io``, the ``.chiplet`` reader at release 1.21.0
(Apache-2.0, its text in ``LICENSES/Apache-2.0.txt``, inside this
GPL-3.0-or-later tool), and ``_vendor/round_trip_names.py``, interposer-pnr's
reader of its export report. An install from the clone's ``pyproject.toml``
carries both.

.. tip::
   Both converters can write themselves a small test GDS, which is the quickest
   way to check an install:

   .. code-block:: bash

       python3 gds_to_kicad.py --generate-test-gds
       python3 gds_to_kicad.py tests/test_footprint.gds -o demo.kicad_mod

   The result has three pads, numbered rather than named, because the fixture
   carries no text labels.

Telling it where the pads are
-----------------------------

There is no PDK baked in, no ``--pdk`` flag and no PDK discovery. You say
explicitly which layer holds the pads, in one of three ways, in this order of
precedence:

.. list-table::
    :header-rows: 1
    :widths: 10 44 46

    * - Order
      - How
      - Example
    * - 1
      - Raw GDS layer number, ignores the ``.lyp`` entirely
      - ``--pad-layer-number 134/0``
    * - 2
      - Layer name resolved through a KLayout ``.lyp``
      - ``--lyp-file pdks/sg13g2.lyp --layer TopMetal2.drawing``
    * - 3
      - Nothing, and the densest plausible pad layer is auto-detected
      - (no flags)

Pin names come from a separate text layer, selected the same way with
``--text-layer NAME`` or ``--text-layer-number N/D``, or auto-detected.

.. note::
   Two things reliably cost people time.

   The flag spelling differs between the two converters: ``gds_to_kicad.py``
   uses ``--layer``, ``gds_to_kicad_symbol.py`` uses ``--pad-layer``. The
   ``*-layer-number`` flags are spelled the same in both.

   More importantly, if you name the pad layer with ``--layer`` and say nothing
   about text, ``gds_to_kicad.py`` emits **numbered** pads instead of named
   ones, and it does so silently. Add ``--text-layer NAME``, or ``--auto-text``
   to let it find the text layer itself. The symbol tool does not have this
   problem because it derives ``TopMetal2.text`` from ``TopMetal2.drawing`` on
   its own, which is why it has no ``--auto-text`` flag. When both tools
   auto-detect the pad layer, both auto-detect the text layer too.

Auto-detection works on a clean chiplet GDS. On a full die it will happily
return routing, fill and guard rings as "pads". Inspect first:

.. code-block:: bash

    python3 gds_to_kicad.py die.gds --scan-layers
    python3 gds_to_kicad.py die.gds --list-layers --lyp-file pdks/sky130.lyp

The role of the ``.lyp``
~~~~~~~~~~~~~~~~~~~~~~~~

A KLayout layer-properties file is what maps a human-readable layer name onto a
GDS layer and datatype pair. ``gds2kicad`` uses it for nothing else: it does not
read design rules, it does not need a technology, and it does not care which
process the file describes. That is why any technology works, and why passing a
raw layer number bypasses the ``.lyp`` completely.

Four files ship under ``pdks/``:

.. list-table::
    :header-rows: 1
    :widths: 24 76

    * - File
      - Contents
    * - ``generic.lyp``
      - The default. A pads-only vocabulary: pad metal 205/0, pad text 205/25,
        outline 206/0. For closed chiplets that ship no layer file at all.
    * - ``sg13g2.lyp``
      - The full IHP SG13G2 layer set.
    * - ``sky130.lyp``
      - The full SkyWater sky130 layer set.
    * - ``interposer.lyp``
      - SG13G2 upper metals through Bump, for interposer work.

Drop any other technology's ``.lyp`` into ``pdks/``, or pass any path with
``--lyp-file``. IHP SG13G2 is what the tool is tested against most heavily, not
a requirement.

Die to footprint
----------------

.. code-block:: bash

    python3 gds_to_kicad.py die.gds --lyp-file pdks/sg13g2.lyp \
        --layer TopMetal2.drawing --text-layer TopMetal2.text \
        -o die.kicad_mod

The converter reads the top cell, flattens it, collects box and polygon shapes
from the pad layer, and names each pad from the nearest text label on the text
layer.

Pad extraction
~~~~~~~~~~~~~~

A rectangular pad becomes an ordinary ``smd rect`` pad. A non-rectangular pad
becomes an ``smd custom`` pad whose ``gr_poly`` primitive carries the real
vertices, expressed relative to the pad centre. This matters because octagonal
and chamfered pads are common on real silicon, and approximating them by their
bounding box would misreport the metal available for a bump landing.

Coordinates are converted GDS Y-up to KiCad Y-down by negating Y. Pad names are
sanitised before being written, because both the cell name and the text labels
come from a GDS file that the tool did not produce, and a stray quote or
parenthesis would corrupt the S-expression.

``--flip-chip`` mirrors X, so that a die mounting face-down on an interposer
reads as seen from the interposer side. It also changes the ``ORIENTATION``
property written into the footprint from ``face_up`` to ``flip_chip``, which is
the value the ``.chiplet`` exporter later keys its flip-chip handling on.

Traceability properties
~~~~~~~~~~~~~~~~~~~~~~~

Every generated footprint carries four properties recording where it came from:

.. list-table::
    :header-rows: 1
    :widths: 22 78

    * - Property
      - Value
    * - ``GDS_FILE``
      - Absolute path of the source GDS.
    * - ``LYP_FILE``
      - Absolute path of the layer-properties file used.
    * - ``GDS_LAYER``
      - The pad layer, as name and as number, for example
        ``TopMetal2.drawing (134/0)``.
    * - ``ORIENTATION``
      - ``face_up`` or ``flip_chip``.

These are not documentation. ``GDS_FILE`` is the field the KiCad fork's
HyperLynx exporter emits on the device record, and the field the chiplet
exporter reads to fill in a die's ``layout:`` entry. It is what lets the
downstream converter instantiate the real die layout instead of a placeholder
rectangle, without anyone typing a path into a board. ``ORIENTATION`` feeds the
flip-chip path in the same exporter. See :doc:`/tools/01_kicad_adk_mod`.

.. note::
   The generated courtyard (``F.CrtYd``) is a rectangle over the **pad bounding
   box**, not over the die outline. The chiplet exporter takes a component's
   width and height from the courtyard when one is present, so a die whose pads
   sit well inside its edge will export with dimensions smaller than the
   physical die. Draw the courtyard to the die outline in the footprint editor
   if the assembly dimensions matter, which they do for the assembly placement
   rules.

Die to symbol
-------------

.. code-block:: bash

    python3 gds_to_kicad_symbol.py die.gds --lyp-file pdks/sg13g2.lyp \
        --pad-layer TopMetal2.drawing -o die.kicad_sym

Same pad and text extraction, emitted as a KiCad 6 or later ``.kicad_sym``
library. Pins are placed automatically: pins whose names look like power or
ground go top and bottom, signals are distributed across the remaining sides so
the counts stay balanced. ``--symbol-name``, ``--footprint-ref`` and
``--max-text-distance`` (a DBU cutoff for matching a label to a pad) adjust the
result.

The pin list
------------

Automatic classification is a starting point, not an answer. The pin list is the
mechanism for correcting it, and it is the single source of truth for pin names,
types and sides in the human-in-the-loop workflow.

.. code-block:: bash

    python3 gds_to_kicad_symbol.py die.gds --extract-pins pins.json
    # edit pins.json
    python3 gds_to_kicad_symbol.py --from-pin-list pins.json -o die.kicad_sym

The rebuild step touches no GDS at all. Once a pin list exists it is the input,
which means a naming correction survives a re-extraction only if you keep the
file.

Each entry carries a ``name``, a ``side`` (``left``, ``right``, ``top``,
``bottom``), a ``type`` (``passive``, ``input``, ``output``, ``bidirectional``,
``tri_state``, ``power_in``, ``power_out``, ``unspecified``) and the pad
geometry in database units, including the polygon vertices when the pad is not
rectangular. The file carries metadata alongside the pins: a format version, the
chiplet name, the source GDS, the ``.lyp``, the pad layer, the text layers used
and a timestamp. Names such as ``<chiplet>_pins.json`` are the convention the
GUI and ``footprint_to_pinlist.py`` both default to.

The same file is what the Pin List Editor tab edits, what ``--pin-list``
expects in the pad-review workflow below, and what ``bump_mirror.py`` in the
interposer PDK consumes to place bumps. :doc:`/formats/07_pin_lists` documents
the format.

Going the other way, ``footprint_to_pinlist.py`` pulls pad geometry out of one
or more ``.kicad_mod`` files into a pin list, converting KiCad millimetres back
to database units.

Curating pads by hand
---------------------

This is the normal path for real silicon, not an advanced fallback.

A full die GDS is mostly routing, fill and guard rings, and no heuristic can
tell those from bond pads. The workflow is to reduce the GDS to the pad layer
plus labels, clean it up in KLayout where you can see what you are deleting, and
then build from the result:

.. code-block:: bash

    python3 gds_to_kicad.py die.gds --generate-pad-review review.gds
    klayout -e -l pdks/sg13g2.lyp review.gds
    # delete everything that is not a real pad, save
    python3 gds_to_kicad.py --from-pad-review review.gds \
        --pin-list pins.json -o die.kicad_mod

``--pin-list`` is required in the rebuild step. After a manual edit the shapes
in the file no longer correspond to the extraction that produced them, so the
pin list is the authoritative list of names; pads are matched to it by nearest
neighbour, and anything left unmatched is warned about rather than silently
numbered.

Database units
--------------

The converters do not assume a database unit. The scale factor comes from
``layout.dbu`` of the file actually being read, resolved once per conversion and
threaded through every coordinate conversion. ``--dbu`` overrides it for a file
whose header is wrong.

The DBU is not a constant across the ecosystem: IHP SG13G2 layouts are
conventionally 1 nm per unit, but a chiplet from another source may not be, and
the wrong factor produces a footprint off by a power of ten that still looks
plausible. When no layout is available the fallback is 1 DBU equals 1 nm, stated
explicitly in the code.

Black-box chiplets
------------------

``blackbox_chiplet.py`` handles the case where a chiplet comes from a commercial
or closed process and all you have is a pad map: names, centres and sizes, from
a datasheet. There is no layout and no layer file.

.. code-block:: bash

    python3 blackbox_chiplet.py pads.json -o chiplet.gds
    python3 blackbox_chiplet.py pads.csv  -o chiplet.gds --no-manifest

The input is JSON or CSV, chosen by extension. CSV is a header
``name,x_um,y_um,w_um,h_um`` with one pad per row. JSON adds an optional
explicit ``die`` size (as ``width_um``/``height_um`` or as ``bbox_um``) and a
``chiplet_name``. Pad ``x`` and ``y`` are **centre** coordinates. Without an
explicit die, the outline is derived from the pad extents plus a margin.

Pads, labels and outline are stamped on the ADK canonical generic layers, 205/0,
205/25 and 206/0, read from ``config/chiplet_pads.json`` under the discovered
ADK root with those values as a hardcoded fallback so the generator still runs
when the ADK is unreachable. Because those are exactly the layers
``generic.lyp`` describes, the output feeds the converters above with no layer
flags at all.

.. note::
   ``blackbox_chiplet.py`` is also a boundary-manifest producer. Alongside the
   GDS it writes a ``<stem>.boundaries.json`` carrying the die outline as the
   chiplet boundary, with schema ``adk-boundary-manifest`` version ``1.0.0``,
   the same contract ``hyp_to_gds.py`` emits for a full assembly. That is what
   allows the assembly DRC to check a standalone synthesised die, and it is why
   the boundary is metadata rather than a layer: a stand-in GDS has no
   fabrication layers to put it on. Suppress it with ``--no-manifest``. See
   :doc:`/formats/04_boundary_manifest`.

Interposer I/O pads
-------------------

``io_pads/`` holds the other end of the interposer: the pads that connect the
assembly to the outside world.

.. code-block:: bash

    python3 io_pads/generate_io_pad.py --io-class wire_bond --size 100x100
    python3 io_pads/kicad_pcb_to_iopads.py design.kicad_pcb -o io_pads.json

``generate_io_pad.py`` emits a parametric KiCad symbol and footprint tagged with
``IO_CLASS`` and ``IO_PAD_SIZE_UM`` properties. ``IO_CLASS`` is the field the
chiplet exporter uses to tell an interposer I/O pad from a chiplet die, so the
tag is what puts the pad under the interposer's ``io_pads`` rather than in the
component list. Only ``wire_bond`` is implemented; ``flipped_bump`` and
``tsv_bump`` are reserved names and are rejected.

After routing, ``kicad_pcb_to_iopads.py`` walks the board, keeps the footprints
carrying an ``IO_CLASS``, and writes their pad locations, sizes and nets to JSON,
converting millimetres to micrometres and negating Y for the GDS Y-up
convention. The export plugin performs the same extraction automatically; this
script is the standalone and override path.

Each entry's ``ref`` is the pad's io_pad id. On a board ``interposer-pnr
export`` drew, recognised by a carrier from the ``chiplet_carrier`` library or
one carrying ``IO_PAD_ID``, that is each carrier's hidden ``IO_PAD_ID``, and a
carrier without one, or two with the same one, is refused. On a board drawn by
hand it is the reference. A carrier's ``net`` is the one net all its pads
carry; a carrier on two nets, an unnetted pad counting as one, is refused.

The nets are written in the planner's names. A board export drew against a
sheet carries the sheet's names instead, so it needs the report export wrote
beside it:

.. code-block:: bash

    python3 io_pads/kicad_pcb_to_iopads.py draft.kicad_pcb \
        --export-report export.json -o io_pads.json

A routed net goes back to its planner name, a pad no routed net binds is
written with an empty net, and a net the report does not name is refused.
Without the report, a board whose carriers link sheet symbols is refused, exit
1, and nothing is written:

.. code-block:: text

    Error: draft.kicad_pcb: carrier pad J1 is linked to a sheet symbol, so this board's nets may be the sheet's; give the export report interposer-pnr export --report wrote for it (--export-report)

A report written for another board (other carrier references, or another
``IO_PAD_ID`` on one) is refused too, and so is a ``round_trip`` newer than
version 6. A board drawn against no sheet needs no report. The reading rules
are interposer-pnr's own, and the export plugin carries the same file, so both
write the same ids and nets for every board they accept; see
:ref:`chiplet_export_report`.

Board back to chiplet netlist
-----------------------------

.. code-block:: bash

    python3 kicad_netlist_to_chiplet.py design.net --yaml nets.yaml --csv nets.csv
    python3 kicad_netlist_to_chiplet.py design.net --inject board.chiplet --summary

Converts a KiCad S-expression netlist to YAML and/or CSV, or injects
a ``netlist:`` section directly into an existing ``.chiplet``. Nets are
classified as power, ground or signal by name. Footprints from the ``io_pads``
library, or any reference prefix passed with ``--external-ref-prefix``, are
flagged ``external: true``. At least one of ``--yaml``, ``--csv``, ``--inject``
or ``--summary`` is required.

System schematics
-----------------

Two tools carry a whole system, not a single die, between the ``.chiplet`` and
a KiCad schematic. ``chiplet_to_kicad_sch.py`` draws the system sheet, or a
handout for drawing one by hand. ``kicad_sch_to_connectivity.py`` reads an
edited sheet back as a connectivity form, which the ``.chiplet`` schematic
import turns into a revision of the system. This section covers drawing,
handouts and reading back. The generator can also draw co-simulation setup
sheets (``--setup``); those are not covered here.

Drawing the sheet from a ``.chiplet``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    python3 chiplet_to_kicad_sch.py --chiplet design.chiplet \
        --pins U1=u1_pins.json --pins U2=u2_pins.json \
        --out sys.kicad_sch --report schematic.json --check

The result is one KiCad 9 sheet. Each die is a symbol whose Reference is its
component id, with a pin per name in its pin list, and every connected pin
carries a global label with the exact net name. Terminals on no net get a
no-connect flag, except open pins that link dies, which are left bare so that
KiCad's list of unconnected pins is the list still to wire. Nets come only from
the ``.chiplet``: the sheet is a view of the description, not a second source
of it.

A die symbol names its footprint ``chiplet_dies:<top cell>``. A carrier, a
component that is not a die but lists ``io_pads`` (a wire-bond interposer, for
example), is drawn as its pads: one ``chiplet_system:EXT_PAD`` symbol per pad,
with Reference the pad id and Footprint ``chiplet_carrier:EXT_PAD_<n>um`` from
the pad's size in the ``.chiplet``. Those are the footprints
``interposer-pnr export`` draws, so a board it drew pairs with the sheet symbol
for symbol. The carrier's pin list is written next to the sheet as
``<id>.carrier_pins.json``. Reading the sheet back, with ``--check`` or with the
connectivity reader, folds a carrier's pads into one carrier whose pins are the
pad ids.

Each symbol carries a hidden ``CHIPLET_COMPONENT`` property with its component
id, title-block comment 1 holds the sha256 of the ``.chiplet``, and reruns on
the same inputs are byte-identical. Anything that cannot be drawn verbatim is
refused by name and no sheet is written. The report lists every refusal; among
them are a pin the component does not have, a pad whose netlist net and
``io_pads`` net disagree, a pad whose size is missing, not square or not a
whole number of micrometres, a pad id that is also a component id or another
pad's, and a die that states no top cell. ``--check`` exports the sheet's
netlist with ``kicad-cli`` and compares it with the ``.chiplet``. The exit
status is 0 when written, 3 when refused, and 4 when written but the check
found a difference or could not run.

**Names KiCad carries verbatim.** Die and carrier ids are plain
``[A-Za-z0-9_.+-]`` names. Pin and net names may also carry numeric subscripts
after a plain first character, as a die's bus pads are often named:
``IO[0].pad`` and ``a[1].b[2]`` are drawn as they are. A range such as
``B[0..3]``, which KiCad reads as a bus, a name that starts with a subscript,
which KiCad reads as stacked pins, and any other character are refused as
``unmappable_name``, with a message ending "KiCad would not carry it
verbatim".

Handouts for drawing a sheet by hand
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--handout DIR`` writes, instead of a sheet, what is needed to draw the
system from scratch:

.. code-block:: bash

    python3 chiplet_to_kicad_sch.py --chiplet given.chiplet \
        --pins U1=u1_pins.json --pins U2=u2_pins.json --handout sheet_first/

``DIR`` gets ``chiplet_dies.kicad_sym``, one symbol per top cell, named by it,
with Reference prefix ``U``, every pin passive and the link pins on the right;
a ``sym-lib-table`` naming that library ``chiplet_dies`` through
``${KIPRJMOD}``; and a project with an empty sheet, named after the
``.chiplet`` or ``--name``. Carriers are not drawn. No file carries a digest, a
time or a host path, so a rerun writes the same bytes.

A handout file already in ``DIR`` that differs from what would be written, a
sheet you have started drawing on for instance, is never overwritten: the run
is refused (``handout_exists``) and nothing is written. Move the file away for
a fresh handout. The exit status is 0 when written and 3 when refused, with the
refusals on stderr.

The same handout can be drawn from die folders, with no ``.chiplet``:

.. code-block:: bash

    python3 chiplet_to_kicad_sch.py --handout sheet_first/ \
        --dies sheet_first/dies/DRIVER --dies sheet_first/dies/ECHO \
        --ext-pad-um 80

Each die folder holds ``die-contract.json`` and the pad inventory it binds, and
lies inside the handout directory. A folder is read the way the schematic
import reads it, so a die that import would refuse is refused here rather than
drawn: a contract and an inventory that name different pads
(``contract_pads_differ``), a pad on no port (``unported_pads``), or a folder
that cannot be read as a die (``die_folder``). There is no system netlist, so
signal pins sit on the right and power and ground pins on the left. The
handout adds ``chiplet_system.kicad_sym`` with ``GND`` and ``SUPPLY``, drawn as
KiCad power symbols, and ``EXT_PAD`` for the external pads; the table names
``chiplet_system`` first. ``--ext-pad-um`` is the external pad's edge in whole
micrometres. The project is named by ``--name``, or by the directory's own
name.

A die whose repeated pad numbers all belong to one power or ground port gets
``duplicate_pin_numbers_are_jumpers`` on its symbol, because the die ties those
pads inside. Any other repeated number is refused as ``undeclared_tie``. KiCad
9.0 cannot read that flag, so such a handout opens only in the tools image's
KiCad (:doc:`/tools/01_kicad_adk_mod`). A handout drawn from a ``.chiplet``
never sets it, and a die with repeated rail pad numbers drawn that way is
refused later, at ``interposer-pnr export --form``. Draw such a die from its
folder.

Reading an edited sheet back
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Export the netlist and the ERC report with ``kicad-cli``, then read them:

.. code-block:: bash

    kicad-cli sch export netlist --format kicadsexpr --output sys.net sys.kicad_sch
    kicad-cli sch erc --format json --severity-all --output erc.json sys.kicad_sch
    python3 kicad_sch_to_connectivity.py sys.net sys.kicad_sch schematic.json \
        connectivity.json --erc erc.json

This is the form for a generated sheet, ``chiplet_system.connectivity`` 1.0:
each symbol with its ``CHIPLET_COMPONENT`` identity and pin numbers, each net
with its endpoints and whether KiCad made its name up, the base digest from the
title block, and every input by path and sha256. The reader reports what KiCad
resolved and judges nothing; that is the import's job. What the form cannot
carry is listed in it as a refusal: a hierarchical sheet, a net named by a
local label, two names on one net (from the ERC report), or a node on a pin its
symbol does not have. ``--no-erc`` skips the ERC report and with it the
two-name check. The exit status is 0 when the form is written, refusals
included, and 2 when an input is missing or is not what it claims to be.
Options may sit anywhere on the line, between the paths too.

A sheet drawn on a handout has no generator report. Say which handout it came
from instead:

.. code-block:: bash

    # handout from a .chiplet
    python3 kicad_sch_to_connectivity.py sys.net sys.kicad_sch connectivity.json \
        --blank --library sheet_first/chiplet_dies.kicad_sym --erc erc.json

    # handout from die folders
    python3 kicad_sch_to_connectivity.py sys.net sys.kicad_sch connectivity.json \
        --classic --library sheet_first/chiplet_dies.kicad_sym \
        --system-library sheet_first/chiplet_system.kicad_sym --erc erc.json

``--blank`` writes form 1.1 with ``sheet`` set to ``blank``: no base digest and
no generator report, the library by path and sha256, and each symbol's
``part`` (library nickname and symbol name) with a null identity, since the
designator is the only identity a blank sheet has. Two symbols under one
reference, two left unannotated for instance, are refused as
``duplicate_reference``.

``--classic`` writes form 1.3 with ``sheet`` set to ``classic``. It adds each
component's UUID key, its value, footprint and fields verbatim, explicitly
flagged no-connect pins as ``open``, each symbol's ``units`` and ``jumpers``
(its ``duplicate_pin_numbers_are_jumpers``), and ``rails`` from the
``chiplet_system:GND`` and ``chiplet_system:SUPPLY`` symbols on the root sheet.
The netlist's names and endpoints stay the connectivity authority. Refusals on
a classic sheet include a symbol with more than one unit (``multi_unit``), a
net-naming power symbol from another library (``foreign_rail``; a
``PWR_FLAG`` names no net and is ignored), a drawn rail that is no netlist net
(``rail_unused``), and two pins of one unit at one position with different
numbers (``unit_pin_order``). Only root-sheet symbols are written. A symbol
with no cached library symbol is an input error, exit 2.

The GUIs
--------

``unified_gui.py`` is the recommended entry point and drives the same engine as
the command line. It is a single window with five tabs, in workflow order:

1. **Extract Pins**, load a GDS and a ``.lyp``, optionally prepare a stripped
   pad-review GDS, extract the pin list.
2. **Pin List Editor**, review and correct names, types and sides.
3. **Symbol Designer**, generate the ``.kicad_sym`` with a live preview.
4. **Footprint Generator**, generate the ``.kicad_mod``.
5. **History**, a registry of past conversions.

.. figure:: /_figures/screenshots/gds2kicad-unified-gui-symbol-designer.png
    :align: center
    :width: 100%
    :alt: The unified GUI on its Symbol Designer tab, with the five-tab strip across the top, a pin configuration table on the left giving each pin a side and an electrical type, a live symbol preview on the right, and a log pane at the bottom.

    The Symbol Designer tab. The pin configuration table on the left is the pin
    list, one row per pad, with the side and the electrical type editable per
    pin; the preview on the right redraws as you change them, and *Export
    .kicad_sym* writes the library. The log records what the extraction found,
    here seven pads with seven names, and sends you to the Pin List Editor
    before anything is generated. That review step is the point: the tool
    proposes a classification, you confirm or correct it.

In the container this is what the ``gds-to-kicad`` command launches. On a
headless machine set ``QT_QPA_PLATFORM=offscreen``.

Where files are written
-----------------------

From the **command line**, generated files land in the current directory:
footprints under ``generated_kicad_footprint_files/``, symbols under
``generated_kicad_symbol_files/``.

.. list-table::
    :header-rows: 1
    :widths: 44 56

    * - To control it
      - Use
    * - An exact output path
      - ``-o FILE``
    * - The per-design ``<DIR>/<design>.pretty/`` convention
      - ``--design-dir DIR`` (footprint tool only)
    * - A different base directory
      - the ``GDS_TO_KICAD_DATA_DIR`` environment variable

Defaulting to the working directory is what makes the tools usable inside the
container: the install directory is read-only for the non-root user and no home
directory is mounted, so only the shared ``/work`` tree persists.

The **GUIs** behave differently. Every export goes through a save dialog that
opens in the directory the GUI was launched from. Only the conversion history
registry is written under ``generated_kicad_symbol_files/``.

One exception: ``io_pads/generate_io_pad.py`` writes back into the clone
(``io_pads/kicad_symbols/`` and ``io_pads/kicad_footprints/``) unless you pass
``--out-dir``.

.. tip::
   Every generated file is written atomically: the content goes to a sibling
   temporary file and is moved into place only once it is complete, so an
   interrupted or failing run leaves the previous artefact intact rather than a
   truncated one. Output is forced to UTF-8, and the file mode follows the
   umask rather than the owner-only default, which is what keeps generated
   files readable across the container's shared mount.

Troubleshooting
---------------

.. list-table::
    :header-rows: 1
    :widths: 42 58

    * - Symptom
      - Cause
    * - ``No module named klayout``
      - ``pip install klayout``, or put a system KLayout's bindings on
        ``PYTHONPATH``.
    * - Qt "xcb platform plugin" error on Linux
      - Missing Qt system libraries, or use ``QT_QPA_PLATFORM=offscreen``.
    * - Footprint pads come out numbered, not named
      - ``--layer`` was passed with no text layer. Add ``--auto-text`` or
        ``--text-layer``.
    * - Thousands of pads, huge output file
      - Auto-detection grabbed routing or fill. Use the pad-review workflow.
    * - ``pdks/...lyp`` not found
      - The examples use paths relative to the clone root. Run from there, or
        pass an absolute ``--lyp-file``.
