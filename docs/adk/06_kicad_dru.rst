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

One self-describing section, ready to be appended to a project's
``.kicad_dru`` file or by a larger generator. With the defaults and
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
    #     Only die footprints (those with a GDS_FILE field) are held to it: a
    #     pad footprint drawn with a courtyard (a library or hand-drawn one; the
    #     flow's own pad footprints carry none) is not a chiplet.
    #   * ASM.e (chiplet minimum area), ASM.f (attachment geometry inside
    #     chiplet) and ASM.g (die edge to wire-bond pad) have no clean KiCad DRU
    #     equivalent and are enforced post-layout only by the ADK KLayout deck
    #     (adk/klayout/drc). ASM.g would need a courtyard on the pad, which the
    #     flow's wire-bond pad footprints do not carry.

    (rule "ASM.b - Chiplet min spacing"
      (constraint courtyard_clearance (min 0.2mm))
      (condition "A.Type == 'Footprint' && B.Type == 'Footprint' && A.getField('GDS_FILE') != '' && B.getField('GDS_FILE') != ''"))

The coverage comment is part of the rendered output on purpose. A ``.kicad_dru``
file travels with the project and is read by people who never see this page, so
the block states in place what it does and does not cover.

The banner line ``# ADK assembly DRC rules (auto-generated)`` opens every
render and is the marker a downstream generator can look for when it needs to
locate or replace a previously appended ADK section.

.. note::

    The ``0.2mm`` in the emitted constraint is ``ASM_b``, 200 um, the ADK's
    assembly rule and not a foundry rule. Every length goes out in mm: KiCad
    applies no clearance written in ``um`` or ``nm`` and reports no error. See
    :doc:`/adk/03_asm_rules` for what the value means and
    :doc:`/adk/02_adapter_contract` for how an interposer adapter states its
    own.

The condition holds only die footprints to the clearance, the ones with a
``GDS_FILE`` field. A pad footprint drawn with a courtyard, a library or
hand-drawn one, is not a chiplet, and at 200 um two such pads at a 150 um
pitch would otherwise be reported.

.. warning::

    The section has no ``(version 1)`` header. It goes below the one the
    project's ``.kicad_dru`` opens with, and KiCad ignores a rules file that
    lacks it without saying so. A template passed through ``template_dir``
    must write every length with the ``mm`` filter: nothing checks the
    template for it, and KiCad silently applies no clearance written in
    ``um``.

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
        between two die footprints, the ones with a ``GDS_FILE`` field. This is
        the only rule with a faithful KiCad expression, and the only one the
        generator writes.
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
    * - ``ASM.g``
      - Not mirrored, post-layout only
      - Die edge to wire-bond pad would be a courtyard clearance between a die
        and a pad footprint, which needs a courtyard on the pad. The flow's
        wire-bond pad footprints carry none, so the rule is evaluated by the
        KLayout deck on the finished carrier.
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

With no interconnect adapter the interconnect block is skipped entirely.

Running the generator
---------------------

.. code-block:: bash

    # Defaults from config/rule_params.json, to stdout
    python3 kicad/dru/generate_assembly_dru.py

    # Merge the interposer adapter's overrides and write the section to a file
    python3 kicad/dru/generate_assembly_dru.py \
        --interposer-adapter intm4tm2 \
        --out adk_section.txt

    # Add the interconnect-axis provenance comment
    python3 kicad/dru/generate_assembly_dru.py \
        --interposer-adapter intm4tm2 \
        --interconnect-adapter ihp_cupillar \
        --out adk_section.txt

.. include:: /_image_adk_scripts.inc

Both adapter flags take a registry id, resolved through the ADK registry as
for the DRC runner (:doc:`/adk/02_adapter_contract`); a path is refused. An
unknown id exits 1, an unusable registry 5 or 6.

.. literalinclude:: /adk/_usage/generate_assembly_dru.txt
   :language: text

Append the rendered section to the project's ``.kicad_dru``, below its
``(version 1)`` line. KiCad reads that file per project, so the rules apply to the board you are placing chiplets on
and to nothing else.

How adapter overrides are merged
--------------------------------

An interposer adapter is Ruby, read by the KLayout deck. The generator does not
execute it. It reads the overrides with the ADK's own parser,
``adk_rule_params.py``, which accepts one form per line:

.. code-block:: ruby

    drc_rules['ASM_b'] = 250.0     # this interposer's own chiplet spacing

and merges those on top of the JSON defaults. The parser cannot know what the
deck would apply for anything else, so it refuses rather than guesses:

- Only a **complete** decimal literal is read, with no leading zero in its
  integer part, since Ruby reads ``0250`` as octal. Scientific notation
  (``2.5e2``), Ruby underscore grouping (``1_000``), a trailing ``;``,
  ``store``, ``merge!`` and computed expressions (``200.0 + margin``) are
  refused with an error that names the line, never read as a partial number or
  skipped.
- Overrides sit above any other code in the adapter, at most once per name,
  and a line that continues one (led by ``.``, ``&.``, ``&&``, ``||``, ``and``
  or ``or``) is refused. A comment that names a rule table is refused
  anywhere in the file, as a line of its own or after an override; write a
  commented-out override without the table name.
- An override key that is not already a known rule is a hard error. A
  lowercased ``asm_b`` would otherwise be silently dropped and the template
  would emit the default, which looks like a working override and is not.
- A negative value is a hard error. A spacing or area constraint cannot be
  negative.

Lengths are rendered in mm, as fixed-point decimals to 1 nm with trailing zeros
stripped: 200 um becomes ``0.2mm``. Scientific notation is never emitted,
because KiCad's DRU length-literal parser cannot read it, and a nonzero length
that would round to 0 is refused rather than written as no clearance.

Importing the renderer
----------------------

A per-project DRU generator should reuse the ADK renderer rather than
duplicate the rule logic. There is no installed ``adk`` package (the
directories carry no ``__init__.py``), so put the generator's directory on
``sys.path`` and import the bare module, the same way the ADK's own tests do:

.. code-block:: python

    import sys
    sys.path.insert(0, "/path/to/adk/kicad/dru")
    from generate_assembly_dru import (
        _apply_overrides, load_defaults, parse_adapter_overrides,
        render_assembly_rules, resolve_adapter_path,
    )

    rules = load_defaults()
    adapter = resolve_adapter_path("intm4tm2")
    _apply_overrides(rules, parse_adapter_overrides(adapter), adapter, "Interposer")
    section = render_assembly_rules(rules, adapter_name="intm4tm2")

``render_assembly_rules`` renders the numbers it is given. ``adapter_name`` is
only the provenance label in the file's ``Source:`` comment: passing it does not
merge the adapter's overrides, so merge them yourself, as above, or the file
claims overrides it does not contain. Merge through ``_apply_overrides``, as
the CLI does, rather than with ``dict.update``: it refuses an override of an
unknown key or a negative value before it merges. It is the module's only
merge-and-validate path today, although its name marks it private.
``parse_adapter_overrides`` is defined in ``adk_rule_params`` at the ADK root;
the module re-exports it and puts that root on ``sys.path`` itself.
``render_assembly_rules`` returns a string ready to append to a
``.kicad_dru``, below its ``(version 1)`` line. Its signature is append-only:

.. code-block:: python

    render_assembly_rules(
        rules,                            # dict of ASM_* values (required)
        adapter_name=None,                # interposer provenance label
        template_dir=None,                # override the template search dir
        interconnect_rules=None,          # IXN_* values
        interconnect_adapter_name=None,   # interconnect provenance label
    ) -> str

New options arrive as trailing keyword arguments with defaults, so a call
written against an older ADK keeps working. The output does follow the rules:
ADK 0.3.0 writes the ``ASM.b`` clearance as ``0.2mm`` for die footprints only.
A custom template passed through ``template_dir`` must change too, since the
``num`` filter is gone: write a length as ``{{ value | mm }}``, not
``{{ value | num }}um``.

The supporting entry points are importable too: ``load_defaults(path)`` and
``load_interconnect_defaults(path)`` read the registries,
``resolve_adapter_path(adapter_id)`` and
``resolve_interconnect_adapter_path(adapter_id)`` resolve a registry id to its
deck, and ``parse_adapter_overrides(path)`` /
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
