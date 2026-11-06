interposer-pnr
==============

.. include:: /common.inc

``interposer-pnr`` places the dies of a 2.5D assembly on the interposer, puts
a bump on every die pad, routes the nets between them with OpenROAD and writes
the copper as a draft on a KiCad board, which a person then reviews and signs.
Each step is one subcommand that reads files and writes one, so
:doc:`/tools/10_packaging_flow` runs the steps in turn and stops at the first
refusal. You can also run them by hand.

Version 0.5.0 ships in the ADK-Tools image as the ``interposer-pnr`` command.
It is licensed GPL-3.0-or-later; the schema of the record ``signoff --check``
writes is Apache-2.0.

.. warning::
   Automated 2.5D place and route in the ADK is a proof of concept, at alpha
   maturity. What interposer-pnr writes is a geometric draft: it is not checked
   against a foundry DRC deck, not LVS-checked, and not ready for fabrication.
   Its own checks are pre-filters that catch a class of mistakes early. The
   assembly DRC deck, :doc:`/tools/09_assembly_lvs` and a person's review in
   KiCad remain the authority. Read `What it does not verify`_ before relying
   on a result.

This page covers ``place-check``, ``place``, ``bumps``, ``route``,
``export``, ``report``, ``signoff``, ``check-requirements``, ``io-pads`` and
``board-revision``. The commands for power delivery are not covered here.
``interposer-pnr <command> --help`` lists every option of a command.

The steps
---------

- ``place-check`` checks the placement a ``.chiplet`` states: overlap, the
  spacing between dies, minimum area, and that each die sits inside the
  interposer. It writes the placement report.
- ``place`` decides the dies a source leaves without a position. It seeds the
  dies on a square grid, each near the die it shares the most lanes with, turns
  each by a multiple of 90 degrees so its link bumps face that partner, then
  legalizes overlap and spacing with the other dies fixed. It writes an
  ``interposer_pnr.placement`` 1.0 document, or the refusals ``not_legal`` and
  ``kept_overlap`` in place of the dies. It reads only the provisional source
  that ``packaging-flow place`` writes, so you call it through that command.
- ``bumps`` puts one bump on each die pad, from each die's pin list, and
  binds pads to nets by name and by position. It lists the pads no net claims,
  so "every net routed" is never read as "every pad accounted for".
- ``route`` routes the nets with OpenROAD. With one routing layer it uses
  ``rdl_route``; with two or more it uses global and detailed routing. It
  refuses (exit 3) a die whose interconnect method does not land on the
  attachment surface the technology declares. A partial route is reported,
  not raised; ``--require-complete`` stops on any unrouted link.
- ``export`` writes the routed copper onto a copy of your board, never
  rewriting the board itself. Without ``--board`` it synthesizes a minimal
  board from the routing technology, with the interposer's stackup and its
  KiCad rule files.
- ``report`` collects the step reports into one run manifest.
- ``signoff`` is the manual gate. It exits 4 until a person has signed that
  exact board; see `Signing`_.

Three more commands support the steps. ``check-requirements`` refuses net
width requirements a routing technology cannot honour, before any route.
``io-pads`` writes the expected ``io_pads.json`` of a ``.chiplet``.
``board-revision`` reads the observations of an exported board and of your
edited copy, and writes a new intent proposal from the difference;
packaging-flow's ``edit --board`` drives it.

By hand, on a run
-----------------

The steps chain as below. The files are those of a completed run of
``two_die_echo_shifted_gf180`` (:doc:`/examples`), with ``EX`` and ``WD`` set
as on :doc:`/tools/10_packaging_flow`; each output goes to a scratch folder,
so the run's records stay as they are. The run itself records the exact
command line of every step in its manifest, which is the one to read when a
result differs.

.. RUN-ON-IMAGE: mkdir -p /tmp/pnr && PINS="--pins U1=$EX/inputs/dies/CF_DRIVER_LS/pins.json --pins U2=$EX/inputs/dies/CF_ECHO_CX_BONDPAD/pins.json" && interposer-pnr place-check --chiplet $WD/design.chiplet $PINS --out /tmp/pnr/placement.json && interposer-pnr bumps --chiplet $WD/design.chiplet $PINS --out /tmp/pnr/bumps.json && interposer-pnr route --chiplet $WD/design.chiplet --tech ihp_sg13g2_intm4tm2_rdl2 --bumps /tmp/pnr/bumps.json --work-dir /tmp/pnr/work --out /tmp/pnr/traces.json --report /tmp/pnr/route.json && interposer-pnr export --traces /tmp/pnr/traces.json --tech ihp_sg13g2_intm4tm2_rdl2 --out /tmp/pnr/design.draft.kicad_pcb --report /tmp/pnr/export.json && interposer-pnr report --placement /tmp/pnr/placement.json --bumps /tmp/pnr/bumps.json --route /tmp/pnr/route.json --export /tmp/pnr/export.json --out /tmp/pnr/run.json; echo "exit=$?"
.. code-block:: bash

    mkdir -p /tmp/pnr
    PINS="--pins U1=$EX/inputs/dies/CF_DRIVER_LS/pins.json
          --pins U2=$EX/inputs/dies/CF_ECHO_CX_BONDPAD/pins.json"
    interposer-pnr place-check --chiplet $WD/design.chiplet $PINS \
        --out /tmp/pnr/placement.json
    interposer-pnr bumps --chiplet $WD/design.chiplet $PINS \
        --out /tmp/pnr/bumps.json
    interposer-pnr route --chiplet $WD/design.chiplet \
        --tech ihp_sg13g2_intm4tm2_rdl2 --bumps /tmp/pnr/bumps.json \
        --work-dir /tmp/pnr/work --out /tmp/pnr/traces.json \
        --report /tmp/pnr/route.json
    interposer-pnr export --traces /tmp/pnr/traces.json \
        --tech ihp_sg13g2_intm4tm2_rdl2 \
        --out /tmp/pnr/design.draft.kicad_pcb --report /tmp/pnr/export.json
    interposer-pnr report --placement /tmp/pnr/placement.json \
        --bumps /tmp/pnr/bumps.json --route /tmp/pnr/route.json \
        --export /tmp/pnr/export.json --out /tmp/pnr/run.json

``PINS`` is left unquoted on purpose, so the shell splits it into its four
words. A ready die's pin list is the ``pins.json`` its die contract binds
(:doc:`/tools/12_chiplet_flow`). In the run, the ``route`` step may also take
the net width requirements the source states, so a route by hand without them
can differ from the run's.

The routing technology
----------------------

interposer-pnr reads no PDK kit files. An interposer enters as a
routing-technology descriptor, a small JSON file checked against a schema, and
``--tech`` takes its path or the name of a shipped one. The descriptor is the
one place the engine couples to a process, and the engine's ``PDK_CONTRACT``
document says how to write one for a new interposer. Version 0.5.0 ships three:

.. list-table::
    :header-rows: 1
    :widths: 38 62

    * - Descriptor
      - What it is
    * - ``ihp_sg13g2_intm4tm2``
      - The IHP IntM4TM2 interposer, one routing layer.
    * - ``ihp_sg13g2_intm4tm2_rdl2``
      - The same interposer, routed on TopMetal1 and TopMetal2. The examples
        use it.
    * - ``lambdapdk_interposer_5ml_0800``
      - A synthetic interposer with no fab behind it. It exists to show that
        the descriptor schema is not shaped around one PDK.

Where the numbers come from
---------------------------

Four inputs that interposer-pnr does not own feed the steps: the ADK's
``config/rule_params.json`` (the assembly rules), the interconnect PDK's
``manifest/interconnect_methods.json`` (bump body, landing and pitch per
method), the interposer PDK's ``libs.tech/intm4tm2_stack.json`` and KiCad rule
files (a synthesized board's stackup and rules), and the descriptor. The
engine finds them through ``--adk-root``, ``--interconnect-pdk-root`` and
``--interposer-pdk-root``, or ``ADK_ROOT``, ``INTERCONNECT_PDK_ROOT`` and
``INTERPOSER_PDK_ROOT``, which the image sets.

When a source cannot be found, the step stops with exit 5 and names every
place it looked. A ``rule_params.json`` that is found but states no ``ASM_b``
or no ``ASM_e`` also stops with exit 5; it is never completed from defaults.
``--allow-builtin-rules`` runs on the engine's own constants instead, and
every file it writes then records ``rules_source: builtin``. packaging-flow
never passes it.

Placement reads the assembly rules from ``rule_params.json`` only. An ADK
interposer adapter may override a rule for its own deck, and this engine does
not see that override.

Signing
-------

``signoff --sign`` records an acknowledgment that binds a signer to the
SHA-256 of one board. ``--reviewed`` (the same as ``--channel terminal``) is a
person who opened the board in KiCad, signing at a terminal; ``--channel
form`` is a person who reviewed through a review request, named by digest;
with neither, the record says nobody reviewed the copper. ``signoff --check
--report <export report> --record <file>`` judges the board against what was
sent and signs nothing: it writes ``as_drawn``, ``edited_as_sent`` or
``refused`` with reasons. Every acknowledgment says it is not fabrication
sign-off.

In a run you do not call ``signoff`` yourself: packaging-flow's
``verify-sign --gate interposer`` has the run's own interposer-pnr sign the
board.

What it does not verify
-----------------------

The engine states these limits in its own documentation:

- Routed traces are idealized centrelines. ``rdl_route`` has no DRC of its
  own, and on one layer a design can stay partly open: on the ADK-Tools
  reference assembly one layer routes 53 of 57 links. It also leaves a few
  terminal stubs narrower than the layer's minimum width (13 of 434 segments
  there), which must be fixed before real DRC passes.
- The multi-layer backend reports OpenROAD's detailed-route DRC, which is
  geometric and is not fabrication DRC. On a net widened by a requirement,
  ``detailed_route`` can report 0 violations while leaving the net closer to
  other copper than the technology allows. The engine's own copper spacing
  check fails such a route (exit 3) and names the net.
- Routing is not impedance-driven, and no parasitics are carried for the IHP
  interposer.
- ``place`` seeds on a grid as wide as the largest die plus ASM_b, so dies of
  very different sizes sit further apart than they need to, and a carrier the
  dies fit by hand can still be refused. It never flips a die and does not
  read the carrier's pad rows. Minimum area is detected, never fixed.
- The OpenROAD in the image is not the build the engine's routing tests ran
  on, so a route made there is not backed by those tests.
- An acknowledgment binds the board bytes; it does not read the die layouts
  the footprints name again.

Exit codes
----------

Codes 0 to 4 are never renumbered. A non-zero exit prints one line;
``--debug`` adds the traceback.

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - 0
      - The step did what it says.
    * - 1
      - A usage error, or a file it was asked to read is missing or does not
        parse. A usage error is 1, not 2, because 2 means a tool is missing.
    * - 2
      - A required external tool, such as OpenROAD, is absent or cannot run
        the step.
    * - 3
      - A design finding that must stop the run.
    * - 4
      - A human gate is not satisfied.
    * - 5
      - A source of rules or geometry is unreachable, or the built-in rules
        were asked for without ``--allow-builtin-rules``.
    * - 6
      - A source declares a major version this engine cannot read.
    * - 7
      - An unexpected exception: a bug in the engine, not in the design.
    * - 130
      - Interrupted.
