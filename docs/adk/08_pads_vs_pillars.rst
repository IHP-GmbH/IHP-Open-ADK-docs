Pad to pillar alignment
=======================

A die's pads have to land on the Cu pillars or bumps actually drawn on the
interposer. Nothing in the geometric DRC deck checks that: it sees polygons on
fab layers and chiplet boundaries from a manifest, not the correspondence
between a die's pad named ``VDD`` and the pillar that is supposed to carry it.

The gap matters because the drawn pillar positions are not simply the pad
positions transformed by the placement. The producer that generates the
pillars runs a collision auto-resolver, which may shift individual bumps to
clear neighbouring geometry. A pillar that has moved far enough is an open
circuit that looks perfectly clean in every geometric check.

``checks/pads_vs_pillars.py`` closes that gap. It is a manifest-level check: it
transforms each die's pad centres through that die's ``.chiplet`` placement,
and compares the result against the as-drawn pillar centres recorded in the
assembly's pillar manifest.

.. note::

    The manifest's ``x_um`` / ``y_um`` are authoritative for this check: they
    are what the producer drew, after auto-resolve. The assembly GDS remains the
    fabrication ground truth. A consumer must never prefer a re-derived pillar
    position over the manifest. See :doc:`/formats/05_pillar_manifest`.

Inputs
------

.. list-table::
    :header-rows: 1
    :widths: 24 76
    :class: adk-wide-table

    * - Flag
      - Input
    * - ``--chiplet``
      - The finalised ``.chiplet``, which supplies the die placements
        (``position``, ``rotation.z``, ``orientation``, ``anchor``).
    * - ``--pillars``
      - The pillar manifest ``<gds-stem>.pillars.json``, written next to the
        assembly GDS by ``hyp_to_gds`` whenever the Cu-pillar or bump path
        runs.
    * - ``--pins REF=PINS_JSON``
      - A pad source for one die: a ``gds_to_kicad`` ``*.pins.json`` pin list,
        die-local and unmirrored. Repeatable. See
        :doc:`/formats/07_pin_lists`.
    * - ``--gds-pads REF``
      - A pad source for one die, extracted from that die's ``.chiplet``
        ``layout`` GDS. Repeatable. Requires the ``klayout.db`` Python module.

Each die takes at most one pad source; supplying both for the same reference
is a usage error, as is repeating either flag for one reference.

The manifest is validated after the ``.chiplet`` is loaded, and before any pad
source is read or any matching runs. ``schema`` must be
``adk-pillar-manifest`` and ``version`` must be exactly ``1.0.0``: an exact
string match, never a range. ``units`` must be ``um``, every coordinate must be
a finite number, and ``diameter_um`` must be positive. Non-finite coordinates
are rejected at read time on purpose, because a comparison against ``NaN`` is
false and would make every distance check pass.

Extracting pads from a GDS
~~~~~~~~~~~~~~~~~~~~~~~~~~

With ``--gds-pads`` the pads are the merged ``pad_drawing`` polygons of the
die's layout, one pad per merged polygon, each centre being the polygon's
bounding-box centre in micrometres relative to the GDS origin. Names come from
``pad_text`` labels: a label contained in the pad polygon wins, the nearest one
when several are contained, and the nearest label overall otherwise. A die with
no labels yields unnamed pads, which is legal and shifts the matching to the
fallback strategy.

Layer numbers are read from ``config/chiplet_pads.json`` and are never
hardcoded. A die that carries no polygons on the ``pad_drawing`` layer is an
error telling you to supply ``--pins`` instead: it is probably not a black-box
pads-only chiplet.

The ``layout`` path is resolved the same way every ADK reader resolves paths.
``${VAR}`` ecosystem-root references expand through the environment first and
then a sibling-checkout walk, and relative paths resolve against the
``.chiplet`` file's own directory.

The transform
-------------

Pad coordinates are die-local GDS micrometres, y-up, relative to the die GDS
origin. The die's ``.chiplet`` ``position`` is where that origin lands in the
canonical interposer GDS-bbox-corner frame, which is the same frame the pillar
manifest coordinates live in. Each pad ``p`` therefore maps to:

.. math::

    \mathrm{global} = \mathrm{position} + R(\mathrm{rotation.z}) \cdot M \cdot p

with ``R`` a counter-clockwise rotation in that y-up frame and
``M = diag(-1, 1)`` for a ``flip_chip`` die, identity for ``face_up``.

Three details of that composition are easy to get wrong:

- The mirror is applied **before** the rotation. The assembly generator places
  a flipped die as ``translate * R(rotation.z) * mirror-x``, and the pillar
  producer consumes footprint-frame pin lists that already carry the same
  mirror. This check reproduces that order.
- Arbitrary rotation angles are supported here, unlike the 3Dblox export which
  is restricted to quarter turns by its target format.
- ``face_down`` is a hard error. It is not a canonical orientation token, so
  there is no mirror convention to apply; use ``flip_chip``. This is the same
  policy as :doc:`/adk/07_chiplet2dbx`.

Dies must declare ``anchor: gds_origin``. Both ``bbox_center`` and an absent
``anchor`` are hard errors, for the reasons
:doc:`/formats/03_coordinate_frames` sets out; getting it wrong shifts every pad
by the bbox-corner offset, which can turn a real match into an open with no other
signal. Every die written by ``gds_to_kicad`` and by the KiCad plugin writer
already emits the field.

Matching
--------

Matching runs per die, in three passes.

**1. By pin name.** Entries whose pad name and pillar ``pin_name`` are both
non-empty are grouped by name and paired nearest-first inside each group, so
duplicate names pair deterministically. A pair beyond tolerance is
``MISALIGNED``. Two conflicting names never cross-match: they surface as a
leftover pad and a leftover pillar rather than as a plausible-looking pairing.

**2. Nearest-unique fallback.** Remaining entries where at least one side is
unnamed are paired greedily by distance, within tolerance. This is what makes
the check usable on dies whose pad labels were not preserved.

**3. Leftovers.** Anything still unpaired becomes ``PAD_WITHOUT_PILLAR`` or
``PILLAR_WITHOUT_PAD``.

Findings
~~~~~~~~

.. list-table::
    :header-rows: 1
    :widths: 26 74
    :class: adk-wide-table

    * - Type
      - Meaning
    * - ``MISALIGNED``
      - A named pad and its same-named pillar are further apart than the
        tolerance. The finding carries both coordinate pairs and the distance.
    * - ``PAD_WITHOUT_PILLAR``
      - A pad has no matching pillar. Either the producer drew no bump for it,
        or the bump is far enough away that neither pass could pair them.
    * - ``PILLAR_WITHOUT_PAD``
      - A drawn pillar has no matching pad. The finding carries the pillar's
        ``pin_name``, its interconnect method and its coordinates.
    * - ``AMBIGUOUS_MATCH``
      - The nearest-unique fallback cannot decide: two or more candidates sit
        at indistinguishable distance, within 1e-6 um of each other. All the
        involved pads and pillars are named in the finding and are removed from
        further matching rather than being paired arbitrarily.
    * - ``NO_PAD_SOURCE``
      - Only with ``--strict``. A die declares a connection method, or has
        pillars in the manifest, but was given no pad source, so its alignment
        is unchecked.

Auto-resolve demotion
~~~~~~~~~~~~~~~~~~~~~

A named pair beyond tolerance is not automatically a defect. When the pillar
carries ``moved_by_auto_resolve: true`` **and** a recorded
``auto_resolve_shift_um`` magnitude, the producer's collision auto-resolver
shifted that bump away from its pad on purpose. In that case a deviation within
``shift + tolerance`` is reported as a warning instead of a finding.

Beyond ``shift + tolerance`` the flag cannot explain the deviation and the pair
is ``MISALIGNED`` again, with the recorded shift included in the finding. The
bound matters: without it, a genuine placement bug that happens to hit a
collision-moved bump would be hidden at any distance.

A bare ``moved_by_auto_resolve`` boolean with **no** recorded magnitude does
not demote. It cannot bound the excuse, so it is advisory only. The ADK's own
producer always records the magnitude alongside the flag, so real manifests are
unaffected; the rule closes an unbounded false pass for foreign or hand-edited
manifests. An unnamed moved pillar cannot be attributed to a pad at all and
still surfaces as a leftover.

Tolerance
~~~~~~~~~

``--tolerance-um`` sets the pad-to-pillar distance tolerance; the default is
1.0 um. It is validated as a finite non-negative number before the per-die loop
runs, so a pipeline that interpolated a failed computation into the flag fails
here rather than going green. ``NaN`` in particular would make every comparison
pass.

Running the check
-----------------

.. code-block:: bash

    python checks/pads_vs_pillars.py \
        --chiplet demo.chiplet \
        --pillars build/demo_interposer.pillars.json \
        --pins U1=chiplets/die_a.pins.json \
        --gds-pads U2 \
        --tolerance-um 1.0 \
        --json build/pads_vs_pillars.json \
        --strict

.. literalinclude:: /adk/_usage/pads_vs_pillars.txt
   :language: text

Warnings go to stderr prefixed with ``WARNING:``; findings go to stdout as
``<TYPE> [<ref>]: <message>``; the run ends with a one-line summary:

.. code-block:: text

    pads_vs_pillars: 0 finding(s), 1 warning(s) across 2 checked device(s): PASSED

Warnings, not findings, are also how the check reports a pillar manifest that
references a ``device_ref`` which is not a die in the ``.chiplet``, which
usually means the sidecar is stale.

The JSON report
~~~~~~~~~~~~~~~

``--json PATH`` writes the machine-readable report. Its shape:

.. code-block:: json

    {
      "tool": "pads_vs_pillars",
      "tolerance_um": 1.0,
      "strict": false,
      "devices": {
        "U1": {"pads": 48, "pillars": 48, "matched": 48, "findings": 0}
      },
      "findings": [],
      "warnings": [],
      "summary": {
        "devices_checked": 1,
        "findings": 0,
        "warnings": 0,
        "passed": true
      },
      "chiplet": "demo.chiplet",
      "pillar_manifest": "build/demo_interposer.pillars.json"
    }

Each finding object carries at least ``type``, ``device_ref`` and ``message``,
plus the coordinates, names, distance and, where relevant, the recorded
auto-resolve shift.

``--strict``
~~~~~~~~~~~~

Without ``--strict``, a die that declares a connection method but was given no
pad source produces a warning and the run can still pass. That is convenient
interactively and dangerous in CI, where "no pad source was supplied" and "the
pads are aligned" would produce the same green result. ``--strict`` turns those
into ``NO_PAD_SOURCE`` findings. Use it in CI.

Exit codes
~~~~~~~~~~

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - ``0``
      - Clean. No findings.
    * - ``1``
      - Findings. Reached **only** through the deliberate return at the end of
        a completed run.
    * - ``2``
      - Usage, validation or tooling error: a malformed ``.chiplet``, a
        rejected manifest, an unknown die reference, a missing ``klayout.db``,
        a malformed ``rotation.z``, an unsupported anchor, a bad tolerance.

The separation is structural, not incidental. The whole pipeline, including
report emission, runs inside one guard, and even an unexpected exception exits
2 with its traceback intact. Python's default handler exits 1, which would be
indistinguishable from a ``MISALIGNED`` finding, so no unguarded exception is
allowed to reach it. CI can rely on that: exit 1 means the assembly has a
problem, exit 2 means the check could not be run.

Importable entry points
-----------------------

.. code-block:: python

    load_chiplet(path) -> dict
    load_pillar_manifest(path) -> dict          # validated, exact version pin
    load_pads_config(path=None) -> dict         # pad layer vocabulary
    extract_gds_pads(gds_path) -> [{"name", "x_um", "y_um"}, ...]
    transform_pads(component, pads) -> [{"name", "x_um", "y_um"}, ...]
    match_device(ref, pads, pillars) -> (findings, matched_count)
    run_check(assembly, manifest, die_pads) -> report dict
    expand_path_vars(path) -> str               # ${VAR} discovery expansion

``run_check`` takes ``die_pads`` as die-local pad lists; the placement
transform is applied inside. ``match_device`` takes pads already in the global
frame. Both accept ``tolerance_um`` as a keyword argument, and ``match_device``
accepts a ``warnings`` list; when no list is supplied, the auto-resolve
demotion does not apply and a moved pillar beyond tolerance stays a finding,
which keeps legacy importers conservative.

``CheckError`` is the exception type for everything that maps to exit code 2.
It subclasses ``ValueError``. As everywhere in the ADK, new options are
appended as trailing keyword arguments with defaults, so importers stay
source-compatible.
