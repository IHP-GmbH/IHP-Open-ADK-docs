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

An interposer adapter is a single file, selected by a registry id::

    pdk_adapters/interposer/<basename>.drc

The ``--interposer-adapter`` flag of the DRC runner takes a **registry id**, such
as ``intm4tm2``, and resolves it through the ADK registry and nothing else. A
path is refused, and so is a name ending in ``.drc``. The reason is that the
adapter is evaluated as Ruby, and the field that names it can come from a
downloaded ``.chiplet``: only an id someone registered on this computer may
select the code the DRC runs. An unknown id exits 1 with the list of registered
ids, and ``run_drc.py --list-adapters`` prints them with their decks and the
registry that supplied each.

The registry has three layers, lowest precedence first:
``adk_registry.builtin.json`` beside the ADK, which lists the shipped adapters;
``$XDG_CONFIG_HOME/adk-tools/registry.json``; and
``$ADK_REGISTRY_DIR/registry.json``. To use a deck the ADK does not ship,
register it in one of the last two and pass its id:

.. code-block:: json

    {
      "schema": "adk-registry",
      "version": "1.0",
      "adapters": { "my_interposer_wip": "/abs/path/to/my_interposer.drc" }
    }

then ``--interposer-adapter my_interposer_wip``. A relative value resolves
against the directory of the file that declares it.

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
    passiv_sbump  = polygons(9, 36)
    dfpad_sbump   = polygons(41, 36)

    chiplet_attachment_input = passiv_pillar.and(dfpad_pillar).join(passiv_sbump.and(dfpad_sbump))

The **KLayout deck validates this, not the runner**. The runner only resolves the
adapter path and shells out to KLayout. After the adapter source is evaluated,
the deck raises unless every required input is both ``defined?`` and non-nil,
aborting the run with an error that names the missing input and the adapter file
that should have declared it. The required list itself is one line in
``klayout/drc/adk_assembly.drc``:

.. code-block:: ruby

    required_inputs = ['chiplet_attachment_input']

Optional abstract input
~~~~~~~~~~~~~~~~~~~~~~~

An adapter MAY declare the interposer's wire-bond pads, which rule ASM.g keeps
every die away from:

``wire_bond_pad_input``
    A lambda that takes a layout source and returns the interposer's wire-bond
    pad region from it.

It is a lambda, not a layer, because the die layouts in an assembly GDS may
draw their own bond pads on the same layers. The deck calls it once, on a
source with every die cell the boundary manifest names pruned from the
hierarchy, so a die's pads are never read and a carrier pad drawn under a die
still is. Inside the lambda, read layers from the source argument
(``src.polygons(...)``), never with a bare ``polygons(...)``, which reads the
full layout, die pads included. The shipped ``intm4tm2`` adapter uses the
PDK's own pad derivation:

.. code-block:: ruby

    wire_bond_pad_input = lambda do |src|
      src.polygons(9, 0).and(src.polygons(41, 0)).and(src.polygons(134, 0))
    end

An adapter that does not declare it runs ASM.g as not applicable, and the
report says so instead of passing it. See :doc:`/adk/03_asm_rules`.

Optional rule-parameter overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An adapter MAY override entries in the ``drc_rules`` dictionary, which the deck
loads from ``config/rule_params.json`` before the adapter runs:

.. code-block:: ruby

    drc_rules['ASM_b'] = 250.0  # this interposer's own chiplet spacing rule

An override is the technology's own rule, not a relaxation of the default.
Both ADK consumers honour it, by different mechanisms. The KLayout deck simply
reads the mutated dictionary. The KiCad DRU generator does not evaluate Ruby:
it reads the overrides with the ADK's own parser, ``adk_rule_params.py``, and
merges them on top of the registry defaults, only when invoked with
``--interposer-adapter <name>``. The parser cannot know what the deck would
apply for anything but a plain literal, so it refuses rather than guesses:

* write one override per line, ``drc_rules['NAME'] = NUMBER``, at most once per
  name, above any other code in the adapter (only blank lines, comments and
  other overrides before it);
* a computed value, for example ``drc_rules['ASM_b'] = base * 1.5``, exponent
  or underscore digits, a trailing ``;``, ``store`` or ``merge!``, or a
  continued line is refused, and so is a comment that names a rule table,
  on its own line or after an override;
* an override targeting a key that is not in ``config/rule_params.json``, or a
  negative value, is refused.

Placement reads no adapter: interposer-pnr legalizes to ``ASM_b`` and the
packaging flow keeps its wire-bond pads ``ASM_g`` from each die, both straight
from ``config/rule_params.json``. So a packaging-flow run that dispatches the
deck refuses an interposer adapter that overrides ``ASM_b`` or ``ASM_g`` to a
value other than the registry's, since the deck would check a different value
than placement used. The ADK's adapter README lists the exact
override form. See :doc:`/adk/06_kicad_dru`.

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

``--interconnect-adapter`` resolves through the same registry as the
interposer flag: a registry id such as ``ihp_cupillar``; a path is refused.

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
check the same numbers. Pitch is the exception: the interposer DRC deck does
not emit ``Padc.e`` or ``Padb.e``, so in the two-stage DRC pitch is checked
only at the assembly stage, by the IXN axis when it is enabled; see
:ref:`adk_ixn_pitch_as_spacing`.
``vendorx_microbump`` is a demonstration adapter for a fictional non-IHP vendor:
it exists to show that swapping the interconnect axis retightens the checks on
the *same* interposer geometry without touching the interposer adapter.

The parameter pack
~~~~~~~~~~~~~~~~~~

An interconnect adapter is a **parameter pack**, nothing more. It MUST set these
three keys on the ``interconnect_rules`` dictionary, whose defaults the deck
loads from ``config/interconnect.json`` before the adapter runs. Set all three
explicitly: a key the adapter leaves out takes the registry default and is not
reported (see :ref:`adk_ixn_fail_loud`).

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

The executable content of ``pdk_adapters/interconnect/ihp_cupillar.drc``,
below its header comment, is:

.. literalinclude:: /../src/IHP-Open-ADK/pdk_adapters/interconnect/ihp_cupillar.drc
    :language: ruby
    :start-at: interconnect_rules['IXN_spacing']

The deck enforces ``IXN_pitch > IXN_pad_size`` at rule time, because the pitch
check is implemented as a spacing of ``pitch - pad_size``: KLayout has no
native pitch check, so a pitch that does not exceed the pad size would produce
a non-positive spacing and a meaningless rule.
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
   ``IXN.e.unclaimed``, and each method's pads against those pads, reported as
   ``IXN.x.<method>.unclaimed``; all three only when an interconnect adapter is
   also loaded. Without an adapter those pads carry no rule, and the deck reports
   them as ``IXN.unassociated``: a finding that they were not checked, not a
   spacing violation.

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

**Versioning.** The interconnect axis is additive: without an interconnect
adapter or a per-method file none of its parts enter the eval chain (see
:ref:`adk_ixn_additive`), and interposer adapters written before that axis
existed still load unchanged. ``CHANGELOG.md`` in the ADK is the authoritative
per-release record of the contract; the ``VERSION`` file and the ``version`` keys
in every ``config/*.json`` track its latest released entry, and a test enforces
that they agree.

Writing an adapter for a new interposer
---------------------------------------

The shipped ``intm4tm2`` adapter is the whole worked example, because a
conforming adapter really is this small. Here it is in full, comment header
included, as the pinned ADK ships it:

.. literalinclude:: /../src/IHP-Open-ADK/pdk_adapters/interposer/intm4tm2.drc
    :language: ruby

Line by line:

``# SPDX-License-Identifier: Apache-2.0``
    Every ADK source file carries an SPDX header. Keep it.

The comment block
    States the substrate the adapter is for and, more usefully, *what physical
    mechanism the attachment region models* and which layers encode it, and
    which layers make up the wire-bond pads. This is the only documentation a
    reader of the assembly report has for why the regions are what they are.
    Write it.

``passiv_pillar = polygons(9, 35)``
    A KLayout layer expression for the passivation opening, in the interposer's
    own GDS layer and datatype numbers. These are the numbers the ADK deck must
    never see, which is why they live here.

``dfpad_pillar = polygons(41, 35)``
    The final Cu pad.

``passiv_sbump`` and ``dfpad_sbump``
    The same pair for the solder bump, on datatype 36.

``chiplet_attachment_input = passiv_pillar.and(dfpad_pillar).join(passiv_sbump.and(dfpad_sbump))``
    The required abstract input. A Cu pillar or a solder bump exists only where
    both its passivation opening and its pad metal are present, so each
    mechanism's region is that intersection, not either layer alone, and the
    attachment region is the union of the two. Choosing the intersection
    rather than the pad layer is the modelling decision: it makes ``ASM.f`` and
    the ``IXN`` rules operate on the geometry that actually forms a joint.

``wire_bond_pad_input = lambda do |src| ... end``
    The optional abstract input. The PDK derives a wire-bond pad from the
    passivation opening (9/0), dfpad (41/0) and TopMetal2 (134/0) together, so
    the lambda returns that intersection. It reads every layer through
    ``src``, the carrier source the deck passes in, so a die in the assembly
    that draws its own pads on the same layers is never read. Leave it out and
    ASM.g is reported not applicable; see `Optional abstract input`_.

Note what is *absent*: no rule, no ``output`` call, no include of another file
and no parameter override. The four intermediate locals are a readability choice;
the contract cares only that ``chiplet_attachment_input`` ends up defined and
non-nil, and that ``wire_bond_pad_input``, when present, is a lambda that
returns a layer.

To support a new interposer, a vendor must produce exactly this:

#. **One file**, ``pdk_adapters/interposer/<name>.drc``, and a registry entry
   for ``<name>``: in ``adk_registry.builtin.json`` when it ships with the ADK,
   in a user registry until then (see `Location and selection`_). ``<name>`` is
   the id designers pass to ``--interposer-adapter``.
#. **A definition of** ``chiplet_attachment_input`` in terms of that
   interposer's own layers, modelling the region where attachment can physically
   land. If the mechanism is not a Cu pillar, say so in the header comment and
   build the region from whatever layers do encode it.
#. **Optionally, a** ``wire_bond_pad_input`` **lambda** that returns the
   interposer's wire-bond pads from the source it is given, if the substrate
   has any. Without it ASM.g is not applicable on that substrate. See
   `Optional abstract input`_.
#. **Optionally, numeric overrides** of ``drc_rules`` keys where the substrate
   genuinely demands different assembly numbers than the registry defaults.
   Write them as plain literals so the KiCad generator sees them too.

Nothing else. No change to any rule deck, to the parameter registries or to the
runner. Verify the result by running the assembly DRC on a known-good and a
known-bad layout for that substrate: see :doc:`/adk/05_run_drc`. The two axes are
independent, so an interposer adapter can be validated on its own before any
interconnect adapter exists for that substrate.
