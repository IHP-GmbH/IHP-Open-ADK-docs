Pillar manifest
===============

.. include:: /common.inc

The pillar manifest is the sidecar file that records where the Cu-pillar and
bump producer **actually drew** each attachment element in an assembly GDS. It
is the alignment ground truth for manifest-level checks: a checker can compare
die pad positions against the as-drawn pillar centres without re-deriving bump
placement from the GDS artwork, and without repeating the producer's placement
logic.

The normative JSON Schema is ``config/schema/pillar_manifest.schema.json`` in
|adk-repo|.

File location
-------------

The manifest is written next to the assembly GDS it describes and named after
its stem, in the same producer pass that writes ``<stem>.boundaries.json``::

    board_complete.gds
    board_complete.boundaries.json
    board_complete.pillars.json

The file is written whenever the Cu-pillar and bump generation path is entered,
which means the producer had pad locations and at least one device resolved a
connection method, from its per-die override or from the assembly-global
connection type. A run that enters that path and ends with zero bumps still
writes the manifest with an empty ``pillars`` array. That distinction is
deliberate: "the bump path ran and drew nothing" and "the bump path never ran"
are different states, and only the first one writes a file.

Producers and consumers
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 12 34 54
   :class: adk-wide-table

   * - Role
     - Component
     - Notes
   * - Producer
     - ``hyp_to_gds.py`` (|plugin-repo|)
     - One entry per drawn pillar, after collision auto-resolve, rebased into
       the canonical frame and sorted by ``(device_ref, pin_name)``.
   * - Consumer
     - ``checks/pads_vs_pillars.py``
     - Validates schema, version, units and entry structure, then checks
       pad-to-pillar alignment.

Schema
------

Top level
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 10 14 54
   :class: adk-wide-table

   * - Field
     - Required
     - Type
     - Meaning
   * - ``schema``
     - yes
     - string
     - Literal ``"adk-pillar-manifest"``.
   * - ``version``
     - yes
     - string
     - Exact ``"1.0.0"``. The schema only types it as a string; the exact
       value is pinned by ``checks/pads_vs_pillars.py``. See
       `Version policy`_.
   * - ``units``
     - yes
     - string
     - Literal ``"um"``. ``x_um`` and ``y_um`` are a coordinate contract, so a
       different unit is rejected rather than converted.
   * - ``pillars``
     - yes
     - array
     - One entry per drawn pillar. May be empty.
   * - ``generator``
     - no
     - string
     - Producing tool, for provenance. The producer writes ``"hyp_to_gds.py"``.
   * - ``assembly_gds``
     - no
     - string
     - Basename of the assembly GDS this sidecar describes.

Pillar entries
~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 10 12 54
   :class: adk-wide-table

   * - Field
     - Required
     - Type
     - Meaning
   * - ``device_ref``
     - yes
     - non-empty string
     - KiCad reference of the die the pillar belongs to, for example ``U1``.
   * - ``pin_name``
     - yes
     - string
     - Pad or pin name. ``""`` when unknown.
   * - ``method``
     - yes
     - string
     - Interconnect method id, for example ``cupillar_opt1``.
   * - ``x_um``, ``y_um``
     - yes
     - number
     - Pillar **centre** in the canonical frame. See `Frame and semantics`_.
   * - ``diameter_um``
     - yes
     - number greater than zero
     - Bump body diameter for the method.
   * - ``moved_by_auto_resolve``
     - no
     - boolean
     - ``true`` when collision auto-resolve shifted this bump. The key is
       **omitted** when unknown, never written as a guess.
   * - ``auto_resolve_shift_um``
     - no
     - number, zero or greater
     - Distance the bump was shifted by auto-resolve. Present only on shifted
       bumps.

The schema file
~~~~~~~~~~~~~~~

``config/schema/pillar_manifest.schema.json``, validated against the shipped
manifests in CI so the committed schema cannot drift from the data.

.. literalinclude:: /../src/IHP-Open-ADK/config/schema/pillar_manifest.schema.json
    :language: json

Frame and semantics
-------------------

As drawn, not as requested
~~~~~~~~~~~~~~~~~~~~~~~~~~

``x_um`` and ``y_um`` are the centres the producer drew, **after** its collision
auto-resolve pass has run. If a bump was nudged to clear an obstruction, the
manifest carries the nudged position, not the nominal one derived from the pad
map.

The manifest is therefore authoritative for manifest-level checks. A consumer
must never re-derive pillar positions from pin lists or ``.chiplet`` placement
and prefer that derivation over the manifest. The assembly GDS remains the
fabrication ground truth; the manifest is a faithful record of what went into
it, at a granularity the GDS itself does not carry (the GDS has circles, not
named bumps attributed to a die and a method).

The canonical frame
~~~~~~~~~~~~~~~~~~~

The producer accumulates pillar records in its raw drawing frame, which is the
HYP coordinate space inherited from the KiCad board. The manifest writer rebases
every record by the interposer top-cell bounding-box lower-left corner before
writing, so the coordinates land in the **canonical GDS-bbox-corner frame**:
y-up, micrometres, origin at the lower-left of the interposer top cell.

That is the same frame ``.chiplet`` die positions and ``io_pads`` live in, which
is the entire point. The two sidecars compare directly, with no frame
conversion in the consumer:

.. code-block:: text

    checks/pads_vs_pillars.py, die-local pad -> canonical frame:

        global = position + R(rotation.z) * M * pad

    with M = diag(-1, 1) for flip_chip and identity for face_up.

The rebase origin is captured once, at the first manifest write, which is the
interposer GDS write before chiplet instances are merged in. The later
complete-GDS manifest reuses the same origin, so both sidecars share one frame
rather than each picking up the bounding box of whatever happened to be in the
layout at the time.

.. note::
   The boundary manifest is **not** rebased: its ``polygon_dbu`` is the placed
   contour in the assembly GDS coordinate system, which is what a KLayout deck
   needs. The pillar manifest is rebased, because its consumer compares against
   ``.chiplet`` positions rather than against layout geometry. The two sidecars
   sit next to each other and are in different frames on purpose. See
   :doc:`/formats/03_coordinate_frames`.

Auto-resolve bookkeeping
~~~~~~~~~~~~~~~~~~~~~~~~

``moved_by_auto_resolve`` marks a bump the collision auto-resolver shifted.
``auto_resolve_shift_um`` records how far, and it is frame-invariant: it is a
distance, so the writer's rebase leaves it untouched.

The pair exists because a shifted bump legitimately does not sit on its pad, and
the magnitude is what bounds the excuse: with only the boolean, the check would
have to excuse *any* deviation on a flagged bump.

``checks/pads_vs_pillars.py`` therefore treats the two fields differently:

* ``moved_by_auto_resolve: true`` **with** an ``auto_resolve_shift_um``
  magnitude: a named pair beyond tolerance demotes to a warning as long as the
  deviation stays within shift plus tolerance. Beyond that the flag cannot
  explain the distance and the finding stands as ``MISALIGNED``.
* A bare ``moved_by_auto_resolve`` boolean with no magnitude does **not**
  demote. It is advisory only.

The ADK producer always records the magnitude alongside the flag, so real
manifests are unaffected by the second rule. It closes the gap for foreign or
hand-edited manifests.

.. tip::
   Because the key is omitted rather than written ``false`` when the producer
   does not know, absence of ``moved_by_auto_resolve`` means "no information",
   not "not moved". Do not infer a clean placement from a missing key.

Version policy
--------------

Readers pin the version with an **exact string match** against ``"1.0.0"``. Any
other value, a missing field included, is a hard error, never a warning. This
mirrors the boundary manifest policy and for the same reason: a stale manifest
silently reinterpreted under new semantics could pass an assembly whose pillars
no longer sit where the checker believes they do.

``load_pillar_manifest`` validates, in order, that the file exists, parses as a
JSON object, carries the schema string, carries the exact version, declares
``units: "um"``, and that ``pillars`` is a list whose entries have string
``device_ref`` (non-empty), ``pin_name`` and ``method``, finite numeric
``x_um``, ``y_um`` and ``diameter_um`` with ``diameter_um`` greater than zero,
a boolean ``moved_by_auto_resolve`` when present, and a finite non-negative
``auto_resolve_shift_um`` when present.

.. note::
   The finiteness checks are not pedantry. ``NaN`` in a coordinate would make
   every distance comparison fail open, because ``dist > tol`` is false for
   ``NaN``. Rejecting it at read time keeps a corrupted manifest from turning
   the check green.

When the schema changes, bump the version in the producer and the reader in the
same change set:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30
   :class: adk-wide-table

   * - Repository
     - File
     - Symbol
   * - Chiplets-KiCad-Plugin
     - ``hyp_to_gds.py``
     - ``PILLAR_MANIFEST_VERSION``
   * - IHP-Open-ADK
     - ``checks/pads_vs_pillars.py``
     - ``SUPPORTED_PILLAR_MANIFEST_VERSION``

Example
-------

.. code-block:: json

    {
      "schema": "adk-pillar-manifest",
      "version": "1.0.0",
      "generator": "hyp_to_gds.py",
      "assembly_gds": "board_complete.gds",
      "units": "um",
      "pillars": [
        {
          "device_ref": "U1",
          "pin_name": "VDD",
          "method": "cupillar_opt1",
          "x_um": 1210.5,
          "y_um": 806.25,
          "diameter_um": 44,
          "moved_by_auto_resolve": true,
          "auto_resolve_shift_um": 12.0
        },
        {
          "device_ref": "U1",
          "pin_name": "",
          "method": "cupillar_opt1",
          "x_um": 1290.5,
          "y_um": 806.25,
          "diameter_um": 44,
          "moved_by_auto_resolve": false
        }
      ]
    }

Using it
--------

The manifest is consumed by the pad-to-pillar alignment check:

.. code-block:: bash

    python checks/pads_vs_pillars.py \
        --chiplet demo.chiplet \
        --pillars build/demo_interposer.pillars.json \
        --pins U1=chiplets/die_a.pins.json \
        --gds-pads U2

.. tip::
   Point ``--pillars`` at the sidecar of the GDS whose bumps you want to check.
   The interposer GDS and the complete GDS each get their own manifest, and both
   are written in the same frame, so either can be checked against the same
   ``.chiplet``.

See :doc:`/adk/08_pads_vs_pillars` for the check itself: pad sources, the
matching algorithm, the finding taxonomy and the exit codes.
