Registries and schemas
======================

.. include:: /common.inc
.. include:: tables/_rule_counts.inc

Every number the ADK's own rule decks check, and every layer number the ADK core
still knows, lives in a small JSON registry under ``config/`` in the ADK
repository. PDK-specific layer numbers and per-method numbers live in adapters,
which is the point of the adapter axes. Nothing
normative is hardcoded in a rule deck or in a generator. This page describes each
registry, who reads it, and what its values are worth.

Alongside the registries, ``config/schema/`` holds the JSON Schemas: three that
describe the registries themselves, and three that describe the per-assembly
sidecar files the toolchain exchanges.

Version discipline
------------------

All four registries carry a ``version`` key, and all four read
|adk-config-version| today. That is not a coincidence maintained by hand: a test
in the ADK reads the first released heading in ``CHANGELOG.md`` and asserts that
the ``VERSION`` file and every ``config/*.json`` version key equal it. A skew
between them fails CI.

The sidecar schemas version independently, because they describe a data contract
between separate tools rather than the ADK release. All three currently stand at
``1.0.0``, and their readers pin them **exactly**: a boundary manifest, a
per-method interconnect file or a pillar manifest whose ``version`` is anything
other than the pinned string is rejected rather than best-effort parsed. See
:doc:`/tools/07_adk_tools_image` for the full version matrix.

.. note::
   The registries are also baked into the ADK-Tools container image, which is
   why the schema files are committed rather than generated. A container built
   from a given ADK commit validates against exactly that commit's schemas.

config/rule_params.json
-----------------------

The assembly-placement parameter registry: the numbers the ``ASM`` rules use.

**Consumers.** ``klayout/drc/adk_assembly.drc`` loads it into the ``drc_rules``
dictionary, which the interposer adapter may then override and which
``8_1_assembly.drc`` reads. ``kicad/dru/generate_assembly_dru.py`` loads the same
file as its defaults. Both consumers apply adapter overrides, which is what makes
the KLayout and KiCad checks agree. See :doc:`/adk/02_adapter_contract`.

.. csv-table:: Assembly rule parameters
    :file: tables/asm_params.csv
    :header: "Key", "Meaning", "Default", "Unit"
    :widths: 14 58 14 14
    :class: adk-rule-table
    :align: left

.. warning::
   ``ASM_b`` and ``ASM_e`` are **engineering defaults with no recorded
   provenance in the registry**. The registry's own description calls them
   parameter defaults, and no foundry document, assembly-house specification or
   qualification report is cited for either value anywhere in the source. Treat
   50 um of chiplet-to-chiplet spacing and 10000 um2 of minimum chiplet area as
   sane starting points that make the rules do something useful on a plausible
   assembly, not as manufacturing constraints. Override them from your
   interposer adapter when you have numbers that are actually justified.

``ASM_e`` in particular is a sanity check rather than a constraint: it exists to
catch degenerate boundary polygons, a chiplet outline that collapsed to a sliver
during a transform, not to express a real minimum die size.

config/interconnect.json
------------------------

The interconnect-axis parameter registry: the numbers the ``IXN`` rules use when
no adapter overrides them.

**Consumers.** ``klayout/drc/adk_assembly.drc`` loads it into
``interconnect_rules`` when the file exists, and tolerates its absence so that a
partial checkout still runs the interposer-only path.
``rule_decks/8_2_interconnect.drc`` reads the dictionary, but only when the
interconnect axis is active at all. ``generate_assembly_dru.py`` also loads it,
for the documented render signature, but the KiCad template emits no ``IXN``
constraint: the interconnect checks are post-layout geometry checks with no
KiCad equivalent, so only the adapter name reaches the generated file, as a
provenance comment.

.. csv-table:: Interconnect rule parameters
    :file: tables/ixn_params.csv
    :header: "Key", "Meaning", "Default", "Unit"
    :widths: 14 58 14 14
    :class: adk-rule-table
    :align: left

Unlike the ``ASM`` defaults, these numbers have recorded provenance, stated in
the registry's own description: they mirror the IHP Cu-pillar default option in
the bumping vendor's table, a 35 um passivation opening, 40 um edge-to-edge space
and 75 um pitch. The interposer PDK's ``Padc_a``, ``Padc_b`` and ``Padc_e`` carry
the same three numbers, so the interposer stage and the assembly stage of the
two-stage DRC check the same values.

Designs using the larger Cu-pillar options are checked against this conservative
floor, exactly as they are at the interposer stage. Option-specific adapters are
trivial copies with that option's values from the same table, and can be added
when a design needs option-specific checking. :doc:`/adk/04_ixn_rules` describes
how the pitch value becomes a spacing check.

config/layers.json
------------------

A layer registry that exists for backward compatibility and nothing else.

It contains one entry, ``exchange0`` at GDS 190/0, the historical fabrication
location of the chiplet boundary. The default path never touches it: the boundary
travels in the per-assembly manifest, outside any fabrication-layer namespace.

**Consumers.** ``adk_assembly.drc`` loads the file unconditionally and raises if
it is missing, but only ``layers_def.drc`` consults the ``exchange0`` entry, and
only when the deck runs with ``legacy_exchange0`` set, which the runner flag
``--legacy-exchange0`` does:

.. code-block:: ruby

    if defined?(legacy_exchange0) && legacy_exchange0
      exchange0_layer  = adk_layers['exchange0']
      chiplet_boundary = polygons(exchange0_layer['gds_layer'],
                                  exchange0_layer['gds_datatype'])
    else
      chiplet_boundary = polygon_layer
      # ... polygons inserted from the injected boundary manifest
    end

The KiCad DRU generator does not read the file at all. Bumping its ``version``
key has no effect on the contract; only its ``layers`` key is ever read, and only
on that one path. :doc:`/formats/04_boundary_manifest` describes what replaced
it.

config/chiplet_pads.json
------------------------

The canonical chiplet-internal pad vocabulary.

.. list-table::
    :header-rows: 1
    :widths: 20 14 66

    * - Name
      - GDS
      - Purpose
    * - ``pad_drawing``
      - 205/0
      - Bond-pad metal geometry on a black-box or pads-only chiplet, one
        polygon per pad.
    * - ``pad_text``
      - 205/25
      - Pad-name text labels, associated to pads by proximity. Datatype 25
        mirrors the PDK ``.text`` convention, so the existing text auto-pairing
        works unchanged.
    * - ``outline``
      - 206/0
      - Die mechanical outline, one polygon.

.. note::
   This registry is **producer-side vocabulary, not an assembly check**. No ADK
   rule reads it, and no assembly verdict depends on it. It says what the
   black-box generator writes and what a downstream reader may assume when it is
   told the geometry came from that generator. Do not read it as "the layers a
   chiplet must use".

Two things follow from that framing, and both are in the registry's own
description:

* The **input** side never consults this file. Reading an arbitrary commercial
  pads-only GDS, whose layer numbers are unknown, is handled by an explicit
  ``--pad-layer-number`` or by densest-layer auto-detection, not by assuming
  205/0.
* The numbers 205 and 206 were chosen deliberately in a band the reference
  interposer PDK leaves free. IHP SG13G2 uses the Exchange family at 190 to 194
  and layer 257, so 195 to 256 is unassigned, and a black-box chiplet's synthetic
  pad and outline geometry cannot alias a real interposer fabrication layer in an
  assembled GDS. A guard test in ``gds2kicad`` pins this against the IHP layer
  set, and a test in the ADK pins the registry's own shape.

The one reader on the checking side is ``checks/pads_vs_pillars.py``, which uses
the vocabulary to extract pad positions from a die layout when no pin list is
available. That is still consumption of producer-side geometry, not an assembly
rule: layer numbers are never hardcoded in the check, they come from here. See
:doc:`/adk/08_pads_vs_pillars`.

Finally, note what the registry says about the outline: the black-box generator
records the die outline as the chiplet boundary in the ``.boundaries.json``
manifest, and it is **no longer mirrored onto** ``exchange0``. The 206/0 outline
is a drawing convenience for the chiplet's own GDS; the manifest is what the
assembly DRC reads.

Registry schemas
----------------

The three registry schemas are validated against their data in CI, so the
committed schema files cannot drift from the registries they describe.

Rule parameter registry
~~~~~~~~~~~~~~~~~~~~~~~

``config/schema/rule_params.schema.json``. Note the closed ``additionalProperties``
on ``rules``: a key that does not match the uppercase-initial pattern is a schema
error, not an ignored extra.

.. literalinclude:: /../src/IHP-Open-ADK/config/schema/rule_params.schema.json
    :language: json

Interconnect registry
~~~~~~~~~~~~~~~~~~~~~

``config/schema/interconnect.schema.json``. Structurally identical to the rule
parameter schema, kept separate so the two registries can diverge without a
coupled edit.

.. literalinclude:: /../src/IHP-Open-ADK/config/schema/interconnect.schema.json
    :language: json

Layer registry
~~~~~~~~~~~~~~

``config/schema/layers.schema.json``. It constrains both ``config/layers.json``
and, by convention, ``config/chiplet_pads.json``, which the ADK test suite checks
against the same constraints without requiring a ``jsonschema`` dependency.

.. literalinclude:: /../src/IHP-Open-ADK/config/schema/layers.schema.json
    :language: json

Sidecar schemas
---------------

Three further schemas describe per-assembly files that travel next to an
assembly GDS rather than living in ``config/``. They are data contracts between
separate tools, so their readers pin the schema string and the version exactly.
Each is listed on the page that owns it:

.. list-table::
    :header-rows: 1
    :widths: 34 26 40

    * - Schema file
      - Schema string
      - Normative page
    * - ``boundary_manifest.schema.json``
      - ``adk-boundary-manifest``
      - :doc:`/formats/04_boundary_manifest`
    * - ``pillar_manifest.schema.json``
      - ``adk-pillar-manifest``
      - :doc:`/formats/05_pillar_manifest`
    * - ``ixn_methods.schema.json``
      - ``adk-ixn-methods``
      - :doc:`/formats/06_ixn_methods`

Changing a registry
-------------------

* **Changing a value.** Edit the registry, and expect the generated rule and
  parameter tables in this documentation to change with it. The documentation
  generators read the pinned submodule, and CI fails if the committed tables no
  longer match.
* **Adding a rule parameter.** Add the key and a matching entry in
  ``rule_descriptions``. The description is not decoration: the table generators
  fail the documentation build when a parameter has no description.
* **Adding a layer entry.** Only ``config/layers.json`` and
  ``config/chiplet_pads.json`` have a layers shape, and neither is the right
  home for a new assembly-level concept. If a new piece of per-assembly data is
  needed, it belongs in a sidecar with its own schema and its own version pin,
  for the reasons the ``exchange0`` migration records above.
* **Bumping a version.** The four registry ``version`` keys move together with
  ``VERSION`` and the ``CHANGELOG.md`` heading, and the consistency test enforces
  it. Sidecar schema versions move on their own, and a bump there means every
  reader's exact-match pin must be updated in the same change.
