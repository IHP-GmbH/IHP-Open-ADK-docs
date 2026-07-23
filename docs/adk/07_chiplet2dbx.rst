OpenROAD 3Dblox export
======================

.. include:: /common.inc

``openroad/chiplet2dbx.py`` derives a 3Dblox view of a finalised ``.chiplet``
assembly, so the assembly geometry can be loaded into OpenROAD and linted by
``check_3dblox``. It is a one-way, geometric export: dies become black-box
chiplet definitions, the interposer becomes a substrate, and each die's
connection stack becomes a connection whose thickness is the stack's exact
total height.

3Dblox, originated by TSMC and being standardised as IEEE P3537, describes
multi-die physical assemblies, and has an open-source implementation in OpenROAD
under BSD-3 that this exporter writes for.

The two formats describe the same physical assembly at different abstraction
levels. 3Dblox binds it to the place-and-route abstraction and references no
artwork. ``.chiplet`` binds it to the mask level: GDS bodies, layer property
files, per-layer interconnect metallurgy and fab DRC parameters. A design can
usefully hold both, one for exploration and P&R-level linting, one for
mask-level assembly and DRC.

.. note::

    The export is lossy by declaration. Mask artwork, per-layer metallurgy,
    interconnect method provenance, DRC parameter linkage, ``io_pads``,
    polygonal boundary manifests and parasitics have no 3Dblox target and are
    dropped. The ``.chiplet`` file stays the **authoritative** placement source;
    a ``.3dbx`` is a derived artefact, regenerated rather than edited. The
    mapping follows the non-normative interoperability appendix
    (``docs/3dblox_interop.md``) of the |spec-repo| repository; where that
    appendix and this tool disagree, the appendix governs. See
    :doc:`/formats/08_3dblox_interop`.

What it consumes and what it emits
----------------------------------

The single required input is a finalised ``.chiplet`` file: an assembly whose
components carry final positions, dimensions, technologies and connection
stacks. It is loaded through the vendored reference reader, so a file that
fails ``.chiplet`` validation fails here first.

.. list-table:: Outputs
    :header-rows: 1
    :widths: 26 74
    :class: adk-wide-table

    * - Artefact
      - Content
    * - ``<name>.3dbv``
      - The ``ChipletDef`` view. One black-box def per distinct die
        (``design_area``, ``thickness``, front and back bond regions covering
        the full outline, no cell LEF, DEF or Verilog), plus the interposer as
        a ``substrate`` def.
    * - ``<name>.3dbx``
      - The placed assembly: the ``Design`` name, one ``ChipletInst`` per
        component, the ``Stack`` block with each instance's corner location, z
        and orientation, and the ``Connection`` block. It ``include``\ s the
        ``.3dbv`` from its header.
    * - ``<technology>.lef``
      - One minimal technology LEF per distinct ``.chiplet`` technology,
        referenced as each def's ``APR_tech_file``. Units only, plus a single
        minimal routing layer ``BUMP_ATTACH`` when the export is bump-aware,
        so the bump macros' pad ``PORT``\ s resolve in every technology.
    * - ``<def>.bmap``
      - With ``--pins`` only. Bump centres of one bump-aware def, in the
        def-local frame, with port and net columns.
    * - ``<method>__<technology>.lef``
      - With ``--pins`` only. The bump macro LEF for one connection method in
        one technology, rendered by the interconnect PDK's generator.

``--name`` overrides the output basename, which otherwise comes from
``assembly.name``. ``--out-dir`` defaults to the directory of the input file.
Every written path is printed on stdout.

.. tip::

    A minimal technology LEF is generated rather than required because the
    target ODB needs every chip to carry a technology: ``dbBlock::create``
    reads the technology's database units with no null check. The tech-LEF
    filename is also the technology identity the loader deduplicates on, so
    two dies that share a ``.chiplet`` technology share one LEF and one ODB
    technology.

Running the exporter
--------------------

.. code-block:: bash

    python openroad/chiplet2dbx.py \
        --chiplet demo.chiplet \
        --out-dir build/3dblox

    # Bump-aware export: one pin list per die
    python openroad/chiplet2dbx.py \
        --chiplet demo.chiplet \
        --out-dir build/3dblox \
        --pins U1=chiplets/die_a.pins.json \
        --pins U2=chiplets/die_b.pins.json

.. literalinclude:: /adk/_usage/chiplet2dbx.txt
   :language: text

Exit status is 0 on success and 1 on any failure. There is no second failure
tier by design: a malformed field surfaces as
``chiplet2dbx: error: <message>`` and exit 1, never as a raw traceback.

What the output looks like
--------------------------

For a two-die demo assembly on a 1000 by 800 um interposer, the ``.3dbx``
placement and connection blocks read:

.. code-block:: yaml

    Design:
      name: "openroad_3dblox_demo"

    ChipletInst:
      interposer:
        reference: DEMO_INTERPOSER
      D1:
        reference: DIE_A
      D2:
        reference: DIE_B

    Stack:
      interposer:
        loc: [0, 0]
        z: 0
        orient: R0
      D1:
        loc: [100, 200]
        z: 54
        orient: MZ
      D2:
        loc: [600, 200]
        z: 54
        orient: MZ

    Connection:
      D1_attach:
        top: D1.regions.front
        bot: interposer.regions.front
        thickness: 44
      D2_attach:
        top: D2.regions.front
        bot: interposer.regions.front
        thickness: 44
      interposer_mount:
        top: interposer.regions.back
        bot: ~
        thickness: 0

Two conversions are visible there. ``.chiplet`` positions are geometric
centres and 3Dblox places by corner, so ``loc`` is the position minus half the
placed span; a quarter turn swaps the width and height spans before that
subtraction, because the centre stays put while the footprint rotates. And the
substrate carries a grounded ``<interposer>_mount`` connection with no ``bot``
so that the linter's floating-component check has a reference chip to anchor
the stack on.

Validation before export
------------------------

The exporter refuses to emit geometry it cannot represent faithfully. It never
rounds and never guesses.

z consistency, exactly
~~~~~~~~~~~~~~~~~~~~~~

The ``.chiplet`` z-mounting rule is
``z_die = mounting_surface + connection.total_height()``. OpenROAD's linter
asserts that a connection's declared thickness equals the actual gap between
the connected surfaces, exactly. The equality is guaranteed only when the die's
z was auto-calculated; a ``.chiplet`` may carry an explicit ``position.z``,
which readers honour as written.

So the exporter recomputes it. For every die it takes the connection stack
named by ``connection:``, sums the ``height`` of every layer in that stack, and
compares that total against ``position.z`` minus the mount surface z. The
tolerance is ``Z_TOLERANCE = 1e-6`` um, well below one database unit at any
realistic precision, so float noise passes and a real mismatch fails:

.. code-block:: text

    chiplet2dbx: error: die 'D1': z gap to the mount surface is 55 um but
    connection stack 'cupillar_opt1' totals 44 um; a .chiplet with explicit
    position.z must satisfy z == mount_surface + stack height exactly

A ``connection:`` id that does not resolve to a stack with layers, or a stack
layer without a ``height``, is likewise a hard error: there is no thickness
source, and inventing one would produce a model that loads and lints against
the wrong geometry.

.. note::

    Do not derive the die-to-substrate gap from outline maximum z: passivation
    can rise above the attachment plane, so a gap taken from the outline
    disagrees with the stack total and fails the exact-equality check.

Mounting on ``attachment_surface_z``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The mount surface is the interposer's component-level
``attachment_surface_z``: the BEOL-top die-attachment plane, decoupled from the
physical interposer body. Legacy ``.chiplet`` files that predate the field
encoded that surface in ``dimensions.thickness``, and the exporter falls back
to it when ``attachment_surface_z`` is absent. A non-positive
``attachment_surface_z`` is an error.

The die mount z is then the interposer's ``position.z`` plus that reference.
The same reference is used as the substrate def's thickness, because the
3Dblox substrate here is a thin mount plane, not a model of the interposer
body: the physical body is intentionally not modelled.

Rotation restricted to quarter turns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``rotation.z`` is normalised modulo 360 and must land on 0, 90, 180 or 270
within 1e-6 degrees. 3Dblox expresses only multiples of 90 degrees, so any
other angle fails loudly rather than being rounded to the nearest quarter turn.
A non-numeric or otherwise malformed ``rotation.z`` is reported as an export
error, not as a traceback.

Orientation, and why ``face_down`` is rejected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``.chiplet`` orientation and the rotation quarter compose into a **single**
3Dblox orientation token, never two attributes:

.. list-table::
    :header-rows: 1
    :widths: 30 30 40

    * - ``orientation``
      - ``rotation.z``
      - Emitted token
    * - ``face_up``
      - 0 / 90 / 180 / 270
      - ``R0`` / ``R90`` / ``R180`` / ``R270``
    * - ``flip_chip``
      - 0
      - ``MZ``
    * - ``flip_chip``
      - 90 / 180 / 270
      - ``MZ_R90`` / ``MZ_R180`` / ``MZ_R270``
    * - ``face_down``
      - any
      - rejected

``face_down`` records a distinct mounting intent whose 2D realisation the
``.chiplet`` format deliberately leaves to the writer. It is not a canonical
orientation token, so mapping it would mean pinning a convention the format
does not fix, and a wrong guess here silently mirrors an entire die. The
exporter rejects it and tells you to use ``flip_chip``. Any orientation value
other than ``face_up`` or ``flip_chip`` is also rejected. An absent
``orientation`` is read as ``face_up``, which is the format's own default.

The emitted token also decides which bond region attaches to the substrate:
``front`` for a flipped die, ``back`` otherwise.

The anchor requirement
~~~~~~~~~~~~~~~~~~~~~~

Every die must declare ``anchor: gds_origin`` explicitly. The exporter emits
die-local bump coordinates offset by the die ``position``, which is the
``gds_origin`` anchor semantics: the die GDS origin is the placement
reference.

- ``anchor: bbox_center`` is a hard error. Those bumps would need to be
  re-centred on the die GDS bounding box first, which this exporter does not
  do, and skipping that step misplaces every bump by the bbox-corner offset.
- An **absent** anchor is also a hard error. The coordinate frame contract
  defaults an absent anchor to ``bbox_center``, which is exactly the
  unsupported case, so guessing ``gds_origin`` would risk misplacing a genuine
  legacy file. Every die written by ``gds_to_kicad`` and by the KiCad plugin
  writer already emits the field. See :doc:`/formats/03_coordinate_frames`.

Other preconditions
~~~~~~~~~~~~~~~~~~~

- ``assembly.units`` must be ``um``. 3Dblox coordinates are microns.
- Exactly one component of type ``interposer``. Only ``die`` and
  ``interposer`` components are supported; anything else is an error.
- Every die needs ``dimensions.width``, ``height`` and ``thickness``, all
  strictly positive. For dies the physical thickness comes from the board's
  ``DIE_THICKNESS_UM`` field, and a zero or missing value says so in the error
  message rather than exporting a zero-height slab. The interposer needs
  ``width`` and ``height`` on the same terms; it needs ``thickness`` only on
  the legacy path, where it stands in for ``attachment_surface_z``.
- Every component needs a ``technology``: the generated technology LEF is named
  after it.
- All technologies must declare the same ``dbu``, and it must be an integer
  fraction of 1 um. The header ``precision`` is the resulting database units
  per micron; with no declared ``dbu`` it falls back to 1000.

Bump-aware export
-----------------

Passing ``--pins REF=PINS_JSON`` for a die turns its definition bump-aware.
The pin list is the ``*.pins.json`` artefact that ``gds_to_kicad`` extracts
from a die's GDS or footprint (see :doc:`/formats/07_pin_lists`). The die's def
then gains:

- a ``.bmap`` file listing every bump as
  ``bumpInstName bumpCellType x y portName netName``, with x and y being the
  bump centre in the def-local frame;
- a ``LEF_file`` reference to a bump macro LEF for that connection method,
  rendered by the interconnect PDK's ``bump_lef_generator``;
- a ``bmap:`` key on the def's ``front`` region.

Together these activate the linter's bump-alignment check.

``REF`` must name a die in the assembly, and that die must declare a
``connection`` method, since the bump map is keyed by method and the macro LEF
is rendered from it. A ``--pins`` reference that matches no die, and a die
given a pin list but no method, are both hard errors: either one means the
flags and the ``.chiplet`` disagree about which dies are bumped.

Pin coordinates in the artefact are die-local GDS database units
(``center_x_dbu``, ``center_y_dbu``), y-up, relative to the GDS origin;
``load_pinlist`` converts them to micrometres with the file's own ``dbu_um``,
which is why a pin list without ``dbu_um`` is rejected outright. The def-local
position is ``pin + dimensions/2``, mirrored
in x for ``flip_chip`` dies: this ecosystem realises the flip as a layout
mirror, while the target's flipped orientation leaves bump x and y unchanged.
A pin that lands outside the declared outline is a hard error naming the
offending pins, because it means the pin list and the dimensions describe
different dies.

Port and net columns are emitted only when the ``.chiplet`` ``netlist:`` block
binds the pad name to a net. Otherwise both columns are ``-``, since the target
warns on a port declared without a net.

.. note::

    A bump map is a property of the ``ChipletDef``, not of the instance. Two
    dies that share artwork but differ in connection method or in net binding
    therefore split into separate defs. Giving two dies that resolve to the
    same def different pin lists is an error rather than a silent last-writer
    wins.

The bump LEF generator lives in the interconnect PDK, not in the ADK. It is
discovered through ``INTERCONNECT_PDK_ROOT`` first, then by walking upward for
a sibling checkout named ``interconnect_pdk`` or
``IHP-Interconnect-IntM4TM2``. When pin lists are supplied and no generator is
found, the export fails loudly with the variable to set: a bump-aware export
silently degraded to a bumpless one would lint clean and mean nothing. A
connection method that is not in the interconnect PDK manifest is likewise a
hard error. See :doc:`/tools/06_interconnect_pdk`.

Loading the result in OpenROAD
------------------------------

``read_3dbx`` on the ``.3dbx`` loads the assembly; the ``.3dbv`` and the LEFs
are pulled in through the header ``include`` and the ``APR_tech_file`` and
``LEF_file`` references, so keep the whole output directory together.

.. code-block:: tcl

    read_3dbx openroad_3dblox_demo.3dbx
    check_3dblox

Run it from the export directory, since the references are by filename.

``check_3dblox`` is the assembly linter. It covers floating components, 3D
overlap, connection-region validity, bump alignment, internal-extension usage,
logical connectivity against a declared netlist, and alignment markers. It
reports findings as OpenROAD ``[WARNING ...]`` and ``[ERROR ...]`` lines, which
means a wrapper that only checks the process exit status will not notice a
geometry finding. Grep the log for those prefixes if you want a flow step to
fail on findings.

.. tip::

    Two of the exporter's guarantees are worth exercising once, so the failure
    mode is familiar. Change a die's ``position.z`` by one micron in the
    ``.chiplet`` and the **export** fails, before OpenROAD is ever started.
    Hand-edit the same ``z:`` in the generated ``.3dbx`` instead and the same
    rule is caught on the other side: ``check_3dblox`` reports an invalid
    connection.

Importable entry points
-----------------------

.. code-block:: python

    load_chiplet(path) -> dict
    load_pinlist(path) -> [{"name", "x_um", "y_um"}, ...]
    render_3dbv(assembly, *, die_pins=None) -> str
    render_3dbx(assembly, dbv_filename, *, die_pins=None) -> str
    render_bmap(assembly, def_name, *, die_pins=None) -> str
    render_tech_lef(precision, route_layer=None) -> str
    export_3dblox(assembly, out_dir, name=None, die_pins=None)
        -> (dbv_path, dbx_path, [extra_paths])

The three renderers take ``die_pins`` keyword-only; ``export_3dblox`` takes it
as an ordinary keyword argument.

``export_3dblox`` accepts ``die_pins`` values as either a path to a
``*.pins.json`` or an already-parsed pin list. As everywhere in the ADK, new
options are appended as trailing keyword arguments with defaults, so importers
stay source-compatible.

``ExportError`` is the exception type every faithfulness failure raises. It
subclasses ``ValueError``.
