Pin lists
=========

.. include:: /common.inc

A pin list is the ``*.pins.json`` artefact that carries a die's pad names and
pad centres. It originates in |gds2kicad-repo|, where it is the single source of
truth for pin names in the human-in-the-loop symbol and footprint workflow, and
two ADK tools consume it: the 3Dblox exporter uses it to emit bump maps, and the
pad-to-pillar alignment check uses it as a pad source.

.. warning::
   The pin list is **not formally specified**. There is no JSON Schema for it in
   ``config/schema/``, no version pin in any reader, and no validator beyond the
   handful of keys each consumer happens to need. What follows documents the
   shape as the producers write it and as the consumers read it, which is the
   only contract that exists today. Treat any field not listed under
   `What the ADK consumers read`_ as belonging to gds2kicad's own workflow.

Shape
-----

A pin list is a JSON object: a flat block of metadata, plus a ``pins`` array.

.. code-block:: json

    {
      "version": 1,
      "chiplet_name": "ACME_PHY",
      "source": "ACME_PHY.kicad_mod",
      "source_type": "kicad_footprint",
      "dbu_um": 0.001,
      "timestamp": "",
      "pins": [
        {
          "name": "VDD",
          "type": "power_in",
          "side": "top",
          "pad_index": 0,
          "center_x_dbu": -180000.0,
          "center_y_dbu": 240000.0,
          "width_dbu": 44000.0,
          "height_dbu": 44000.0
        }
      ]
    }

Metadata
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 16 60
   :class: adk-wide-table

   * - Field
     - Type
     - Meaning
   * - ``version``
     - integer
     - Pin list format version, currently ``1`` (``PIN_LIST_VERSION`` in
       ``pin_list.py``). No reader checks it.
   * - ``chiplet_name``
     - string
     - Cell or chiplet name the pins belong to.
   * - ``dbu_um``
     - number
     - Database unit in microns for the ``*_dbu`` fields. **Required by the ADK
       consumers.** See `The dbu_um caveat`_.
   * - ``gds_source`` / ``source``
     - string
     - The GDS or footprint the pins were extracted from. The two producers use
       different key names.
   * - ``source_type``
     - string
     - ``"kicad_footprint"`` from the footprint path. Absent on the GDS path.
   * - ``lyp_file``, ``pad_layer``, ``text_layers``
     - string, string, array
     - Extraction provenance, written by the GDS path only.
   * - ``timestamp``
     - string
     - ISO timestamp on the GDS path, empty string on the footprint path.

Pin entries
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 26 16 58
   :class: adk-wide-table

   * - Field
     - Type
     - Meaning
   * - ``name``
     - string
     - Pad name. Falls back to the one-based pad index when the extractor found
       no label.
   * - ``center_x_dbu``, ``center_y_dbu``
     - number
     - Pad centre in die-local database units, y-up. Multiply by ``dbu_um`` for
       microns.
   * - ``width_dbu``, ``height_dbu``
     - number
     - Pad bounding-box size in database units.
   * - ``pad_index``
     - integer
     - Index of the pad in the extraction order.
   * - ``type``
     - string
     - KiCad pin electrical type: one of ``passive``, ``input``, ``output``,
       ``bidirectional``, ``tri_state``, ``power_in``, ``power_out``,
       ``unspecified``. Used by the symbol generator only.
   * - ``side``
     - string
     - Symbol side: ``left``, ``right``, ``top`` or ``bottom``. Used by the
       symbol generator only.
   * - ``polygon_points_dbu``
     - array of ``[x, y]`` pairs
     - Optional exact pad contour, written by the GDS path when the pad is not a
       rectangle. Omitted otherwise. No ADK consumer reads it.

Coordinate frame
~~~~~~~~~~~~~~~~

Pin coordinates are **die-local**, y-up, relative to the die GDS origin, which is
the ``gds_origin`` anchor of the frame contract. Both ADK consumers reject a die
that declares ``bbox_center``, or no ``anchor`` at all, rather than silently
misplacing its pads by the bounding-box corner offset.

The coordinates are also **unmirrored**: they describe the die as drawn, not as
placed. Flip-chip handling belongs to the consumer, and each one applies it.

.. note::
   ``footprint_to_pinlist.py`` has to undo two transforms to get back to that
   frame. KiCad footprints are y-down, so it negates y; and when the footprint
   was generated with ``ORIENTATION=flip_chip``, gds2kicad had already mirrored
   x when writing it, so it mirrors x back. The result is the original die
   frame rather than a mixed die and footprint frame.

How pin lists are produced
--------------------------

From a die GDS
~~~~~~~~~~~~~~

.. code-block:: bash

    python3 gds_to_kicad_symbol.py die.gds \
        --lyp-file pdk.lyp --pad-layer TopMetal2.drawing \
        --extract-pins die.pins.json

Pads are extracted from the pad layer, names are paired to pad polygons by
proximity to text labels, and ``classify_pin`` assigns an initial symbol side
and type. The result is meant to be reviewed: names from a real die are often
wrong or missing, and the file is the place to fix them. The Pin List Editor tab
of ``unified_gui.py`` edits the same file.

For a full die, auto-detection on the raw GDS is usually not enough. Real
silicon is mostly routing, fill and guard rings, and the extractor cannot tell
those from bond pads. The normal path is to generate a pad-review GDS, delete
everything that is not a pad in KLayout, and build from the cleaned result with
the pin list supplying the authoritative names.

From a KiCad footprint
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    python3 footprint_to_pinlist.py die.kicad_mod -o die.pins.json

Parses the ``(pad ...)`` blocks of a ``.kicad_mod``, converts millimetres to
database units at ``--dbu`` (default ``0.001``), and applies the y and flip-chip
corrections described above. This is the path the ADK's own documentation points
at, and the one that produces a file the ADK consumers can read unmodified.

The dbu_um caveat
~~~~~~~~~~~~~~~~~

The two producers do not write the same metadata, and the difference matters.

``footprint_to_pinlist.py`` writes ``dbu_um``. The ``PinList`` writer behind
``--extract-pins`` and the GUI's save action does not: its metadata block is
``version``, ``chiplet_name``, ``gds_source``, ``lyp_file``, ``pad_layer``,
``text_layers`` and ``timestamp``.

Both ADK consumers go through ``chiplet2dbx.load_pinlist``, which requires
``dbu_um`` and raises otherwise:

.. code-block:: text

    ExportError: pin list <path> lacks dbu_um or a non-empty pins array

So a pin list extracted from a GDS needs the key added before the ADK can read
it. ``PinList.load`` preserves every metadata key it does not recognise and
``PinList.save`` writes it back, so adding ``"dbu_um": 0.001`` by hand survives
a later edit round trip through the editor.

.. tip::
   Take ``dbu_um`` from the die layout it was extracted from, not from a
   default. gds2kicad resolves the database unit per GDS, and a die drawn at
   0.005 um DBU with ``0.001`` recorded would place every bump 5 times too far
   from the die centre.

What the ADK consumers read
---------------------------

``chiplet2dbx.load_pinlist`` reduces the file to the three fields the ADK cares
about, and nothing else in the artefact is consulted:

.. code-block:: text

    load_pinlist(path) -> [{"name": str, "x_um": float, "y_um": float}, ...]

        name  <- pins[i].name
        x_um  <- pins[i].center_x_dbu * dbu_um
        y_um  <- pins[i].center_y_dbu * dbu_um

A pin missing any of the three keys, or carrying a non-numeric coordinate, is a
hard error naming the offending index. An empty ``pins`` array is a hard error
too: a pin list that resolves to no pads is a broken input, not a die with no
pads.

Consumer 1: bump maps for the 3Dblox export
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    python openroad/chiplet2dbx.py --chiplet design.chiplet \
        --out-dir build/3dblox \
        --pins U1=chiplets/die_a.pins.json \
        --pins U2=chiplets/die_b.pins.json

Supplying a pin list for a die turns its export bump-aware. The die's
``ChipletDef`` gains a ``.bmap`` bump map plus a per-method bump macro LEF
rendered by the interconnect PDK's generator, which is what activates the
``check_3dblox`` bump alignment check in OpenROAD. Without pin lists the export
is purely a black-box geometric view.

The transform into the def-local frame is a translation and, for flip-chip
dies, a mirror. The def-local frame is the outline rectangle
``(0, 0)..(width, height)`` with the die centre at ``(width/2, height/2)``:

.. code-block:: text

    x = width  / 2 + (-pin.x_um if flip_chip else pin.x_um)
    y = height / 2 +  pin.y_um

The mirror is applied here because this ecosystem realises a flip as a layout
mirror, while the target format's flipped orientation leaves bump x and y
unchanged.

Three behaviours are worth knowing before you feed a pin list in:

* **A pin outside the outline is fatal.** If any transformed pin falls outside
  ``0..width`` by ``0..height``, the export aborts and names up to five
  offenders. It means the pin list and the ``.chiplet`` ``dimensions`` disagree,
  which is a real error the exporter refuses to round away.
* **A pin list requires a connection method.** The bump map is keyed by method,
  so a die with pins but no ``connection:`` in the ``.chiplet`` is an error.
* **Pin lists split defs.** A bump map is a property of the ``ChipletDef``, not
  of the instance. Two dies that share artwork but differ in attachment method
  or net binding are emitted as separate defs, and two dies that would share a
  def but were given different pin lists are an error.

Pad names are sanitised to ``[A-Za-z0-9_]`` and de-duplicated with ``_2``,
``_3`` suffixes for the bump map. The ``port`` and ``net`` columns are filled
only when the ``.chiplet`` ``netlist:`` block binds that pad name to a net;
otherwise both are ``-``, because the target warns on a port with no net.

Consumer 2: pad positions for the alignment check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    python checks/pads_vs_pillars.py --chiplet design.chiplet \
        --pillars build/design_interposer.pillars.json \
        --pins U1=chiplets/die_a.pins.json

Here the pin list is the pad source: the positions the design *intends*, which
the check compares against the positions the producer *drew*, recorded in the
:doc:`/formats/05_pillar_manifest`. Die-local pads are mapped into the canonical
assembly frame through the die's placement,

.. code-block:: text

    global = position + R(rotation.z) * M * pad

with ``M = diag(-1, 1)`` for ``flip_chip`` dies and identity for ``face_up``,
then matched against that die's pillar entries by pin name, falling back to
nearest-unique matching when either side is unnamed.

``pads_vs_pillars.py`` accepts a second pad source that is not a pin list.
``--gds-pads REF`` extracts pad centres directly from the die's ``.chiplet``
layout GDS, using the ``pad_drawing`` and ``pad_text`` layers declared in
``config/chiplet_pads.json`` (``205/0`` and ``205/25``; the numbers are never
hardcoded in the tool). It yields the same in-memory
``{name, x_um, y_um}`` records, so the rest of the check is identical. Use it
for black-box or pads-only chiplets, where the die GDS already is the pad map;
use ``--pins`` when the names live in a reviewed pin list. A die given both is
an error.

.. tip::
   Pass a pad source for every die that declares a connection method. A die
   without one is silently unchecked, reported only as a warning. ``--strict``
   promotes that warning to a ``NO_PAD_SOURCE`` finding, which is what you want
   in CI.

See :doc:`/tools/03_gds2kicad` for the tools that produce pin lists,
:doc:`/adk/07_chiplet2dbx` for the 3Dblox export and
:doc:`/adk/08_pads_vs_pillars` for the alignment check.
