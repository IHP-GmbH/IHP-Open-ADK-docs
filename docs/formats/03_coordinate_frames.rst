Coordinate frames
=================

.. include:: /common.inc
.. include:: /_frame_values.inc

A ``.chiplet`` file carries XY positions that originate in several different
coordinate frames: KiCad's PCB frame, the HyperLynx file's absolute frame, and
the GDS frame. A die placed in the wrong one lands tens or hundreds of
micrometres off its pads, and the resulting layout still looks plausible. Six
alignment incidents in the reference toolchain traced back to exactly that.

The coordinate-frame contract is the response. It pins one canonical frame,
requires every writer to convert into it, and requires every reader to fail
loudly when something leaks through un-converted. It is normative: it is part
of the ``.chiplet`` format definition, it lives in the |spec-repo| repository
at ``docs/coord_frame_contract.md``, and where it and the format specification
could appear to differ, the contract governs.

The contract is a format-level companion to the schema, not the property of one
implementation.

.. warning::

    This is the single most common source of subtle placement bugs in the
    flow, and the failures are silent. Nothing downstream of a wrongly framed
    position can detect that it is wrong: the GDS is well formed, the DRC deck
    checks what it is given, and the 3D view renders happily. The only defence
    is that every writer converts and every reader range-checks.


The rules in brief
------------------

1. All ``position`` x and y values in a ``.chiplet`` file are expressed in the
   **GDS-bbox-corner frame of the interposer top cell**, y-up cartesian,
   micrometres.
2. ``position`` places the component's **anchor reference point** in x and
   y: the centre of its GDS bounding box for ``anchor: bbox_center``, its own
   GDS ``(0, 0)`` for ``anchor: gds_origin``. It is the geometric centre only
   in the ``bbox_center`` case. In z a die's ``position`` is its **seating
   plane**, the bottom face of the placed body; an interposer's is the origin
   of its local frame.
3. Each component declares an explicit ``anchor``: ``gds_origin`` for a mesh
   built around the component's own GDS ``(0, 0)``, ``bbox_center`` for a mesh
   centred on its own GDS bounding box.
4. Z-mounting is **per-die**. Each die's ``connection`` selects its own
   bump or pillar bodies, so one assembly can mix methods.
5. ``hyp_to_gds.py --update-chiplet-file`` is mandatory in the canonical path.
   KiCad's ``pcbnew`` GUI export produces an intermediate file whose positions
   are in the wrong frame.
6. Interposer ``dimensions`` are the board outline (prBoundary 235/0, drawn
   from KiCad Edge.Cuts) when that layer is present; ``position`` stays the
   full-GDS-bbox centre.


The canonical frame
-------------------

.. list-table:: Canonical frame definition
    :header-rows: 1
    :widths: 30 70
    :class: adk-wide-table

    * - Property
      - Value
    * - Reference object
      - The interposer's GDS top cell
    * - Origin ``(0, 0)``
      - Lower-left corner of the interposer's GDS bounding box
    * - X axis
      - Increases rightward
    * - Y axis
      - Increases upward (y-up cartesian)
    * - Units
      - Micrometres
    * - Float precision
      - At least six decimal places, that is 1 pm in theory

.. figure:: /_figures/canonical_frame.*
    :align: center
    :alt: Plan view of the interposer GDS bounding box with the origin at its lower-left corner, x rightward, y upward, and a die whose position marks its anchor point, drawn for anchor: bbox_center, where the anchor point is the die's bbox centre.
    :width: 90%

    The canonical frame. Positions are measured from the lower-left
    corner of the interposer's GDS bounding box, in micrometres, y up.

Why the GDS bbox corner
~~~~~~~~~~~~~~~~~~~~~~~

The choice is not arbitrary, and the alternative was tried.

- The GDS file is the physical fabrication artefact. The interposer GDS is the
  ground truth of the layout.
- KLayout, the 3D scene in Chiplet Studio, and any downstream packaging tool
  all consume positions as offsets within the GDS bbox.
- The PCB Edge.Cuts bounding box, which KiCad uses natively, **does not always
  match** the GDS bbox. The wire-bond demo historically carried a hidden shift
  of (-200 um, -780 um) between the two, even though the widths and heights
  agreed to the micrometre. The GDS frame is the only one with no such hidden
  shift relative to what actually gets fabricated.
- Because the converter draws the board outline (Edge.Cuts into prBoundary
  235/0) into the interposer GDS, the GDS bbox contains the outline. In the
  normal case, where all drawn geometry sits inside the outline, the canonical
  origin coincides with the outline's lower-left corner and the historical
  shift is zero by construction.


Position semantics
------------------

``position`` x and y place the component's anchor reference point, which
the component's ``anchor`` names. For ``anchor: bbox_center`` that is the
component's geometric centre. For ``anchor: gds_origin`` it is the component's
own GDS ``(0, 0)``, wherever that origin sits in the artwork, so a die's
``position`` is its centre only if its layout author put the origin there.

The contract's own example is a ``bbox_center`` die whose lower-left corner
sits at |contract-example-corner| inside the interposer, so its ``position``
is that corner plus half its ``dimensions``. It is seated on the IntM4TM2
plane plus a |contract-example-stack-height| um stack (see
`The z-mounting rule`_):

.. literalinclude:: _excerpts/contract_position.yaml
    :language: yaml

A die's ``position.z`` is its seating plane: the bottom face of the placed
body, the face that meets the mounting surface. For a die on a connection
stack, that is the tip of the stack. ``dimensions.thickness`` extends the body
**upward** from ``position.z``. An interposer's ``position.z`` is the origin of
its local frame instead (`Interposer dimensions against interposer
position`_).

.. note::

    Files that predate real thickness data carry the placeholder
    ``thickness: 0.0``, where the centre reading and the seating-plane reading
    of ``position.z`` coincide. With a real thickness they differ by
    ``thickness / 2``, and the seating-plane reading is the normative one: it
    is what the z-mounting rule computes and what consumers implement.

Interposer dimensions against interposer position
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The interposer is the one component whose ``dimensions`` and ``position`` come
from different sources and answer different questions.

.. list-table:: Interposer geometry fields
    :header-rows: 1
    :widths: 22 34 44
    :class: adk-wide-table

    * - Field
      - Source
      - Meaning
    * - ``dimensions.width`` / ``height``
      - bbox of prBoundary 235/0, the board outline drawn from Edge.Cuts, when
        that layer is present; bbox of all drawn geometry otherwise (legacy
        GDS)
      - The fab extent of the interposer, which is what viewers render as the
        substrate body
    * - ``dimensions.thickness``
      - KiCad stackup (``GetBoardThickness``)
      - The interposer's physical body z-extent, silicon substrate plus BEOL.
        It extends **downward** from ``attachment_surface_z``, so the die-mount
        plane is the top surface and the body sits below it. It is the body
        only and never a mount plane.
    * - ``attachment_surface_z``
      - The interposer PDK's key ``beol.attachment_surface_z_um``, see
        :ref:`chiplet_mounting_plane`
      - The die-attachment surface in the interposer-local frame, the plane
        dies mount on. Optional in the schema; a file that seats dies without
        it has no mount plane (:ref:`chiplet_mounting_plane`).
    * - ``position.x`` / ``y``
      - Half of the **full** GDS bbox, all layers including the outline
      - Where the mesh bbox centre sits in the canonical frame, consistent with
        ``anchor: bbox_center``

The interposer's ``position.z`` places the origin of its local frame in the
canonical frame; for the interposer it is not the body's bottom face. The plane
in the canonical frame is therefore ``interposer.position.z +
attachment_surface_z``, and the body spans local z ``attachment_surface_z -
thickness`` to ``attachment_surface_z``. A die's ``position.z`` is in the
canonical frame. Every file the pipeline writes keeps the interposer at z 0,
where the local and canonical planes coincide.

When the outline contains all drawn geometry, the full bbox equals the outline
bbox and both fields describe the same rectangle. When copper leaks outside the
outline, which is a design error and which the converter warns about loudly at
export, ``dimensions`` keeps the true board size while ``position`` follows the
mesh centre. That preserves die and pillar registration in the render at the
cost of a shifted substrate body.


The anchor convention
---------------------

Each component declares how its local mesh is built. The anchor is declared by
the **writer**, based on knowledge of how that component's GDS was produced.
The reader must not infer it from the component type.

.. list-table:: ``anchor`` values
    :header-rows: 1
    :widths: 18 42 40
    :class: adk-wide-table

    * - Value
      - Meaning
      - Use cases
    * - ``gds_origin``
      - The mesh is built around the component's own GDS ``(0, 0)``. The
        ``position`` value is added to the GDS origin of the cell, with no
        extra centring.
      - Dies produced by ``gds_to_kicad``, whose footprint anchor sits at GDS
        ``(0, 0)``. Any die whose layout author put the cell origin where the
        placement reference should be.
    * - ``bbox_center``
      - The mesh is centred on the component's own GDS bounding box.
        ``position`` places that bbox centre.
      - Interposers. Components whose GDS layout uses absolute pcbnew-derived
        coordinates and whose meaningful placement reference is the geometric
        centre.

If ``anchor`` is absent, the reader must default to ``bbox_center`` and warn.
That path exists for legacy files only; there is no auto-migration, and new
files must declare the field. The reference implementation collects the
defaulted components and emits one file-level summary rather than one warning
per component, so a legacy file produces a single readable line naming every
component that was defaulted.

Note that ``gds_to_kicad``'s footprint convention is the *reason* dies declare
``gds_origin``. The tool sets the footprint reference text at ``(at 0 0)``,
placing the footprint origin at GDS cell ``(0, 0)``, and places pads at their
GDS-derived centres relative to that origin. The die's GDS ``(0, 0)`` is
therefore the reference point KiCad uses, and the ``.chiplet`` anchor has to
say so.


Orientation and flip-chip mirroring
-----------------------------------

A flip-chip die is mounted face down: its active layers and BEOL point at the
interposer, and the connection stack carries every pad across the gap.

.. figure:: /_figures/flipchip.*
    :align: center
    :alt: Cross-section of a flip-chip die mounted face down on an array of five Cu pillars with SnAg caps, seated over the interposer's TopMetal2 and its lower metal layers. The die's active layers and BEOL face downward and its substrate sits on top.
    :width: 80%

    A flip-chip die in cross-section, seated on Cu pillars with SnAg
    caps over the interposer's TopMetal2. The die's active face points down at
    the interposer, and that physical fact is what the ``flip_chip`` mirror
    described below encodes in plan view.

``orientation`` takes exactly two canonical values.

.. list-table:: ``orientation`` values
    :header-rows: 1
    :widths: 24 76
    :class: adk-wide-table

    * - Value
      - Meaning
    * - ``face_up`` (default)
      - The die artwork is used as drawn, with no mirror. Applied before
        ``rotation.z``.
    * - ``flip_chip``
      - The die is mounted face-down onto the interposer, realised as an
        **x-mirror** of the die artwork (``mx = -1``), applied before
        ``rotation.z``.

**``face_down`` is not a canonical token.** Flip-chip mounting is expressed as
``flip_chip``, because the mirror is the observable contract while "face down" is
only the physical picture. Writers must emit ``face_up`` or ``flip_chip`` and
nothing else.

Readers split on what to do with a non-canonical token:

- **Validators and exporters** must reject it. An ambiguous token must never
  silently yield wrong geometry. In the ADK, ``pads_vs_pillars`` and
  ``chiplet2dbx`` both raise a hard error on ``face_down`` and on any unknown
  string.
- **Interactive viewers** may be lenient and keep rendering, but must warn, and
  may treat ``face_down`` as ``flip_chip``. A viewer must never silently render
  an unknown token as ``face_up``, because un-mirrored is the one answer that
  looks fine and is wrong.

The flip is realised as a mirror in x only, never in y. A pad that sat on the
left of the die layout therefore ends up on the right of the assembly, which is
the whole reason the mirror has to be applied before any pad is compared
against a pillar. ``gds_to_kicad --flip-chip`` implements it as
``mx = -1 if flip_chip else 1``, generating the footprint as seen from the
interposer side.


From a die-local coordinate to an assembly coordinate
-----------------------------------------------------

This is the arithmetic every consumer has to get right. A pad or bump lives in
the die's own GDS frame, in micrometres, y-up, with the origin at the die's GDS
``(0, 0)``, which is what ``anchor: gds_origin`` declares. To compare it
against anything in the assembly, for example the pillar positions in the
pillar manifest, it has to be mapped into the canonical frame:

.. code-block:: text

    global = position + R(rotation.z) * M * local

with

.. code-block:: text

    M = diag(-1, 1)   for orientation: flip_chip
    M = diag( 1, 1)   for orientation: face_up

    R(a) = [ cos a   -sin a ]
           [ sin a    cos a ]

The order matters: **mirror first, then rotate**, then translate by the die's
``position``. Applying the rotation before the mirror gives a different answer
for every angle that is not a multiple of 180 degrees.

.. figure:: /_figures/pad_transform.*
    :align: center
    :alt: Four panels taking a pad from the die-local frame through the flip-chip mirror, then the rotation, then the translation by the die position into the canonical frame.
    :width: 90%

    Mirror first, then rotate, then translate. Applying the flip-chip
    mirror in the wrong place moves the whole pad field by a fixed offset and
    leaves the layout looking plausible.

Worked case
~~~~~~~~~~~

Take die ``U1`` from the specification's worked example,
``examples/interposer_demo_design.chiplet``:

.. literalinclude:: _excerpts/spec_example_u1.yaml
    :language: yaml

Its ``anchor: gds_origin`` makes ``position`` the point where the die's GDS
``(0, 0)`` lands, which is also the origin of the die-local pad coordinates.
Take a pad whose centre in the die's own GDS is |spec-u1-pad-local| um.

**Step 1, mirror.** ``orientation: flip_chip`` means ``M = diag(-1, 1)``, so
the local coordinate becomes |spec-u1-pad-local-mirrored|. Only x changes sign.

**Step 2, rotate.** ``rotation.z`` is 0, so ``cos a = 1`` and ``sin a = 0`` and
the vector is unchanged.

**Step 3, translate** by ``position``:

.. parsed-literal::

    x = |spec-u1-x| + (-|spec-u1-pad-local-x|)
    y = |spec-u1-y| + (|spec-u1-pad-local-y|)

The pad sits at |spec-u1-pad-flip| um in the canonical frame.

Had the same die been ``face_up``, step 1 would have left x at
|spec-u1-pad-local-x| and the pad would land at |spec-u1-pad-face-up|:
|spec-u1-pad-face-up-shift| um away, more than |spec-u1-pad-face-up-pitches|
pitches at |spec-u1-connection|'s |spec-u1-pitch| um minimum. This is the
error mode that makes a flip-chip mistake look like a systematic pad-to-pillar
offset rather than an obvious break.

Now rotate the same flip-chip die by 90 degrees, ``rotation: {z: 90.0}``. Then
``cos a = 0``, ``sin a = 1``, and the mirrored local vector
|spec-u1-pad-local-mirrored| transforms as:

.. parsed-literal::

    x = |spec-u1-x| - (|spec-u1-pad-local-y|)
    y = |spec-u1-y| + (-|spec-u1-pad-local-x|)

giving |spec-u1-pad-flip-r90| um. Note that ``position`` did not move: the
die turns about its anchor reference point, here its GDS ``(0, 0)``, so that
point is rotation invariant and every pad moves around it. For a
``bbox_center`` component the same holds for its bbox centre.

.. tip::

    ``pads_vs_pillars`` implements this transform in ``transform_pads()`` and
    is the cheapest way to find out whether your understanding of a die's
    placement agrees with the toolchain's. It compares every transformed pad
    against the pillar manifest and reports the ones that do not match within
    tolerance. See :doc:`/adk/08_pads_vs_pillars`.

The 3D world frame
~~~~~~~~~~~~~~~~~~

A viewer maps the canonical frame into its own world frame. Chiplet Studio's
OpenGL world is y-up in millimetres, with z out of the screen, so the mapping
is an axis permutation plus a sign flip and a unit change:

.. code-block:: cpp

    geometry.transform.translate(
        static_cast<float>(pos.x / 1000.0),    // chiplet X -> 3D X (mm)
        static_cast<float>(pos.z / 1000.0),    // chiplet Z -> 3D Y (mm)
        static_cast<float>(-pos.y / 1000.0));  // chiplet Y -> 3D -Z (mm)

The synthetic contract fixture checks this with no tolerance at all: an
interposer at ``(500, 500, 0)`` um must map to ``(0.5, 0.0, -0.5)`` mm, and a
die at ``(250, 250, 50)`` um to ``(0.25, 0.05, -0.25)`` mm.


.. _chiplet_z_mounting:

The z-mounting rule
-------------------

For dies that mount on a connection stack, whether Cu pillar, solder bump or
microbump:

.. code-block:: text

    z_die = interposer.position.z + mounting_surface + connection.total_height()

where ``mounting_surface`` is the ``z_bottom`` of the interconnect body whose
name matches the connection stack's first layer, from the interconnect-PDK
fragment for this die's ``connection`` merged on the file's plane (the fragment
is rebased on that plane, so this ``z_bottom`` is the plane), and
``connection.total_height()`` is the sum of ``height`` over every layer in the
stack.

.. figure:: /_figures/zstack.*
    :align: center
    :alt: Cross-section of two dies on one interposer, one on a Cu-pillar stack and one on a microbump stack, seated at different heights above the same attachment surface.
    :width: 90%

    The z-mounting rule. A die's seating plane is the attachment
    surface plus the total height of its own connection stack, so two dies with
    different methods sit at different heights on the same interposer.

.. _chiplet_mounting_plane:

The mounting plane
~~~~~~~~~~~~~~~~~~

The contract (sections 3.1 and 3.4) gives a file one mount plane: its
interposer's ``attachment_surface_z``, as the file declares it, in the
interposer-local frame. Nothing stands in for a missing value: the reference
readers hold no PDK, a tool's stackup copy is not the format, and
``dimensions.thickness`` is the body. An interposer seats dies when its file
holds a ``die`` or ``die_array`` component; one that seats dies and declares no
``attachment_surface_z`` has no mount plane (validation rule 17, and `Edge
cases`_ below). An interposer that seats no die needs no plane.

The interconnect fragment is rebased on the file's plane, not on the technology
stackup's. On the IntM4TM2 interposer the plane is the top of TopMetal2,
|interposer-attachment-z| um, which is the interposer PDK's key
``beol.attachment_surface_z_um`` in ``libs.tech/intm4tm2_stack.json``.

At the pinned versions the reference consumers seat dies as follows:

.. list-table:: Mounting plane resolution in the reference consumers
    :header-rows: 1
    :widths: 34 66
    :class: adk-wide-table

    * - Consumer
      - What it seats a die on
    * - ``chiplet2dbx`` (|adk-repo|)
      - Takes the file's ``attachment_surface_z`` and adds the interposer's
        ``position.z``. An interposer that seats dies without the field is
        refused; ``dimensions.thickness`` is read only for an interposer that
        seats no die, and never in place of the plane.
    * - Chiplet Studio, die whose connection resolves
      - The ``z_bottom`` of the stack's first layer among the interconnect
        bodies merged on the mount plane: the file's ``attachment_surface_z``,
        else ``dimensions.thickness``, never the stackup's plane. The
        interposer stackup contributes no height. When the stackup puts its
        plane elsewhere than the file, a viewing note says so and the die
        seats on the file's plane.
    * - Chiplet Studio, any other die
      - The file's ``attachment_surface_z``. With none,
        ``dimensions.thickness`` (``value_or(thickness)``), and when any die
        has a connection a viewing note names the file and says the plane is
        a guess.

For a file that declares ``attachment_surface_z`` and keeps its interposer at
z 0, which every file the reference flow writes does, the consumers agree.
Chiplet Studio leaves the interposer's ``position.z`` out of a die's z, so on
an interposer placed above z 0 it seats the dies lower than the contract. On a file whose interposer
seats dies without it, ``chiplet2dbx`` refuses and Chiplet Studio shows the
dies on a warned guess, which is what the contract asks of an exporter and of
a viewer. The specification ships these cases in
``conformance/fixtures/mount_plane/``, where ``cases.json`` states per file
what an exporter and a viewer do. ``chiplet2dbx`` runs them in the ADK's
tests, from a copy in ``tests/fixtures/mount_plane/`` held byte for byte to
the specification's. Chiplet Studio computes z but its tests do not read
them, and the reference readers compute no z.

How the mounting surface resolves
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Taking |spec-u1-connection| on the IntM4TM2 interposer of the worked example,
whose file declares ``attachment_surface_z`` as |interposer-attachment-z|:

1. Take the die's connection id, |spec-u1-connection|.
2. Merge the interconnect fragment for that connection id on the mounting
   plane. The fragment declares
   ``z_reference: attachment_surface``, so its ``CuPillar`` layer, at local z
   0.00, is offset by the file's ``attachment_surface_z``. After the merge,
   ``CuPillar.z_bottom`` is |interposer-attachment-z|.
3. The first layer name of the stack is ``CuPillar``. Look it up among the
   merged bodies. It is found, so ``mounting_surface`` is
   |interposer-attachment-z|.
4. ``z_die = interposer.position.z + mounting_surface +
   total_height(connection)``. The example's interposer sits at z 0, so that
   is |interposer-attachment-z| + |spec-u1-stack-height| = |spec-u1-z|.

The merge happens per die and before the first-layer lookup, which is what
makes the rule per-die: a die using any method seats on that method's body
heights even when its neighbours use other methods.

.. _chiplet_z_worked_case:

Worked case, two dies and two methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The specification's worked example seats its two dies on different stacks:

.. list-table:: Mixed-method z-mounting in the specification's worked example
    :header-rows: 1
    :widths: 10 24 34 14 18
    :class: adk-wide-table

    * - Die
      - ``connection``
      - Stack layers
      - ``total_height``
      - ``z_die``
    * - U1
      - |spec-u1-connection|
      - |spec-u1-stack-layers|
      - |spec-u1-stack-height|
      - |spec-u1-z|
    * - U2
      - |spec-u2-connection|
      - |spec-u2-stack-layers|
      - |spec-u2-stack-height|
      - |spec-u2-z|

Both dies sit on the same plane, |interposer-attachment-z|, and end up at
different heights because their interconnect differs. In the specification's
example, U1 selects |spec-u1-connection| rather than |spec-next-option|
because its pad ring contains a 79.93 um-pitch pair, which is legal at
|spec-u1-connection|'s |spec-u1-pitch| um minimum pitch but below
|spec-next-option|'s |spec-next-option-pitch| um. That selection lives in the
die's footprint ``CONNECTION`` field in KiCad and rides through the export
unchanged.

Edge cases
~~~~~~~~~~

.. list-table:: Edge cases for every tool that computes z
    :header-rows: 1
    :widths: 46 54
    :class: adk-wide-table

    * - Case
      - Behaviour
    * - Die has no ``connection`` field
      - Mount on the file's plane with ``connection_height = 0``.
    * - ``connection`` id is not a defined connection stack
      - Same as above.
    * - The connection's first layer is not in the interposer stackup, even
        after the fragment merge
      - Mount on the file's mounting plane.
    * - ``interposer.attachment_surface_z`` is absent and the interposer
        seats dies
      - No mount plane. An exporter that places dies in z refuses the file,
        naming the interposer and the remedy: declare
        ``attachment_surface_z``, which for ``intm4tm2`` is the interposer
        PDK's ``beol.attachment_surface_z_um``. A viewer shows the dies on
        ``dimensions.thickness`` with a warning that names the file; that seat
        is a display guess, not a mount plane. Neither takes a stackup's
        plane.
    * - Die has ``position.z`` explicitly set to a non-zero value
      - Use the explicit value. Do not auto-calculate.

A die with an explicit ``position.z`` still counts as seated: the plane is
what that z is checked against, by `The plane check`_ and by the exporter
check on :doc:`/formats/08_3dblox_interop`.

.. _chiplet_passivation_trap:

The attachment surface is not the substrate top
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The attachment surface is generally **not** the substrate's maximum z.
Passivation can rise above it: on the IntM4TM2 interposer the plane is the top
of TopMetal2 and the passivation films lie above it. Anything that derives the
die-to-substrate gap from an outline maximum z instead of the attachment
surface disagrees with ``total_height()`` by the passivation height.
:doc:`/formats/08_3dblox_interop` describes where this matters on the export
side.

Writing a derived z
~~~~~~~~~~~~~~~~~~~

A z derived from the plane, a die's ``position.z`` or a wire's start or end z,
is written as the exact decimal sum of the plane and the height as written,
emitted as the shortest text that reads back as that sum:
|interposer-attachment-z| + |spec-u1-stack-height| is written |spec-u1-z|,
never |spec-u1-z-17-digits|, which is the same binary value printed to 17
significant digits instead of as its shortest text. A writer also sums in
decimal, not in binary floating point, so a height with more decimals than the
plane keeps all of them.

.. _chiplet_plane_check:

The plane check
~~~~~~~~~~~~~~~

For ``technology: intm4tm2`` the declared ``attachment_surface_z`` must equal
the interposer PDK's ``beol.attachment_surface_z_um``. The contract's check
reads that key and the ``.chiplet`` files whose interposer declares
``technology: intm4tm2``, and fails, naming the file and line, when the file's
``attachment_surface_z`` differs from the key, when the interposer seats dies
and declares no ``attachment_surface_z`` (the key does not stand in for it),
or when a die with a ``connection`` has a non-zero ``position.z`` other than
the interposer's ``position.z`` plus the file's plane plus that connection's
total height, written as above.

In the reference toolchain the check is ``ci/check_attach_plane.py`` in
|tools-repo|. While the image is built it walks the KiCad plugin, Chiplet
Studio, ``gds_to_kicad``, the interconnect PDK and |tools-repo|'s examples, as
its gitlinks pin them, and the staged chiplet-cosim, chiplet-spec,
interposer-pnr and packaging-flow trees. That repository's CI walks the first
five and reports the staged four as not walked, so the image build is the only
place where the PDK sits beside every consumer. A die whose connection neither
the file's ``connection_stacks`` nor the interconnect PDK defines is listed as
not judged, and the check does not fail on it. It accepts a
whole-number die z written with a trailing ``.0``. The reference readers do
not run it, since they hold no PDK; a viewer may report the same mismatch when
it opens a file, but that report is not the check. Conformance fixtures are
format data, not designs: they may hold other values, and the check does not
read them.


io_pads
-------

Assembly-level I/O pads live in the same canonical frame as components:
GDS-bbox-corner of the interposer top cell, geometric centre of the pad,
micrometres. They are nested under their interposer in the schema and inherit
its frame. They do **not** declare an ``anchor``, because they are points and
``size`` is a 2D extent rather than a centring rule.

The finalizer re-anchors them with the same ``(gds_left, gds_bottom)`` shift it
applies to dies, rebuilding each pad from the source JSON:

.. code-block:: python

    component['io_pads'] = [
        {
            'id': p.get('ref') or f"J{i+1}",
            'io_class': p.get('io_class', 'wire_bond'),
            'net': p.get('net', ''),
            'position': {
                'x': float(p.get('x_um', 0.0)) - gds_left,
                'y': float(p.get('y_um', 0.0)) - gds_bottom,
            },
            ...
        }
        for i, p in enumerate(io_pads)
    ]

If no bbox is available the finalizer leaves the pads un-shifted, in
HYP-absolute coordinates, and warns. That is exactly the condition the leak
guard below is designed to catch.


The leak guard
--------------

A reader must warn, or reject, when any ``position.x`` or ``position.y``
exceeds 1e5 um in magnitude, for components and for io_pads alike. The
reference threshold constant is ``kPositionWarnThreshold_um = 1.0e5``.

The reasoning is blunt: an interposer GDS bbox is on the order of a few
thousand micrometres, so a value two orders of magnitude larger is not a large
design, it is HYP-absolute coordinates that were never converted. The guard is
a heuristic, and it is deliberately loose enough that it never fires on a real
assembly and tight enough that a whole class of leaks cannot reach a viewer or
a DRC run unnoticed.


The writer contract
-------------------

Every tool that writes a ``.chiplet`` file must:

1. Express all ``position`` x and y in the canonical frame.
2. Place each component's anchor reference point at ``position``: the bbox
   centre for ``bbox_center``, the component's GDS ``(0, 0)`` for
   ``gds_origin``.
3. Declare ``anchor`` explicitly per component.
4. Set ``z`` to the explicit user value, to 0 to defer to auto-calculation, or
   to the auto-calculated value.
5. Write a z derived from the plane as the exact decimal sum described in
   `Writing a derived z`_.

Any new writer, whether a manual editor, a plugin or a script, must cite the
contract by path in a comment next to the writer code, and reviewers are
expected to reject writers that do not.

Why KiCad needs a finalizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

KiCad cannot produce the canonical frame on its own, for one structural reason:
``pcbnew`` does not read the interposer GDS, so it does not know the GDS bbox
that defines the origin. The pipeline therefore keeps two steps and makes them
explicit rather than pretending one step is enough.

KiCad's exporter emits an **intermediate** file with positions in
PCB-bbox-corner, and marks it:

.. code-block:: yaml

    _metadata:
      frame: pcb-bbox-corner
      finalize_required: true
      finalizer: hyp_to_gds.py --update-chiplet-file

It still emits ``anchor`` per component, ``bbox_center`` for the interposer and
``gds_origin`` for dies that came from ``gds_to_kicad``, because that
information is available to it. Readers must refuse to load a file carrying
``finalize_required: true``.

``hyp_to_gds.py --update-chiplet-file`` is the only place that owns the
interposer GDS bbox, so it performs the frame conversion: the interposer
``position`` becomes the GDS-bbox centre, die and io_pad positions are
re-anchored to the GDS-bbox corner with the same shift, ``anchor`` is emitted
per component, and the ``_metadata`` block is stripped. A canonical
``.chiplet`` carries no ``finalize_required`` marker.

.. tip::

    Tighter integration, where KiCad's "Export Chiplet" action invokes the
    finalizer itself so that a single action yields a canonical file, is
    deferred rather than rejected. All the information the finalizer consumes
    is already present in the HyperLynx file KiCad produces; what is missing is
    a way to make ``hyp_to_gds.py`` discoverable from KiCad's runtime, which is
    a packaging problem rather than a contract problem.


The reader contract
-------------------

Every tool that reads a ``.chiplet`` file must:

1. Parse ``anchor`` and store it on the component.
2. Use ``anchor``, not the component type, to drive mesh centring.
3. Range-check positions and warn loudly past the 1e5 um threshold.
4. Apply the tolerant ``format_version`` policy of
   :ref:`validation rule 1 <chiplet_validation_rules>` rather than
   exact-string equality.

.. note::

    The reference libraries do not satisfy these requirements on their own.
    ``chiplet-format-io`` in both languages is structural only: it parses and
    round-trips ``anchor`` as a raw string, and performs no anchor defaulting,
    no range check and no z-mounting. A reader that needs the full contract has
    to add the frame semantics on top, as Chiplet Studio does in
    ``ChipletFormat.cpp``, ``LayerMeshBuilder.cpp``, ``AssemblyView.cpp`` and
    ``Assembly.cpp``. See :doc:`/tools/04_chiplet_studio`.


Verification fixtures
---------------------

The contract is backed by three checks that can fail independently.

**A synthetic unit fixture** loads a hand-written assembly, one 1000 x 1000 um
interposer with ``anchor: bbox_center`` and two 100 x 100 um dies with
``anchor: gds_origin``, plus four io_pads at the corners, and asserts that
``anchor()`` returns the parsed value, that ``anchor_declared()`` is true, and
that the 3D world mapping is exact with no tolerance.

**A demo round-trip**, in Chiplet Studio's
``tests/test_coord_frame_contract.cpp``, loads a finalized copy of the
wire-bond demo and checks its real numbers. The copy is not bundled with the
repository: ``scripts/run-gate.sh`` mounts it from
``WIREBOND_DEMO_CHIPLET_HOST`` and records its hash, and the tests do not run
without it. They expect U1 near |studio-demo-u1-xy| at z |studio-demo-u1-z|
and U2 near |studio-demo-u2-xy| at z |studio-demo-u2-z|, x and y within
|studio-demo-xy-tol| um and z within |studio-demo-die-z-tol| um, which locks
the mixed-method case; the interposer near |studio-demo-interposer-xy| at z
|studio-demo-interposer-z|; every io_pad inside the interposer extent, which
is the regression net for the HYP-absolute leak; and, implicitly, that the
file loads at all, which it would not if the ``_metadata`` marker had
survived.

**A KLayout-independent geometric check**, ``check_complete_gds_alignment.py``,
opens the finished assembly GDS, finds U1's flipped instance and the Cu-pillar
array, computes both bounding boxes in top-cell coordinates, and asserts that
they overlap with centroids within 1 um. It is deliberately independent of the
viewer, so that a viewer bug cannot mask a real GDS misalignment.


Appendix: glossary of coordinate frames
---------------------------------------

These are all the frames present in the toolchain. From the schema's
perspective only frame 6 (canonical) and frame 9 (3D world) are visible; the
rest are internal to specific tools and never appear in a ``.chiplet`` file.

.. figure:: /_figures/frame_chain.*
    :align: center
    :alt: Graph of the nine coordinate frames from KiCad internal units through the HyperLynx and GDS frames into the canonical frame and the 3D world frame, with the converting tool marked on each edge.
    :width: 90%

    The nine coordinate frames in the toolchain, and where each
    conversion happens. Only frames 6 and 9 are visible outside the tools.

.. list-table:: Frames in the chiplet toolchain
    :header-rows: 1
    :widths: 6 26 34 34
    :class: adk-wide-table

    * - \#
      - Frame
      - Origin
      - Used by
    * - 1
      - KiCad PCB internal nm
      - KiCad's signed integer internal units (nm)
      - KiCad core; not exposed to ``.chiplet``
    * - 2
      - PCB-bbox-corner
      - Lower-left of ``BoardEdgesBoundingBox``, or a fallback
      - KiCad ``export_chiplet.cpp`` for dies and io_pads
    * - 3
      - PCB-bbox-center
      - ``(PCB_w/2, PCB_h/2)``
      - KiCad ``export_chiplet.cpp`` for the interposer
    * - 4
      - HYP absolute
      - HyperLynx file native: metres, KiCad y-down convention before
        conversion
      - ``hyp_to_gds.py`` input parsing
    * - 5
      - GDS absolute
      - GDS file native: micrometres, y-up cartesian
      - KLayout; ``hyp_to_gds.py`` for cell instance placement
    * - 6
      - **GDS-bbox-corner (canonical)**
      - Lower-left of the interposer GDS bbox
      - **This contract.** Also ``update_chiplet_file`` for dies.
    * - 7
      - GDS-bbox-center
      - ``(GDS_w/2, GDS_h/2)``
      - ``update_chiplet_file`` for the interposer
    * - 8
      - Interposer-local-corner
      - The frame components mean to be in
      - The schema's intent, now formalised as identical to frame 6
    * - 9
      - Chiplet Studio 3D world
      - OpenGL world: millimetres, y-up, z out of the screen
      - ``AssemblyView`` final placement


Where to go next
----------------

- :doc:`/formats/01_chiplet` for the schema these positions live in.
- :doc:`/adk/08_pads_vs_pillars` for the check that applies the transform on
  real designs.
- :doc:`/flow/04_export` for where the finalizer runs in the flow.
- :doc:`/formats/08_3dblox_interop` for how the frame and orientation
  conventions translate on export.
