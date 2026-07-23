Boundary manifest
=================

.. include:: /common.inc

The boundary manifest is the sidecar file that carries the mechanical
boundaries of the placed chiplets for an assembly GDS. It is the single source
of truth for the ADK assembly DRC and for the boundary viewer.

The boundary lives in **no fabrication-layer namespace**. It is not a GDS layer,
not a datatype, and not a cell name convention: it is a JSON file written next
to the GDS. That is the whole point of the format, and the reason it exists is
explained in `Why the boundary left the fabrication layer namespace`_.

The normative JSON Schema is ``config/schema/boundary_manifest.schema.json`` in
|adk-repo|. This page explains that schema, and records where the runtime
contract is narrower or looser than the schema text.

File location and auto-discovery
--------------------------------

The manifest is written next to the GDS it describes and named after its stem::

    board_complete.gds
    board_complete.boundaries.json

Every reader auto-discovers the sidecar by that rule. ``run_drc.py`` derives
``<layout-stem>.boundaries.json`` from ``--path`` when ``--manifest`` is
omitted, and ``boundaries_to_rdb.py`` applies the same rule (in its own
``find_sidecar`` helper, kept independent so the KLayout macro does not import
the runner's module tree). An explicit path always wins:

.. code-block:: bash

    # auto-discovery
    python klayout/drc/run_drc.py --path board_complete.gds \
        --interposer-adapter intm4tm2

    # explicit sidecar
    python klayout/drc/run_drc.py --path board_complete.gds \
        --interposer-adapter intm4tm2 \
        --manifest /elsewhere/board_complete.boundaries.json

A missing manifest is a hard error, not a warning. The runner refuses to check
an assembly with no boundary source, because such a run would pass vacuously:
the ASM rules operate on the ``chiplet_boundary`` layer, and an empty layer
produces no violations.

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
     - One entry per placed chiplet. Always writes the file, even with zero
       boundaries. Appends ``assembly_gds_sha256``.
   * - Producer
     - ``blackbox_chiplet.py`` (|gds2kicad-repo|)
     - One entry: the mechanical outline of a standalone die, in die-local DBU
       with an identity transform.
   * - Consumer
     - ``klayout/drc/run_drc.py``
     - Validates schema, version and structure before the deck runs.
   * - Consumer
     - ``klayout/drc/adk_assembly.drc``
     - Parses the JSON blind and injects it as the Ruby local
       ``boundary_manifest``; relies on the runner's pre-validation.
   * - Consumer
     - ``klayout/drc/rule_decks/layers_def.drc``
     - Builds the ``chiplet_boundary`` polygon layer from ``polygon_dbu``.
   * - Consumer
     - ``klayout/drc/rule_decks/8_2_interconnect.drc``
     - Resolves the die instance names of the interconnect methods manifest
       against ``boundaries[].instance``.
   * - Consumer
     - ``klayout/macros/boundaries_to_rdb.py``
     - The viewer half of the contract. Renders the same manifest as a
       ``.lyrdb`` for the KLayout Marker Browser.

The viewer and the checker read the same file, so what you see in the Marker
Browser is exactly what the DRC injected. Nothing is written into the GDS to
make that work.

.. note::
   ``hyp_to_gds.py`` has an opt-in ``--annotate-boundaries`` flag that paints
   the boundaries onto a viewer-only annotation layer (default 1000/0, well
   outside the IHP SG13G2 fabrication range). No DRC rule reads that layer and
   it is not part of the assembly contract. It exists for eyeballing a layout,
   not for checking one.

Schema
------

Top level
~~~~~~~~~

The schema requires only ``schema``, ``version`` and ``boundaries``. Everything
else is optional, which means "no consumer fails when it is absent", not "no
producer writes it": both producers always emit ``generator``,
``assembly_gds``, ``dbu_um`` and ``top_cell``.

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
     - Literal ``"adk-boundary-manifest"``.
   * - ``version``
     - yes
     - string
     - Exact ``"1.0.0"``. The schema only types it as a string; the exact
       value is pinned by the readers. See `Version policy`_.
   * - ``boundaries``
     - yes
     - array
     - One entry per placed chiplet. May be empty.
   * - ``generator``
     - no
     - string
     - Producing tool, for provenance.
   * - ``assembly_gds``
     - no
     - string
     - Basename of the GDS this sidecar describes.
   * - ``assembly_gds_sha256``
     - no
     - string
     - Hash of the GDS at write time. A staleness hint only; no consumer
       verifies it.
   * - ``dbu_um``
     - no
     - number
     - Database unit in microns, typically ``0.001``. Reader default ``0.001``.
   * - ``top_cell``
     - no
     - string
     - Top cell the boundaries are placed in. Viewer default ``"TOP"``.

Boundary entries
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 10 14 54
   :class: adk-wide-table

   * - Field
     - Required
     - Type
     - Meaning
   * - ``polygon_dbu``
     - yes
     - array of at least three ``[x, y]`` integer pairs
     - Placed, transformed boundary contour in integer database units.
       **Authoritative** for the DRC.
   * - ``instance``
     - no
     - string
     - Placed-instance name, for example ``U1``. Used as the viewer label and
       as the die identity the interconnect methods manifest resolves against.
   * - ``source_die``
     - no
     - string
     - Die or library the instance came from.
   * - ``class``
     - no
     - string
     - ``"chiplet"``. Reserved for future classes.
   * - ``polygon_um``
     - no
     - array of at least three ``[x, y]`` number pairs
     - The same contour in microns, for humans and non-DRC tools.
   * - ``transform``
     - no
     - object
     - Placement provenance: ``origin_um``, ``rotation_deg``, ``mirror_x``,
       ``magnification``.
   * - ``kgd``
     - no
     - boolean or null
     - Declared by the schema, written and read by nobody. See
       `Vestigial fields`_.
   * - ``bbox_dbu``
     - no
     - array of four integers
     - Declared by the schema, written and read by nobody. See
       `Vestigial fields`_.

Which fields are authoritative
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``polygon_dbu`` is the geometry. It is the only per-entry field the schema
requires, and the only one the rule deck reads: ``layers_def.drc`` builds the
``chiplet_boundary`` layer from it unconditionally.

``polygon_um`` and ``transform`` are provenance. They record how the producer
got to the contour, they are convenient when reading the file by hand, and they
must never be used in a check. The viewer makes the rule visible: it renders
markers from ``polygon_dbu * dbu_um`` precisely so that the picture is the
checked geometry, and falls back to ``polygon_um`` only when ``polygon_dbu`` is
absent.

``instance``, ``source_die`` and ``class`` are identity. The viewer labels each
marker ``instance``, else ``source_die``, else ``boundary_<index>``. The
interconnect axis is stricter: when a per-method manifest is loaded,
``8_2_interconnect.drc`` raises if any die id it references is not among the
manifest's ``instance`` values, rather than silently dropping that chiplet's
pads out of its method region.

Vestigial fields
~~~~~~~~~~~~~~~~

The schema declares ``kgd`` and ``bbox_dbu`` on each boundary entry. No
producer writes them and no consumer reads them. Treat them as reserved: valid
if present, ignored either way. Before relying on either, wire it into a
producer and a reader, or drop it from the schema.

No z coordinate: single tier by design
--------------------------------------

Boundaries are two-dimensional placement polygons. The schema has no z, no tier
and no height field, and ``transform.origin_um`` is exactly ``[x, y]``. Every
consumer, the ASM rules included, therefore treats all chiplets as sitting on
one attachment plane.

This is a deliberate scope limit, not an oversight. Adding a z or tier field is
a version-bump event and has to land together with tier-aware consumers, since
a manifest that carried a z which the deck ignored would report overlaps
between chiplets that are stacked rather than colliding.

.. tip::
   :doc:`/adk/03_asm_rules` for what the single-plane assumption means for the
   overlap and spacing rules, and :doc:`/formats/03_coordinate_frames` for the
   frame the polygons live in.

The schema file
~~~~~~~~~~~~~~~

``config/schema/boundary_manifest.schema.json``, validated against the
shipped manifests in CI so the committed schema cannot drift from the data.

.. literalinclude:: /../src/IHP-Open-ADK/config/schema/boundary_manifest.schema.json
    :language: json

Version policy
--------------

Readers pin the version with an **exact string match** against ``"1.0.0"``. Any
other value, a missing field included, is a hard error, never a warning.

The reasoning is that the sidecar is trusted. The DRC does not re-derive
boundaries from the layout; it injects whatever the manifest says. A stale
manifest silently reinterpreted under new semantics could therefore pass an
assembly that should fail, which is the one failure mode a checker must not
have.

The runner validates in this order, and exits on the first failure:

#. the file exists (auto-discovered or explicit),
#. it parses as JSON and is an object,
#. ``schema`` equals ``"adk-boundary-manifest"``,
#. ``version`` equals the runner's ``SUPPORTED_MANIFEST_VERSION``,
#. ``boundaries`` is a list and every entry carries a ``polygon_dbu`` of at
   least three ``[x, y]`` pairs.

The last step exists because the deck reads ``polygon_dbu`` blind, so a
structurally malformed sidecar has to be caught by the runner rather than
surfacing as a Ruby backtrace from inside KLayout.

When the schema changes, bump the version in both producers and both reader
constants in one change set:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30
   :class: adk-wide-table

   * - Repository
     - File
     - Symbol
   * - Chiplets-KiCad-Plugin
     - ``hyp_to_gds.py``
     - ``_write_boundary_manifest``
   * - gds2kicad
     - ``blackbox_chiplet.py``
     - ``_write_blackbox_manifest``
   * - IHP-Open-ADK
     - ``klayout/drc/run_drc.py``
     - ``SUPPORTED_MANIFEST_VERSION``
   * - IHP-Open-ADK
     - ``klayout/macros/boundaries_to_rdb.py``
     - ``SUPPORTED_MANIFEST_VERSION``

The two reader constants are intentionally separate copies: the viewer macro
runs inside KLayout and deliberately does not import the runner's module tree.
A test pins the two equal, and the producer test suites pin their writers to
the same string.

Why the boundary left the fabrication layer namespace
-----------------------------------------------------

The boundary used to be a fabrication layer. It was called ``exchange0`` and it
was bound to GDS ``190/0``.

``190/0`` is IHP SG13G2's ``Exchange0``, a layer the process actually uses.
Binding the boundary to it had two consequences that got worse as the ADK
generalised.

The first is an abstraction leak. The ADK sits above all PDKs: an assembly can
combine dies from processes that have never heard of SG13G2, checked against an
interposer selected by an adapter. Pinning that cross-PDK contract to one
foundry's layer number made the assembly format depend on a detail of one
process. A chiplet from another node has no reason to know what ``190`` means,
and a second interposer technology would have had no principled way to answer
"which number is the boundary here".

The second is aliasing. If the boundary is a fabrication layer, then any
chiplet whose own geometry happens to use that layer, legitimately or by
accident, contributes shapes to the boundary layer of the merged assembly.
The DRC cannot tell the difference: it sees polygons on the boundary layer and
checks them as boundaries. That failure is silent and it is in the direction
that matters, because extra or wrong boundary geometry changes the verdict of
the placement rules.

Moving the boundary into a per-assembly manifest removes both problems by
construction. A JSON sidecar has no layer number to collide with, so it cannot
alias a PDK layer or a chiplet's internal geometry, and it is PDK-agnostic
because it is not expressed in any PDK's vocabulary at all.

.. note::
   The manifest is not the only place the assembly contract left the fab
   namespace. The black-box pad vocabulary in ``config/chiplet_pads.json``
   (``205/0``, ``205/25``, ``206/0``) is deliberately placed in a band the
   reference interposer PDK leaves free, and the optional boundary annotation
   layer sits at ``1000/0``. Same reasoning, applied where a synthetic layer is
   genuinely needed.

The legacy path
~~~~~~~~~~~~~~~

``config/layers.json`` still records the ``exchange0`` entry, marked legacy in
its own description. It has exactly one reader: ``layers_def.drc``, and only
when the deck runs with ``legacy_exchange0`` set, which only
``run_drc.py --legacy-exchange0`` sets:

.. code-block:: ruby

    if defined?(legacy_exchange0) && legacy_exchange0
      exchange0_layer  = adk_layers['exchange0']
      chiplet_boundary = polygons(exchange0_layer['gds_layer'],
                                  exchange0_layer['gds_datatype'])
    else
      chiplet_boundary = polygon_layer
      # ... insert polygon_dbu from the injected boundary_manifest
    end

Nothing in the ecosystem emits ``190/0`` any more. The flag exists so that a
GDS produced before the migration can still be checked, and for nothing else.
In that mode ``--manifest`` is ignored with a warning, and
``--interconnect-methods`` is rejected outright: per-method scoping resolves
die instance names against the manifest, and legacy mode has no instance names
to resolve.

Example
-------

.. code-block:: json

    {
      "schema": "adk-boundary-manifest",
      "version": "1.0.0",
      "generator": "hyp_to_gds.py",
      "assembly_gds": "board_complete.gds",
      "dbu_um": 0.001,
      "top_cell": "INTERPOSER",
      "boundaries": [
        {
          "instance": "U1",
          "source_die": "ACME_PHY",
          "class": "chiplet",
          "transform": {
            "origin_um": [1200.0, 800.0],
            "rotation_deg": 0.0,
            "mirror_x": true,
            "magnification": 1.0
          },
          "polygon_dbu": [[1100000, 725000], [1300000, 725000],
                          [1300000, 875000], [1100000, 875000]],
          "polygon_um": [[1100.0, 725.0], [1300.0, 725.0],
                         [1300.0, 875.0], [1100.0, 875.0]]
        }
      ],
      "assembly_gds_sha256": "9f2c..."
    }

.. tip::
   :doc:`/adk/05_run_drc` for the runner, :doc:`/adk/03_asm_rules` for the rules
   that consume ``chiplet_boundary``, and :doc:`/formats/06_ixn_methods` for the
   sidecar that resolves die instances against this one.
