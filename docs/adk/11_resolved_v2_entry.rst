Resolved v2 entry
=================

.. include:: /common.inc

An assembly-lvs input is one **resolved** document that names every component
layout, where it sits, its terminals and the logical nets
(:doc:`/tools/09_assembly_lvs`). The ADK describes the same assembly in its own
files: an assembly GDS, a boundary manifest, a pillar manifest, a per-method
IXN sidecar and a ``.chiplet``. The resolved-v2 entry builds the ADK view from
the resolved document, so that both tools read one assembly and the binding
between them can be reproduced.

Two scripts under ``bridges/assembly_lvs/`` in |adk-repo| do the work.
``derive_attachment_sidecar.py`` writes an attachment sidecar from an accepted
``.chiplet`` and its pillar manifest. ``resolved_v2_entry.py`` reads one
``assembly-lvs.resolved/v2`` document together with that sidecar and writes the
ADK view into a fresh directory.

.. important::

    The entry is a nominal identity, frame and correspondence adapter. It runs
    no DRC and no LVS, invents no z, resolves no collision and certifies no
    process. Every entry manifest carries that scope statement: the entry does
    not prove clean DRC or LVS, uncertain-placement preservation, contact
    completeness or manufacturing qualification. Run the ADK DRC and
    :doc:`/adk/08_pads_vs_pillars` on its outputs; the manifest lists both
    commands.

Running it
----------

Derive the sidecar once from the accepted design, then run the entry:

.. code-block:: bash

    python3 bridges/assembly_lvs/derive_attachment_sidecar.py \
        --chiplet design/outputs/design.chiplet \
        --pillars design/outputs/design.pillars.json \
        --document reference/resolved.json \
        --dies-root design/chiplets \
        --out design.adk_attachment.json
    python3 bridges/assembly_lvs/resolved_v2_entry.py \
        --sidecar design.adk_attachment.json \
        --out build/entry

.. include:: /_image_adk_scripts.inc

.. literalinclude:: /adk/_usage/derive_attachment_sidecar.txt
   :language: text

.. literalinclude:: /adk/_usage/resolved_v2_entry.txt
   :language: text

Neither script replaces anything: the derive tool refuses a ``--out`` that
exists, and the entry refuses an output directory that exists. The entry needs
the ``klayout.db`` Python module.

Exit codes
~~~~~~~~~~

Both scripts share one table:

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - ``0``
      - Written. The entry prints the path of each output.
    * - ``1``
      - Usage error: the sidecar, the resolved document or the dies root is not
        where it is named, ``klayout.db`` is missing, or an adapter id is not
        registered.
    * - ``2``
      - Refused. The message names the key or input that failed. Nothing is
        left behind: the entry removes its output directory, and the derive
        tool publishes no sidecar. ``argparse`` also exits ``2`` for a command
        line it refuses.
    * - ``5``, ``6``, ``7``
      - An adapter registry problem, with the meanings
        :doc:`/adk/05_run_drc` gives them.

The attachment sidecar
----------------------

A resolved v2 document does not carry what the ADK view needs. The sidecar,
schema ``adk-resolved-attachment`` version 1.0.0, adds it: the interposer and
interconnect adapter ids (resolved through the ADK registry, see
:doc:`/adk/02_adapter_contract`), the five attachment layers of the carrier,
the attachment surface z, the carrier's thickness and z, and per die its
connection method, technology, thickness, declared dimensions, layout and top
cell. Its schema file is listed with the other sidecar schemas in
:doc:`/adk/09_registries`; the entry reads it with an exact version match.

``document`` and ``dies_root`` are paths relative to the sidecar's directory.
Every other path is a plain relative path inside its root, and a layout reached
through a symlink is refused.

``binds`` is an exact inventory by SHA-256: the resolved document, the layout
of every component it names, the ADK layout of every die, the methods manifest
and the interposer adapter deck. A stale digest, an extra entry or a missing
one is a refusal. Each input is parsed from the bytes that were hashed, and a
layout, which KLayout reads from a path, is hashed before and after it is read.
After the outputs exist, every bound input is hashed again, and an input that
changed during the run is a refusal that discards the outputs.

The derive tool copies the dies' dimensions from the ``.chiplet`` verbatim,
recomputes every die z from the methods manifest and refuses a ``.chiplet``
that disagrees, and checks the pillar manifest's ``methods`` against the same
manifest. It records the ``.chiplet`` as ``expect_chiplet``, so the entry
round-trips against it, and the identities of both inputs as ``derived_from``.
It validates its candidate with the entry's own loader before publishing, and
never replaces an existing file.

``interposer.attachment_layers`` names ``opening``, ``dfpad``, ``body``,
``body2`` and ``mark``. ``opening`` and ``dfpad`` must equal the pillar branch
of the ``chiplet_attachment_input`` line of the interposer adapter deck. The
entry parses that line as data; it never executes the deck.

The accepted subset
-------------------

The entry accepts a documented subset of valid v2, the profile
``nominal-identity-carrier/1.0.0``. Only ``schema_version``
``assembly-lvs.resolved/v2`` is read; v3 to v5 are refused. On top of the v2
semantics, each of these is a refusal:

- A carrier not placed at identity (``rotation_deg`` 0, ``mirror_x`` false).
- A non-empty ``contracts.internal_equivalences``.
- Any ``uncertainty.component_translation_um`` bound other than exactly 0.
- More than one terminal per die pin.
- A die whose terminals do not all use one dedicated die-contact conductor, or
  more than one interposer contact conductor across the interface contacts.
- A numeric string such as ``"50"``, a YAML integer written in hexadecimal,
  octal or sexagesimal, or a number with a leading zero such as ``012``.
- A coordinate or size outside plus or minus 1073741823 grid units.
- An ``assembly.id`` that is not one plain path component: 1 to 64 characters
  from ``[A-Za-z0-9_.-]``, starting with a letter or digit. It is the stem of
  every output name.

Everything else follows the assembly-lvs reader: duplicate keys are refused,
numbers are read as exact decimals from their text and aligned to
``technology.grid_um``, and every physical endpoint belongs to exactly one
logical net. Every layout in play must have a database unit equal to
``grid_um``; nothing is rescaled, and there is no tolerance argument. Widening
any of this is a new profile version.

Frames and placement
--------------------

The entry maps each die from its die-local GDS frame through the resolved
assembly frame into the ADK canonical frame, the interposer's GDS frame rebased
to the lower-left corner of its top-cell bounding box
(:doc:`/formats/03_coordinate_frames`). Both tools apply the mirror before the
rotation, so a resolved die at ``theta`` with ``mirror_x`` true becomes an ADK
die with ``rotation.z`` of ``theta + 180`` modulo 360 and ``orientation``
``flip_chip``; without the mirror it is ``theta`` and ``face_up``. Each emitted
die has ``anchor: gds_origin``, and its ``position`` is the image of its
die-local origin, never a copy of the resolved position. On every run the
entry reads the placed pad centres back through the instances of the assembled
GDS and checks them against the integer chain.

Attachment bodies and correspondence
------------------------------------

The carrier's attachment bodies are the merged ``opening`` and ``dfpad``
shapes. Each role shape of a body must be one polygon without holes, with a
square bounding box, an integer centre and point symmetry, and all roles must
share the same centres. The opening must lie strictly inside the dfpad and the
body, and the body strictly inside the dfpad. Per the die's connection method,
the bounding-box sizes must match the methods manifest exactly in database
units: the opening equals ``passiv_opening_um``, the dfpad equals
``passiv_opening_um`` plus twice ``tm2_enclosure_um``, and the body equals
``body_diameter_um``. The whole dfpad must be covered by one merged contact
conductor polygon.

These are predicates of the profile, not process rules. A failure means the
artwork differs from what the profile binds. They do not enforce a minimum
clearance: on concentric polygons whose bounding boxes meet the relation
exactly, the edge distance between dfpad and opening is slightly below the
manifest enclosure, because a polygon's apothem is shorter than its
circumradius. The entry computes that literal enclosure check and the literal
"dfpad strictly inside the conductor" test on every body and records both in
the manifest as data, never as a clearance.

For each die the entry then pairs, one to one, the document's terminals, the
die-contact proxies on the resolved die layout, the pads and labels of the ADK
die layout, and the openings and bodies on the carrier. A terminal must sit
strictly inside exactly one pad, carry a label equal to its pin, and land
exactly on one body centre. Every pad must lie strictly inside the die's single
206/0 outline, and every body on the carrier must host exactly one terminal.
The tables are written to the manifest per terminal.

Outputs
-------

The output directory must not exist. ``<id>`` is ``assembly.id``.

``<id>_assembled.gds``
    Top cell ``<id>``, holding a flattened, geometry-preserved copy of the
    resolved carrier top cell and one instance per die of the ADK die cell.
    The manifest proves the preservation per layer: shape and text counts,
    area, an empty merged XOR and an equal bounding box.

``<id>_assembled.boundaries.json``
    The boundary manifest (:doc:`/formats/04_boundary_manifest`), version
    1.0.0, with each die's 206/0 outline. A holed outline is refused.

``<id>_assembled.ixn_methods.json`` and ``<id>_assembled.pillars.json``
    The per-method IXN sidecar, version 1.0.0, and the pillar manifest, version
    1.1.0 with ``methods``. Pillars sit at the body centres found on the
    carrier, and none is marked as moved by auto-resolve.

``<id>.chiplet``
    The interposer with ``anchor: bbox_center``, its I/O pads in the canonical
    frame, and the dies placed as above. A die's z is the interposer's z plus
    the attachment surface z plus the heights of its connection stack, computed
    exactly. Die ``dimensions`` must equal the size of the die's 206/0 outline
    in database units, with no tolerance. With ``expect_chiplet`` set, the file
    is compared with the accepted ``.chiplet``: the component ids, each
    component's type, connection, orientation, anchor, technology, position
    and rotation, each die's top cell and size, and the connection stacks must
    agree. The carrier's top cell and size and the die thickness are recorded,
    not compared.

``entry_manifest.json``
    Schema ``adk-resolved-v2-entry`` version 1.0.0: every input and output
    digest, the frame constants, the preservation record, the body records,
    the correspondence tables, the z arithmetic, the adapter resolutions, the
    scope statement and the next commands to run.

``docs/resolved_v2_entry.md`` in |adk-repo| records the full profile, the
frame algebra and the test controls behind this page.
