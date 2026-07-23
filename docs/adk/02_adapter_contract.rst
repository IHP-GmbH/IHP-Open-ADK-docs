Adapter contract
================

.. include:: /common.inc

A PDK or an interconnect vendor ships an adapter so that the ADK can check an
assembly without baking that vendor's layer numbers into the rule deck. The
adapter is the only place a fabrication layer number may enter the rule path.
Two registries still record layer numbers outside it: ``config/layers.json``,
for the legacy ``--legacy-exchange0`` boundary source, and
``config/chiplet_pads.json``, for the producer-side black-box pad vocabulary.

There are two axes, and they are independent:

* the **interposer** adapter, required, declares *where* chiplet attachment
  lands on the substrate;
* the **interconnect** adapter, optional, supplies the *method* rules, the
  bump-to-bump pitch and spacing.

The interconnect axis is purely additive. With no interconnect adapter and no
per-method file, the eval chain and the output are identical to the
interposer-only deck. See :ref:`adk_architecture_eval_chain`.

.. tip::
   Adapters are plain Ruby, concatenated into the deck source and evaluated in
   the same scope as the rule decks. That is why they can assign to
   ``drc_rules`` directly, and also why they must stay self-contained: there is
   no module boundary protecting the deck from what an adapter does.

Interposer adapter
------------------

Location and selection
~~~~~~~~~~~~~~~~~~~~~~

An interposer adapter is a single file::

    pdk_adapters/interposer/<basename>.drc

The ``--interposer-adapter`` flag of the DRC runner accepts either form:

* a **shortname**, resolved against ``pdk_adapters/interposer/``, so
  ``intm4tm2`` loads ``pdk_adapters/interposer/intm4tm2.drc``;
* an **explicit path** to a ``.drc`` file, absolute or relative, used as-is.

The resolver tries the literal path first, and only if that is not an existing
``.drc`` file does it fall back to the shortname lookup. A trailing ``.drc`` on a
shortname is stripped, so ``intm4tm2`` and ``intm4tm2.drc`` both work. If neither
resolves, the runner reports both the literal path and the directory candidate it
looked for, and exits.

The same resolution is implemented in the KiCad DRU generator,
``kicad/dru/generate_assembly_dru.py``, so both toolchains select an adapter by
the same name.

Through the KiCad plugin orchestrator the adapter comes from the assembly file
instead of the command line: a top-level ``interposer.adapter`` field in the
``.chiplet``, falling back to ``intm4tm2`` when the file, the block or the field
is absent.

.. code-block:: yaml

    interposer:
      adapter: "intm4tm2"

Shipped interposer adapters
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. csv-table:: Interposer adapters shipped with the ADK
    :file: tables/interposer_adapters.csv
    :header: "Adapter", "Interposer", "Declares"
    :widths: 18 42 40
    :class: adk-rule-table
    :align: left

Required abstract inputs
~~~~~~~~~~~~~~~~~~~~~~~~

Every interposer adapter MUST declare the required abstract inputs as KLayout
layer expressions in its top-level scope. Today the list has exactly one entry.

``chiplet_attachment_input``
    The region representing the area on the interposer through which chiplet
    attachment happens. The physical mechanism is unspecified: Cu pillars,
    solder bumps, hybrid-bonding pad arrays are all acceptable, as long as the
    resulting region accurately models *where attachment can land*.

.. code-block:: ruby

    passiv_pillar = polygons(9, 35)
    dfpad_pillar  = polygons(41, 35)

    chiplet_attachment_input = passiv_pillar.and(dfpad_pillar)

The **KLayout deck validates this, not the runner**. The runner only resolves the
adapter path and shells out to KLayout. After the adapter source is evaluated,
the deck raises unless every required input is both ``defined?`` and non-nil,
aborting the run with an error that names the missing input and the adapter file
that should have declared it. The required list itself is one line in
``klayout/drc/adk_assembly.drc``:

.. code-block:: ruby

    required_inputs = ['chiplet_attachment_input']

Optional rule-parameter overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An adapter MAY override entries in the ``drc_rules`` dictionary, which the deck
loads from ``config/rule_params.json`` before the adapter runs:

.. code-block:: ruby

    drc_rules['ASM_b'] = 30.0  # tighter chiplet spacing on this interposer

Both consumers honour the override, but by different mechanisms. The KLayout
deck simply reads the mutated dictionary. The KiCad DRU generator does not
evaluate Ruby: it scans the adapter file for literal numeric assignments of the
form ``drc_rules['NAME'] = NUMBER`` and merges what it finds on top of the
registry defaults, and it does so only when invoked with
``--interposer-adapter <name>``. Two consequences follow:

* a computed override, for example ``drc_rules['ASM_b'] = base * 0.6``, is
  honoured by KLayout and silently ignored by the DRU generator;
* an override targeting a key that is not in ``config/rule_params.json``, or a
  negative value, is rejected by the generator with an error rather than passed
  through.

Keep overrides to plain positive numeric literals on keys the registry already
defines. See :doc:`/adk/06_kicad_dru`.

What interposer adapters must NOT do
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Declare rules.** Rules belong exclusively to the ADK deck. An adapter that
  emits its own ``output`` calls puts vendor-specific verdicts into an
  assembly report that is supposed to be vendor-neutral.
* **Declare or modify the chiplet boundary.** ``chiplet_boundary`` is injected
  by the ADK from the per-assembly boundary manifest and is built in
  ``layers_def.drc`` *before* the adapter runs. It is not a layer adapters may
  touch.
* **Import other .drc files.** Adapters are self-contained. The deck reads the
  adapter file's text and concatenates it; anything it pulls in from elsewhere
  is invisible to the contract and to the generators that parse it.

Interconnect adapter
--------------------

The optional second axis carries the bump-to-bump method rules. Select it with
``--interconnect-adapter <name>`` at the runner, or with the ``.chiplet``
``interconnect.adapter`` field through the orchestrator. Omit it and, unless a
per-method interconnect file is passed, the axis is disabled: no ``IXN`` rules
run, and the output matches an interposer-only run. A ``--interconnect-methods``
file activates the axis on its own, without any adapter.

.. code-block:: yaml

    interconnect:
      adapter: "ihp_cupillar"

Selecting an interconnect adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    pdk_adapters/interconnect/<basename>.drc

``--interconnect-adapter`` uses exactly the same resolver as the interposer
flag: a shortname resolved against ``pdk_adapters/interconnect/``, or an
explicit path to a ``.drc`` file.

Shipped interconnect adapters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. csv-table:: Interconnect adapters shipped with the ADK
    :file: tables/interconnect_adapters.csv
    :header: "Adapter", "Description", "IXN_spacing (um)", "IXN_pitch (um)", "IXN_pad_size (um)"
    :widths: 20 40 14 13 13
    :class: adk-rule-table
    :align: left

``ihp_cupillar`` and ``ihp_sbump`` mirror the corresponding interposer-stage
rules, so the interposer stage and the assembly stage of the two-stage DRC
check the same numbers.
``vendorx_microbump`` is a demonstration adapter for a fictional non-IHP vendor:
it exists to show that swapping the interconnect axis retightens the checks on
the *same* interposer geometry without touching the interposer adapter.

The parameter pack
~~~~~~~~~~~~~~~~~~

An interconnect adapter is a **parameter pack**, nothing more. It MUST set these
three keys on the ``interconnect_rules`` dictionary, whose defaults the deck
loads from ``config/interconnect.json`` before the adapter runs.

.. list-table::
    :header-rows: 1
    :widths: 20 80

    * - Key
      - Meaning
    * - ``IXN_spacing``
      - Minimum edge-to-edge spacing between attachment points, in micrometres.
    * - ``IXN_pitch``
      - Minimum centre-to-centre pitch, in micrometres.
    * - ``IXN_pad_size``
      - Representative pad size, in micrometres, used for the pitch-to-spacing
        conversion.

The whole of ``pdk_adapters/interconnect/ihp_cupillar.drc``, comments aside, is:

.. code-block:: ruby

    interconnect_rules['IXN_spacing']  = 40.0   # edge-to-edge between pillar pads
    interconnect_rules['IXN_pitch']    = 75.0   # centre-to-centre pitch
    interconnect_rules['IXN_pad_size'] = 35.0   # passivation opening

The deck validates the three keys after the adapter is evaluated, and aborts
naming the missing key. It also enforces ``IXN_pitch > IXN_pad_size`` at rule
time, because the pitch check is implemented as a spacing of
``pitch - pad_size``: KLayout has no native pitch check, so a pitch that does not
exceed the pad size would produce a non-positive spacing and a meaningless rule.
:doc:`/adk/04_ixn_rules` explains that conversion and its conservatism.

Optional region narrowing
~~~~~~~~~~~~~~~~~~~~~~~~~

An interconnect adapter MAY declare ``interconnect_region`` to narrow the region
the ``IXN`` rules check. If it does not, the deck falls back to
``chiplet_attachment_input``, the region the interposer adapter already exposes,
so no fabrication layer is duplicated across the two axes:

.. code-block:: ruby

    ixn_region = (defined?(interconnect_region) && !interconnect_region.nil?) ?
                 interconnect_region : chiplet_attachment_input

All three shipped adapters omit it deliberately.

What interconnect adapters must NOT do
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Redeclare** ``chiplet_attachment_input`` **or any fabrication layer.** Those
  belong to the interposer axis. An interconnect adapter that names a GDS layer
  has bound a bumping method to one substrate, which is the coupling this axis
  exists to remove.
* **Declare rules.** The ``IXN`` rules live in
  ``rule_decks/8_2_interconnect.drc``.
* **Import other .drc files.**

Per-method refinement
~~~~~~~~~~~~~~~~~~~~~

A single assembly may mix interconnect *methods* of the active interconnect PDK,
because each die's ``connection:`` selects its own method. Passing
``--interconnect-methods <gds-stem>.ixn_methods.json`` scopes the ``IXN`` checks
per method instead of assembly-globally.

The exporter derives that sidecar from the ``.chiplet``'s per-die connections
plus the interconnect PDK manifest, which remains the single source of truth for
the numbers. Every method entry MUST carry ``IXN_spacing``, ``IXN_pitch``,
``IXN_pad_size`` and ``dies``, the list of boundary-manifest instance names using
that method; the wrapper checks all four keys on every entry before evaluating
anything.

In this mode the deck:

#. builds one region per method, as the attachment pads intersected with the
   boundaries of the dies that use it, and fails loudly if a method references a
   die instance that the boundary manifest does not contain;
#. checks each method's own numbers inside its own region, reported as
   ``IXN.b.<method>`` and ``IXN.e.<method>``;
#. checks a conservative cross-method spacing between the regions of every pair
   of methods, the larger of the two spacings, reported as
   ``IXN.x.<m1>.<m2>``, because neither method's own check can see the other's
   pads;
#. checks attachment pads that fall outside every method region against the
   assembly-global adapter numbers, reported as ``IXN.b.unclaimed`` and
   ``IXN.e.unclaimed``, and only when an interconnect adapter is also loaded. If
   there is no adapter, those pads are simply not checked on this axis, and the
   deck logs that fact.

Because the method regions are resolved through per-die instance names, this
mode **requires the boundary manifest**: legacy ``exchange0`` mode carries no
per-die identity, and the wrapper refuses the combination. One interconnect PDK
applies per assembly; what varies per die is the method within it.

Without the file, the axis stays assembly-global, so adapter-only runs are
unchanged. :doc:`/formats/06_ixn_methods` is the normative description of the
sidecar.

Evolving the contract
---------------------

**Adding a required interposer input.** The required list is hardcoded in the
deck as ``required_inputs`` in ``klayout/drc/adk_assembly.drc``. Add the new name
there and update *every* shipped adapter in the same commit. The deck's
post-evaluation validator then makes any stale adapter fail loudly, by name,
rather than silently skipping a check. Bumping the ``version`` key in
``config/layers.json`` has no effect here: that file is legacy-compat, and only
its ``layers`` key is read, only on the ``--legacy-exchange0`` path.

**Adding an optional input.** Guard the consuming rule with ``if defined?(...)``
in the deck, so adapters that do not declare it still run. This is the pattern
``8_2_interconnect.drc`` uses for ``interconnect_region`` and ``layers_def.drc``
uses for the injected boundary manifest.

**Versioning.** The interconnect axis is additive: runs without an interconnect
adapter, and interposer adapters written before that axis existed, behave exactly
as the pre-interconnect deck. ``CHANGELOG.md`` in the ADK is the authoritative
per-release record of the contract; the ``VERSION`` file and the ``version`` keys
in every ``config/*.json`` track its latest released entry, and a test enforces
that they agree.

Writing an adapter for a new interposer
---------------------------------------

The shipped ``intm4tm2`` adapter is the whole worked example, because a
conforming adapter really is this small. Here it is in full, comment header
included:

.. code-block:: ruby

    # SPDX-License-Identifier: Apache-2.0
    #
    # IHP 130-nm IntM4TM2 aluminum BEOL interposer adapter.
    #
    # Declares ADK abstract inputs in terms of IHP-specific layers. IntM4TM2's
    # chiplet-attachment mechanism is the Cu pillar, formed where the
    # passivation opening (9/35) and the final Cu pad (41/35) overlap.

    passiv_pillar = polygons(9, 35)
    dfpad_pillar  = polygons(41, 35)

    chiplet_attachment_input = passiv_pillar.and(dfpad_pillar)

Line by line:

``# SPDX-License-Identifier: Apache-2.0``
    Every ADK source file carries an SPDX header. Keep it.

The comment block
    States the substrate the adapter is for and, more usefully, *what physical
    mechanism the attachment region models* and which layers encode it. This is
    the only documentation a reader of the assembly report has for why the
    region is what it is. Write it.

``passiv_pillar = polygons(9, 35)``
    A KLayout layer expression for the passivation opening, in the interposer's
    own GDS layer and datatype numbers. These are the numbers the ADK deck must
    never see, which is why they live here.

``dfpad_pillar = polygons(41, 35)``
    The final Cu pad.

``chiplet_attachment_input = passiv_pillar.and(dfpad_pillar)``
    The required abstract input. A Cu pillar exists only where both the
    passivation opening and the pad metal are present, so the attachment region
    is their intersection, not either layer alone. Choosing the intersection
    rather than the pad layer is the modelling decision: it makes ``ASM.f`` and
    the ``IXN`` rules operate on the geometry that actually forms a joint.

Note what is *absent*: no rule, no ``output`` call, no include of another file
and no parameter override. The two intermediate locals are a readability choice;
the contract cares only that ``chiplet_attachment_input`` ends up defined and
non-nil.

To support a new interposer, a vendor must produce exactly this:

#. **One file**, ``pdk_adapters/interposer/<name>.drc``, where ``<name>`` is the
   short name designers will pass to ``--interposer-adapter``.
#. **A definition of** ``chiplet_attachment_input`` in terms of that
   interposer's own layers, modelling the region where attachment can physically
   land. If the mechanism is not a Cu pillar, say so in the header comment and
   build the region from whatever layers do encode it.
#. **Optionally, numeric overrides** of ``drc_rules`` keys where the substrate
   genuinely demands different assembly numbers than the registry defaults.
   Write them as plain literals so the KiCad generator sees them too.

Nothing else. No change to any rule deck, no change to any registry, no change to
the runner. Verify the result by running the assembly DRC on a known-good and a
known-bad layout for that substrate: see :doc:`/adk/05_run_drc`. The two axes are
independent, so an interposer adapter can be validated on its own before any
interconnect adapter exists for that substrate.
