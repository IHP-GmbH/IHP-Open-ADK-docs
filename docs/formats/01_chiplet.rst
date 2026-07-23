The .chiplet assembly file
==========================

.. include:: /common.inc
.. include:: _vendored_state.inc

``.chiplet`` is the pivot format of the whole ADK ecosystem. Every tool
described on this site either writes one, reads one, or is driven by flags
derived from one: the KiCad exporter and the ``hyp_to_gds`` finalizer write it,
Chiplet Studio and the ``pads_vs_pillars`` check read it, the pipeline
orchestrator reads its adapter axes to build the DRC command line, and
``chiplet2dbx`` translates it into 3Dblox.

The format is YAML, the current ``format_version`` is ``"1.0"``, and the
specification lives in the |spec-repo| repository at
``docs/CHIPLET_FORMAT_SPEC.md``, alongside the normative coordinate-frame
contract described in :doc:`/formats/03_coordinate_frames`.

.. note::

    The schema described on this page and on
    :doc:`/formats/02_chiplet_components` is the whole of ``format_version``
    ``"1.0"``.
    The 2026 revisions to the specification document did not change the
    on-disk format; they wrote down parts of the existing schema that had
    never been documented, and added one new optional field
    (``attachment_surface_z``) with a backward-compatible fallback.


What the format is for
----------------------

``.chiplet`` is a **physical-assembly layout** format. It answers three
questions and no others:

- where each die, interposer and substrate sits in one shared coordinate
  frame;
- how each die is z-mounted onto its interconnect;
- which GDS or OASIS body and which layer properties each component carries.

Those are exactly the inputs an assembly viewer and an assembly DRC flow need.
The format is the interchange pivot between PCB-style design entry (KiCad) and
a mask-level 3D assembly and DRC environment.

It is deliberately **not** a chiplet IP datasheet and not a marketplace or
sourcing format. It models nothing electrical, functional, thermal, protocol
related or test related about a chiplet. That information belongs to a
part-description standard, and standards for it already exist.

Relationship to CDXML, JEP30 and 3Dblox
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The specification frames the three format families as stages of one flow, not
as competitors.

**CDXML** (Chiplet Data Exchange in XML) is a per-chiplet, machine-readable
datasheet: pinout, mechanical envelope, electrical and ESD ratings, and D2D
interface type. It was developed in OCP/ODSA and published under CC0-1.0, and
its capabilities were folded into JEDEC's **JEP30** PartModel, which is now the
active vehicle for that part-model data. By its own scope CDXML carries no
inter-die placement: its only coordinates are pad positions inside a single
part.

**3Dblox**, originated by TSMC and being standardised as **IEEE P3537**,
describes multi-die physical assemblies at the same layer as ``.chiplet``, but
bound to a different abstraction level. It has an open-source BSD-3
implementation in OpenROAD (ingestion, an automatic assembly linter, and a 3D
viewer). 3Dblox binds an assembly to the place-and-route abstraction (LEF, DEF,
Verilog netlists, Liberty views) for multi-die EDA and design-space
exploration, and references no artwork files. ``.chiplet`` binds the same
assembly to the mask level: GDS/OASIS bodies, ``.lyp`` layer properties,
per-layer interconnect metallurgy with method identity, and fab DRC parameters.

.. list-table:: Where each format sits
    :header-rows: 1
    :widths: 16 28 28 28
    :class: adk-wide-table

    * -
      - Part description (CDXML, JEP30)
      - Assembly for P&R and exploration (3Dblox, P3537)
      - ``.chiplet``
    * - Answers
      - what is this part (datasheet)
      - how dies stack and connect, over P&R views
      - placed where, z-mounted how, mask-level DRC-ready
    * - Coordinates
      - per-pin pad x/y within one die
      - per-die 3D placement plus bump maps over LEF geometry
      - per-component placement in a shared interposer frame; bodies as
        GDS/OASIS
    * - Stage
      - part selection and sourcing
      - multi-die EDA and design-space exploration
      - physical assembly and fabrication hand-off DRC

The pipeline follows the table: select a part described by CDXML or JEP30, place
and z-mount it in a ``.chiplet`` assembly, run assembly DRC, and derive a 3Dblox
view for P&R-level exploration. A component may carry an optional ``cdxml_ref``
or ``3dblox_ref`` citing the corresponding part or ``ChipletDef``; both are
proposed extensions rather than v1.0 schema fields, described on
:doc:`/formats/02_chiplet_components`.

The canonical source of truth for each layer stays where it belongs: part data
in CDXML or JEP30, P&R views in LEF/DEF and 3Dblox, mask-level placement in
``.chiplet``. A derived ``.3dbx`` assembly file is an export artefact, never a
second source of truth for placement. :doc:`/formats/08_3dblox_interop`
develops that mapping in full.


File structure
--------------

A ``.chiplet`` file always carries ``format_version`` and an ``assembly``
block. Every other top-level block is optional. The reference reader recognises
ten top-level keys.

.. list-table:: Root-level keys
    :header-rows: 1
    :widths: 20 10 14 56
    :class: adk-wide-table

    * - Key
      - Required
      - Type
      - Description
    * - ``format_version``
      - yes
      - string
      - Format version, currently ``"1.0"``. A different value is a hard
        error.
    * - ``assembly``
      - yes
      - object
      - Assembly metadata. ``assembly.name`` must be non-empty.
    * - ``technologies``
      - no
      - map
      - Technology definitions, keyed by technology id.
    * - ``connection_stacks``
      - no
      - map
      - Named interconnect stacks, keyed by method id.
    * - ``components``
      - no
      - array
      - The placed components.
    * - ``interconnect``
      - no
      - object
      - Interconnect-axis adapter and optional technology.
    * - ``interfaces``
      - no
      - array
      - Typed die-to-die and bond interfaces.
    * - ``netlist``
      - no
      - object
      - Optional assembly netlist, inline or by reference.
    * - ``flow``
      - no
      - object
      - Opaque build/flow block, preserved verbatim.
    * - ``_metadata``
      - no
      - object
      - Intermediate-file marker. Canonical files carry none.

Key order is not significant: readers are key driven and accept the sections in
any order. The reference writer emits them in the order ``format_version``,
``_metadata``, ``assembly``, ``technologies``, ``interconnect``,
``connection_stacks``, ``components``, ``interfaces``, ``netlist``, ``flow``.

The rest of this page covers the three blocks that describe the assembly as a
whole, the path convention, and what a conforming reader and writer must do.
``components`` and the five optional blocks are on
:doc:`/formats/02_chiplet_components`.

.. note::

    The ADK toolchain writes one additional top-level block that the
    specification does not list: ``interposer:`` with a single ``adapter:``
    field, naming the interposer DRC adapter for the assembly. The reference
    reader does not model it, does not reject it, and round-trips it with the
    rest of the document. The pipeline orchestrator reads it to build the
    ``--interposer-adapter`` flag; see :doc:`/adk/02_adapter_contract`.


The assembly block
------------------

Metadata about the package as a whole.

.. list-table:: ``assembly`` fields
    :header-rows: 1
    :widths: 22 10 14 54
    :class: adk-wide-table

    * - Key
      - Required
      - Default
      - Description
    * - ``name``
      - yes
      -
      - Display name of the assembly.
    * - ``description``
      - no
      - ``""``
      - Long-form description.
    * - ``author``
      - no
      - ``""``
      - Author or designer name.
    * - ``created``
      - no
      - ``""``
      - Creation date, ISO 8601.
    * - ``modified``
      - no
      - ``""``
      - Last modification date, ISO 8601.
    * - ``units``
      - no
      - ``""``
      - Unit of measurement. The format sets no default; tools conventionally
        write ``um``, and the ADK checks accept only ``um``.
    * - ``assembly_gds``
      - no
      - ``""``
      - Path to a merged or flattened GDS of the whole assembly, when one is
        produced.
    * - ``io_technology``
      - no
      - ``""``
      - Technology id used for assembly-level I/O pads.

.. tip::

    Write ``units: um`` even though the format does not require it. The two
    ADK consumers treat the field differently, and the stricter one is the
    reason to write it: ``chiplet2dbx`` requires ``assembly.units`` to be
    exactly ``um`` and rejects an absent key along with a wrong one, so an
    export stops on a file that never declared its units.
    ``pads_vs_pillars`` rejects a non-``um`` value but tolerates an absent
    one. Neither will convert: a millimetre assembly compared as micrometres
    would pass at a thousand times scale, which is why both refuse rather
    than scale.


The technologies block
----------------------

A map from technology id to a technology definition. The id is the map key and
must be unique within the file; components reference it through their
``technology`` field.

.. list-table:: ``technologies.<id>`` fields
    :header-rows: 1
    :widths: 24 10 14 52
    :class: adk-wide-table

    * - Key
      - Required
      - Default
      - Description
    * - ``description``
      - no
      - ``""``
      - Human-readable technology description.
    * - ``layer_properties``
      - no
      - ``""``
      - Path to a KLayout ``.lyp`` file.
    * - ``dbu``
      - no
      - ``0.001``
      - Database unit in micrometres, that is, the coordinate resolution of the
        referenced layout files.

``dbu`` matters beyond rendering. ``chiplet2dbx`` derives the 3Dblox header
precision from it, requires every technology in the file to agree on one value,
and fails the export when ``1 / dbu`` is not an integer.


The connection_stacks block
---------------------------

A map from interconnect method id to the physical stack a die's bumps or
pillars are built from. A die selects one by id through its ``connection``
field, and the sum of the layer heights is what lifts that die off the
interposer.

.. code-block:: yaml

    connection_stacks:
      cupillar_opt1:
        description: "Cu pillar, Table 6.1 Option 1 (35 um opening)"
        layers:
          - {name: CuPillar, material: Cu,   height: 28.0, diameter: 44.0}
          - {name: SnAgCap,  material: SnAg, height: 16.0, diameter: 44.0}

.. list-table:: ``connection_stacks.<id>`` fields
    :header-rows: 1
    :widths: 26 12 62
    :class: adk-wide-table

    * - Key
      - Type
      - Description
    * - ``description``
      - string
      - Human-readable description.
    * - ``layers``
      - array
      - Ordered stack layers, bottom (interposer side) first.
    * - ``layers[].name``
      - string
      - Layer name, matched against the interposer stackup to resolve the
        mounting surface.
    * - ``layers[].material``
      - string
      - Material, for example ``Cu``, ``SnAg``, ``SAC305``.
    * - ``layers[].height``
      - float, um
      - Layer height. The stack total drives z-mounting.
    * - ``layers[].diameter``
      - float, um
      - Body diameter.

In the reference toolchain the same stacks are published in the
``interconnect_methods.json`` sidecar, which is the single source of truth for
the interconnect PDK (see :doc:`/formats/06_ixn_methods`). A ``.chiplet`` file
may inline the resolved stacks here so that it is self-contained, and the
exporters do exactly that: the reference design inlines every method the
registry publishes (three Cu-pillar options, a SAC305 solder bump, and the
demo vendor microbump), whether or not each one is used by a die.


Paths and the ${VAR} convention
-------------------------------

Relative paths resolve against the directory containing the ``.chiplet`` file.
Absolute paths are used as-is. Supported layout formats are GDS, GDS2 and
OASIS.

The finalizer references a layout that already sits inside the ``.chiplet``
file's own directory relatively, so a colocated export set survives being
moved, copied or committed. Anything outside that directory keeps an absolute
path, because a ``.chiplet`` file is machine-local unless the board data opts
into something portable. To make a file portable across checkouts, path inputs
may reference an ecosystem root with ``${VAR}`` syntax. The convention applies
to
``technologies.*.layer_properties`` and ``components[].layout``, and it comes
in through the KiCad board text variables and footprint fields that flow into
them.

.. code-block:: yaml

    technologies:
      intm4tm2:
        layer_properties: ${INTERPOSER_PDK_ROOT}/libs.tech/klayout/tech/intm4tm2.lyp
      sg13g2:
        layer_properties: ${GDS_TO_KICAD_ROOT}/pdks/sg13g2.lyp

The division of labour is strict:

- **Writers copy the value verbatim.** The KiCad C++ exporter and the Python
  plugin writer have zero emission logic here, which is what keeps them
  byte-identical to each other under the parity gate.
- **Readers expand on read**, using the discovery chain: environment variable
  first, then an upward walk for a conventional sibling checkout, then loud
  failure naming the variable. A set-but-invalid environment value (the marker
  subdirectory is missing) falls through to the walk rather than winning.

Expansion is restricted to five known ecosystem roots: ``ADK_ROOT``,
``INTERPOSER_PDK_ROOT``, ``INTERCONNECT_PDK_ROOT``, ``GDS_TO_KICAD_ROOT`` and
``PDK_ROOT``. An unknown ``${NAME}`` is treated as a typo and fails, rather
than as licence to read arbitrary environment variables. A path that silently
kept a literal ``${VAR}`` component would simply "not exist" downstream and
mask the real problem, so unresolvable references abort with the variable name
in the message.

:doc:`/install/03_environment` lists the variables, what each root must contain
for the discovery walk to accept it, and how to set them.


Validation rules
----------------

The reference libraries enforce a small set of structural invariants across the
whole file, including the component fields defined on
:doc:`/formats/02_chiplet_components`. Everything that needs the filesystem or
cross-reference resolution is left to the consuming tool, because the libraries
never touch the filesystem.

Hard errors in the reference validator:

1. ``format_version`` must be ``"1.0"``.
2. ``assembly.name`` is required and must not be empty.
3. Every component has a non-empty ``id`` and a non-empty ``type``.
4. Every ``interfaces[]`` entry has an ``id`` and a ``type``, and the type is
   one of ``micro_bump``, ``copper_pillar``, ``tsv``, ``wire_bond``. C++
   reference only; the Python validator accepts an unknown type.
5. Every ``netlist.nets[]`` entry has a ``name``. C++ reference only; the
   Python validator accepts a nameless net.
6. A file whose ``_metadata.finalize_required`` is ``true`` is refused unless
   intermediate files are explicitly allowed.

Reader behaviour that warns or falls back rather than failing:

7. New files should declare ``anchor`` on every component. A reader defaults an
   absent ``anchor`` to ``bbox_center`` and warns.
8. An absent or unresolved ``connection`` falls back to the interposer's
   ``attachment_surface_z``, or to ``dimensions.thickness`` when that field is
   absent.
9. A reader must warn, or reject, when any ``position.x`` or ``position.y``
   exceeds 1e5 um in magnitude. This is the leak guard for un-converted
   absolute coordinates.

Consumer-level expectations, not enforced by the reference library:

10. Component ``id`` values are unique.
11. Component ``type`` is one of the four canonical values.
12. A ``technology`` reference names a defined technology id.
13. A ``layout`` or ``layer_properties`` path exists at the resolved location.


Reading and writing .chiplet files
----------------------------------

The specification ships two reference implementations under
``reference/``, both named ``chiplet-format-io`` and both Apache-2.0:

- **Python**, ``reference/python/chiplet_format_io``. Depends on PyYAML and
  nothing else. It deliberately does not import ``pcbnew``, ``klayout`` or any
  other GPL library, so it can be embedded in a tool under any license.
- **C++**, ``reference/cpp/``. Depends on yaml-cpp only. It parses into plain
  value structs, which is why it round-trips exactly the fields it models and
  drops the ones it does not.

Both are **structural only** by design. They parse, validate and round-trip the
schema: the ``format_version`` gate, the intermediate-file guard, the
structural shape, and ``anchor`` as a raw string. They do **not** implement
anchor defaulting, the 1e5 range check, mesh centring or z-mounting. Those
frame semantics are a consumer responsibility, defined by
:doc:`/formats/03_coordinate_frames` and demonstrated by Chiplet Studio.

.. note::

    Using a reference library is not by itself conformance to the reader
    contract. A reader that loads a file with ``cfio.load`` and then places
    geometry has satisfied the schema and none of the frame semantics. The
    range check and the anchor handling have to be added on top.

The Python API is four functions plus a validator:

.. code-block:: python

    import chiplet_format_io as cfio

    assembly = cfio.load("design.chiplet")       # -> dict, validated
    assembly["assembly"]["name"] = "renamed"
    cfio.dump(assembly, "design.chiplet")

``loads`` and ``dumps`` are the string forms, ``validate`` checks an
already-parsed mapping. ``load`` and ``loads`` take ``allow_intermediate`` to
permit a ``finalize_required`` document, and ``validate=False`` to skip
checking entirely. ``dumps`` preserves key insertion order and emits canonical
YAML.

The output is semantically equivalent to, but not byte-identical to, what the
GPL host tools write. The KiCad fork exporter and the KiCad plugin writer are
locked to each other by a byte-exact parity gate; the reference library is an
independent implementation of the same specification and does not participate
in that gate.

The ADK vendors the Python library at ``vendor/chiplet_format_io/`` and reaches
it by putting ``vendor/`` on ``sys.path``. The vendored copy is
|vendored-reader-state|. ``chiplet2dbx`` imports it and re-exports
``load_chiplet``; ``pads_vs_pillars`` imports ``chiplet2dbx`` first so that the
vendored package is on the path, then imports the library itself, so that there
is one copy on the path and one import home rather than two.

Implementer rights
~~~~~~~~~~~~~~~~~~

The formats are published in a repository that is deliberately separate from
any implementing tool. The reference tools that read and write them (the KiCad
fork, the Chiplet Studio viewer, the KiCad plugin) are GPL because they link or
derive from GPL software. The formats are not.

Everything in the specification repository is licensed under the Apache
License 2.0, and IHP makes an explicit additional grant: anyone may implement
readers, writers, converters or any other tools that consume or produce files
in these formats, under **any** license of their choosing, open source or
proprietary, royalty free. IHP asserts no patents over the formats themselves
and will not use patents it may hold to prevent conformant implementations.
Apache-2.0's patent grant in Section 3 applies to the material in the
repository.

The practical consequence: a GPL constraint can only ever reach you through a
*tool* you chose to build on, for example by embedding KiCad or KLayout. It
never reaches you through the format.


Where to go next
----------------

- :doc:`/formats/02_chiplet_components` for the ``components`` block, the
  optional blocks and a complete worked file.
- :doc:`/formats/03_coordinate_frames` for the normative frame, anchor and
  z-mounting semantics that these two pages summarise.
- :doc:`/formats/04_boundary_manifest` and
  :doc:`/formats/05_pillar_manifest` for the sidecars that travel with an
  assembly GDS.
- :doc:`/formats/06_ixn_methods` for the interconnect method registry that
  ``connection`` ids resolve against.
- :doc:`/formats/08_3dblox_interop` and :doc:`/adk/07_chiplet2dbx` for the
  3Dblox export.
- :doc:`/flow/02_die_to_kicad` and :doc:`/flow/04_export` for where in the flow
  the file is written.
