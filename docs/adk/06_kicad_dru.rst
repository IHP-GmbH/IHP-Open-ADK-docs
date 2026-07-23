KiCad DRU generation
====================

.. include:: tables/_rule_counts.inc

The assembly rules are authored once, in ``config/rule_params.json``, and
evaluated by the KLayout deck on the finished assembly GDS. That is late
feedback: you learn that two chiplets sit too close only after the interposer
has been routed and converted. The KiCad DRU generator moves the one rule that
has a faithful KiCad equivalent forward into the placement editor, so the
common mistake is caught while you are still dragging footprints.

The generator is ``kicad/dru/generate_assembly_dru.py``. It reads the same
parameter registry the KLayout deck reads, optionally merges the numeric
overrides an interposer adapter declares, and renders a block of KiCad design
rules to stdout or to a file.

.. warning::

    The KiCad side is a **partial** mirror of the ADK deck, by construction.
    Of the |asm-rule-count| assembly rules exactly one is emitted, and none of
    the |ixn-rule-count| interconnect rules are. A clean KiCad DRC therefore
    does not imply a clean assembly DRC. The KLayout deck
    (:doc:`/adk/05_run_drc`) remains the check that decides.

What the generator produces
---------------------------

One self-describing section, ready to be pasted into a project's
``.kicad_dru`` file or appended by a larger generator. With the defaults and
no adapter:

.. code-block:: text

    # ============================================================================
    # ADK assembly DRC rules (auto-generated)
    # ============================================================================
    #
    # Source: adk/config/rule_params.json
    #
    # Coverage:
    #   * ASM.a (chiplet boundary overlap) -- enforced by KiCad's native
    #     courtyard collision check; no rule emitted here.
    #   * ASM.b (chiplet-to-chiplet spacing) -- emitted below.
    #   * ASM.e (chiplet minimum area) and ASM.f (attachment geometry inside
    #     chiplet) have no clean KiCad DRU equivalent and are enforced
    #     post-layout only by the ADK KLayout deck (adk/klayout/drc).

    (rule "ASM.b - Chiplet min spacing"
      (constraint courtyard_clearance (min 50um))
      (condition "A.Type == 'Footprint' && B.Type == 'Footprint'"))

The coverage comment is part of the rendered output on purpose. A ``.kicad_dru``
file travels with the project and is read by people who never see this page, so
the block states in place what it does and does not cover.

The banner line ``# ADK assembly DRC rules (auto-generated)`` opens every
render and is the marker a downstream generator can look for when it needs to
locate or replace a previously appended ADK section.

.. note::

    The ``50um`` in the emitted constraint is the ``ASM_b`` default. It is an
    engineering default with no recorded foundry provenance, not a fab rule.
    See :doc:`/adk/03_asm_rules` for what the value means and
    :doc:`/adk/02_adapter_contract` for how an interposer adapter replaces it.

Coverage matrix
---------------

.. list-table:: ADK rules and their treatment in KiCad
    :header-rows: 1
    :widths: 14 24 62
    :class: adk-wide-table

    * - Rule
      - KiCad treatment
      - Why
    * - ``ASM.a``
      - KiCad native courtyard collision check
      - Overlapping chiplet boundaries are exactly what KiCad's built-in
        courtyard overlap check already reports for footprints. Emitting a
        second rule for it would double-report the same violation, so the ADK
        emits none and relies on the native check being enabled.
    * - ``ASM.b``
      - ``courtyard_clearance`` constraint, emitted
      - Chiplet-to-chiplet edge spacing maps cleanly onto a courtyard clearance
        between two footprints. This is the only rule with a faithful KiCad
        expression, and the only one the generator writes.
    * - ``ASM.e``
      - Not mirrored, post-layout only
      - Minimum chiplet area is a property of the boundary polygon recorded in
        the boundary manifest. KiCad has no area constraint over a courtyard,
        so the rule is evaluated by the KLayout deck against the manifest.
    * - ``ASM.f``
      - Not mirrored, post-layout only
      - Chiplet-attachment geometry containment is a relation between drawn
        interposer artwork and a chiplet boundary. The artwork does not exist
        in the KiCad board at all, so there is nothing to constrain there.
    * - ``IXN.*``
      - Not mirrored, KLayout only
      - The interconnect axis constrains attachment points inside a footprint,
        against each other and across methods. KiCad's courtyard vocabulary has
        no equivalent, and the pads only acquire their as-drawn positions when
        the interposer is generated. See :doc:`/adk/04_ixn_rules`.

Passing ``--interconnect-adapter`` does not add a constraint. It appends a
provenance comment naming the adapter and restating that ``IXN.b`` and
``IXN.e`` are enforced post-layout by ``8_2_interconnect.drc``:

.. code-block:: text

    #
    # Interconnect axis: ihp_cupillar
    #   * IXN.b (attachment-point spacing) and IXN.e (attachment-point pitch) are
    #     intra-footprint bump rules with no KiCad courtyard equivalent; they are
    #     enforced post-layout only by the ADK KLayout deck (8_2_interconnect.drc).

With no interconnect adapter the interconnect block is skipped entirely and
the output is byte-identical to what the generator produced before the
interconnect axis existed.

Running the generator
---------------------

.. code-block:: bash

    # Defaults from config/rule_params.json, to stdout
    python kicad/dru/generate_assembly_dru.py

    # Merge the interposer adapter's overrides and write a file
    python kicad/dru/generate_assembly_dru.py \
        --interposer-adapter intm4tm2 \
        --out assembly.kicad_dru

    # Add the interconnect-axis provenance comment
    python kicad/dru/generate_assembly_dru.py \
        --interposer-adapter intm4tm2 \
        --interconnect-adapter ihp_cupillar \
        --out assembly.kicad_dru

Both adapter flags accept either a shortname, resolved against
``pdk_adapters/interposer/`` or ``pdk_adapters/interconnect/``, or a literal
path to a ``.drc`` file. An unresolvable name fails with the two locations
that were probed.

.. literalinclude:: /adk/_usage/generate_assembly_dru.txt
   :language: text

Append the rendered section to the project's ``.kicad_dru``. KiCad reads that
file per project, so the rules apply to the board you are placing chiplets on
and to nothing else.

How adapter overrides are merged
--------------------------------

An interposer adapter is Ruby, read by the KLayout deck. The generator does not
execute it. It scans the file line by line for complete numeric assignments of
the form:

.. code-block:: ruby

    drc_rules['ASM_b'] = 75.0      # interconnect adapters use interconnect_rules[...]

and merges those on top of the JSON defaults. The narrow grammar is
deliberate:

- Only a **complete** numeric literal matches. Scientific notation
  (``30.0e3``), Ruby underscore grouping (``1_000``), a unit suffix (``30um``)
  and computed expressions (``30.0 + margin``) do not match and are ignored,
  rather than being truncated to a misleading partial number.
- An override key that is not already a known rule is a hard error. A
  lowercased ``asm_b`` would otherwise be silently dropped and the template
  would emit the default, which looks like a working override and is not.
- A negative value is a hard error. A spacing or area constraint cannot be
  negative.
- Comment lines are skipped.

Values are rendered as fixed-point decimals with trailing zeros stripped:
``50.0`` becomes ``50``, ``30.5`` stays ``30.5``. Scientific notation is never
emitted, because KiCad's DRU length-literal parser cannot read it.

.. tip::

    If an adapter expresses a rule value as a computed Ruby expression, the
    KLayout deck will honour it and the KiCad output will not. Keep the values
    an adapter intends to expose to KiCad as plain literals.

Importing the renderer
----------------------

A per-project DRU generator should reuse the ADK renderer rather than
duplicate the rule logic. There is no installed ``adk`` package (the
directories carry no ``__init__.py``), so put the generator's directory on
``sys.path`` and import the bare module, the same way the ADK's own tests do:

.. code-block:: python

    import sys
    sys.path.insert(0, "/path/to/adk/kicad/dru")
    from generate_assembly_dru import load_defaults, render_assembly_rules

    section = render_assembly_rules(load_defaults(), adapter_name="intm4tm2")

``render_assembly_rules`` returns a string ready to append to a
``.kicad_dru``. Its signature is append-only:

.. code-block:: python

    render_assembly_rules(
        rules,                            # dict of ASM_* values (required)
        adapter_name=None,                # interposer provenance label
        template_dir=None,                # override the template search dir
        interconnect_rules=None,          # IXN_* values
        interconnect_adapter_name=None,   # interconnect provenance label
    ) -> str

New options arrive as trailing keyword arguments with defaults, so an importer
written against an older ADK keeps working across releases and its output does
not change until it opts in.

The supporting entry points are importable too: ``load_defaults(path)`` and
``load_interconnect_defaults(path)`` read the registries,
``resolve_adapter_path(name_or_path)`` and
``resolve_interconnect_adapter_path(name_or_path)`` do the shortname
resolution, and ``parse_adapter_overrides(path)`` /
``parse_interconnect_overrides(path)`` extract the numeric overrides without
applying them.

Files
-----

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - Path
      - Role
    * - ``kicad/dru/generate_assembly_dru.py``
      - The generator and the importable renderer.
    * - ``kicad/dru/templates/assembly_rules.dru.jinja``
      - Jinja2 template for the rendered section. Rendered with
        ``StrictUndefined``, so a missing rule key fails the render instead of
        emitting a blank constraint.
    * - ``config/rule_params.json``
      - ``ASM_*`` defaults, shared with the KLayout deck.
    * - ``config/interconnect.json``
      - ``IXN_*`` defaults. Read on every run and forwarded to the renderer so
        the signature stays append-only, but the template emits no ``IXN``
        constraint: no interconnect value ever appears in the output. Only the
        adapter name does, as the provenance comment.
