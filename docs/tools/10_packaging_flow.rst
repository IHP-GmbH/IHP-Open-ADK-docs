packaging-flow
==============

.. include:: /common.inc
.. include:: /tools/_staged_engines.inc

``packaging-flow`` runs an assembly from one ``system.chiplet`` to a verdict.
It admits each ready die from its contract (or builds it with
:doc:`/tools/12_chiplet_flow`), places the dies and routes the carrier with
:doc:`/tools/11_interposer_pnr`, writes the interposer and assembly GDS, runs
the DRC decks, the terminal map and :doc:`/tools/09_assembly_lvs`, and halts
for a person's signature at four checkpoints on the way. Everything it does is
recorded in a manifest that ``packaging-flow verify`` recomputes from the files
on disk.

It is meant for chip and package designers putting several dies on one carrier,
and for anyone bringing up a new die technology or interposer who wants the
same checks on their own design. The technology, the dies and the carrier come
from the input file and the registries it names, not from the flow. At this
release those cover dies in IHP SG13G2 and GF180MCU on the IHP IntM4TM2
interposer.

Version |packaging-flow-version| ships in the ADK-Tools image as the ``packaging-flow`` command.
It is licensed GPL-3.0-or-later.

.. warning::
   packaging-flow is part of the |current-status|. Its subcommands, run layout
   and messages may still change between versions; its exit codes are never
   renumbered. A verdict covers only the checks the run lists, a signature is
   a review and not a qualification, and nothing it writes is a sign-off for
   fabrication.

This page covers ``run``, ``resume``, ``status``, ``map``, ``validate``,
``verify``, ``verify-run``, ``verify-sign``, ``sign-request``,
``verify-accept``, ``verify-open``, ``review-copy``, ``review-levels``,
``views``, ``edit``, ``place``, ``compare-nets``, ``gds-xor``,
``lvs-bundle``, ``lvs-verify``, ``fab-file`` and ``tasks``.
``packaging-flow --help`` lists every subcommand of the version in your image, and ``packaging-flow <command>
--help`` its options.

Where it runs
-------------

packaging-flow runs inside the image (:doc:`/tools/07_adk_tools_image`). It
starts the other tools from ``PATH``: ``interposer-pnr``, KLayout,
``chiplet-export``, ``adk-verify-carrier-drc``, ``assembly-lvs``, and
``chiplet-die-flow`` when a die is built in the run. A run names a tool it
cannot find before the stage that needs it starts. It finds the ADK, the
interposer PDK and the interconnect PDK through ``ADK_ROOT``,
``INTERPOSER_PDK_ROOT`` and ``INTERCONNECT_PDK_ROOT``, which the image sets;
:doc:`/install/03_environment` describes the discovery chain. A run starts only
from a file inside the workspace, ``/work`` by default (``--workspace``).

A die can enter a run in two ways. A ready die, built elsewhere, is a folder
with its layout, pin list, build record and die contract, as
``chiplet-die-flow emit-ready-die`` writes it, and is admitted from that
contract; :doc:`/tools/12_chiplet_flow` describes one. A die built in
the run goes through ``chiplet-die-flow build-die`` and LibreLane, which the
image carries for IHP SG13G2 only.

The image installs packaging-flow's ``console`` extra, so ``run`` and
``resume`` also show their progress in the terminal.

The examples in :doc:`/examples` drive every step below block by block, and
``two_die_echo_shifted_gf180`` is the one this page follows. The commands use
the shell its README's second block sets up: ``EX`` is the example folder under
``/work``, ``RUN`` is the run folder a run prints, and ``WD`` is ``$RUN/run``,
the folder the stages write into. That block also points
``INTERCONNECT_PDK_ROOT`` at the example's own registry copy.

Checking the input
------------------

``validate`` reads a ``system.chiplet`` without running anything:

.. code-block:: bash

    packaging-flow validate $EX/system.chiplet

It prints one line per finding, ``[SEVERITY PFL-xxxx] file:line: message``,
then a count of the lines that refuse a run, the notes, and the ports no net
accounts for. It writes a pre-run map to ``.packaging-flow/map.json`` beside
the file. A refusing line here is one a run would stop on.

A run
-----

.. code-block:: bash

    packaging-flow run $EX/system.chiplet --tier full --view-store "$ADK_DIE_VIEWS"

The run makes a new folder, ``runs/<UTC time>/`` beside the file, prints
``run folder: <path>`` before its first stage, and writes its stages into
``run/`` inside it. A run never reuses a folder, and there is no command that
runs one stage again: the way on is a new run.

``--tier`` is ``hermetic``, ``smoke`` or ``full`` (the default). The examples
run ``full``; the shorter tiers are for testing the flow itself.
``--view-store`` names the store of die views the co-simulation check reads
(chiplet-cosim's ``select`` and the ``sim`` check kind), pinned with its tree
digest. Dies are admitted from their contracts, not from this store. For a
``system.chiplet`` it defaults to ``$ADK_DIE_VIEWS`` when that is set, and
otherwise to an empty store under the verification root. ``--admitted-by`` names
the role that admits a die built elsewhere, never a person's name. ``--skip
CHECK`` leaves a check out, for iteration only: ``verify`` then exits 17 and
the run is not green.

The run is a fixed list of stages. The ones you see in ``status`` include
``spec``, ``elaborate``, ``terminals``, ``admit:<instance>`` (or ``build`` and
``emit`` for a die built in the run), ``place-check``, ``bumps``, ``route``,
``routed-geometry``, ``export``, ``gds``, ``drc``, ``terminal-map``,
``assembly-lvs``, ``package-drc``, ``signoff-check`` and ``verdict``, with a
``halt:<gate>`` row at each checkpoint. A design finding before a checkpoint
does not stop the run: it is recorded on its row, and the run is not green.
Two failures do stop it at their row: a route that leaves two nets closer than
the layer's spacing rule (:doc:`/tools/11_interposer_pnr`), and a metal fill
that cannot meet the density rules (see `The layout`_).

Placement works to the registry's ``ASM_b`` and ``ASM_g``, so a run that
dispatches the assembly DRC deck refuses an interposer adapter that overrides
either to a different value (:ref:`placement and adapter overrides
<adk_placement_overrides>`).

The layout
----------

The ``routed-geometry`` row has interposer-pnr write every net's wires and
vias as the flow routed them, with the placed dies and the carrier's metal
stack, into ``pnr/routed-geometry.json``, and the I/O pads beside it into
``pnr/routed-io-pads.json``. The ``gds`` row composes the interposer and
assembly GDS from that document when the signoff check reads the board as
drawn (``as_drawn``). When a person edited the board after the flow sent it
(``edited_as_sent``), the row composes from the board instead. Any other word,
or a signoff-check record that is missing or does not read, refuses the row
before it draws anything (``CompositionRefused``). The row records which of the
two it used in its ``composition`` fact. The run no longer writes or checks a
HyperLynx ``.hyp`` file: when the layout is composed from an edited board, the
exporter can still leave one beside the draft ``.chiplet``, and the run does
not record it. Within one run
the board is checked and drawn once: a board edited after ``gds`` has run is
not checked or drawn again; start a new run from it (`Changing the design`_).

On a design whose ``external`` block names a profile, the ``gds`` row also
fills the carrier's metals and reads the fill's density report. When the fill
cannot meet a metal's density rule, the row fails and the run stops at that
row (exit 1). It prints
one line per metal, for example ``gds: the metal fill could not meet the
density rules on Metal4: <n> % is covered, below the allowed <lo> to <hi> %``,
then what usually causes it: dies covering too much of one area, or wires
drawn too densely in one area. No signature waives it. Move the dies apart or
make the interposer larger in ``system.chiplet``, then run again. ``verify``
refuses such a run with the same text. A report the row cannot read is
recorded as a tooling failure, not as a statement about the design.

Checkpoints and signatures
--------------------------

A run halts at four gates in turn: ``die:<instance>`` (one per die), then
``interposer``, ``assembly`` and ``external``. ``verify`` reports them as
``level 1`` (chiplet) to ``level 4`` (external). At each halt the run exits 2
with a ``GatePending`` line that names the gate and the command that signs it.
A halt is not a failure. A later run of the same design reuses a gate's
signature while what it signed is unchanged: ``map`` names each gate it reused
and the run that signed it, and the run halts at the first gate whose signature
no longer holds. The external gate keys the terminal map by its content, not
its raw bytes, so a run in another folder keeps that gate's key.

.. code-block:: bash

    packaging-flow map $RUN
    packaging-flow verify-run $RUN --gate die:U1
    packaging-flow verify-sign $RUN --gate die:U1
    packaging-flow resume $RUN

``map`` shows where the run stands and what each gate waits on.
``verify-run`` reads a gate's checks again. ``verify-sign`` prints the gate's
sheet and, at a terminal, asks each checklist item, then for the gate's key,
your role and your name; a ``no`` signs nothing. A failing check of a kind that
allows it may be waived there, with a reason. ``resume`` continues the run once
every gate the halt waits on is signed, and halts at the next one.

Before it looks at the gate, ``verify-sign`` reads every signature record filed
under the signatures folder. A record that does not read is refused first,
whatever gate you name, and the message says to restore it as it was filed or
move it out of ``signatures/`` and sign its gate again. When a die gate the run
recorded as signed has no record filed at its path under its key, every gate of
the run is refused, not only that die's: either the signatures folder is not
the one the run was signed in (check ``--root``), or the record or the run's
``manifest.json`` changed after signing. Nothing is signed in either case.

Every signature this version files is of version 1. It cannot check a
signature filed at a newer version: every gate of such a run reads as having
no key, and the message says to use the packaging-flow that signed it, or a
newer one.

Away from a terminal, ``sign-request --gate <gate> --answers <file>`` writes
the gate's request, ``$RUN/requests/<gate>.json``, from the run's map and your
answers file, and ``verify-sign --answers <request>`` signs from it. Nothing is
waived away from a terminal, and a request whose channel is a script is
recorded as signed by a script, not reviewed.
``verify-accept`` signs a die gate whose die needs a person's acceptance.

Before the interposer signature, look at the board. At that halt the run
copies it under ``$RUN/review/board/``, and ``verify-open`` opens a result by
its id. ``review-copy <board> <folder>`` makes another copy wherever you name.

.. code-block:: bash

    packaging-flow verify-open $RUN board interposer.board

Close KiCad without saving. The signature binds the board's bytes under
``run/pnr/``, and a save changes only the copy, which ``verify-open`` then
refuses as moved. To change the board on
purpose, see `Changing the design`_.

The run also draws the system's connection sheet, in its ``connection-sheet``
row right after the system schematic: the dies with their pins, the wires to
the net labels, the no-connect marks and the carrier pads, as on the KiCad
sheet, with the assembly name and the digest of its ``.chiplet`` in the title.
It is one SVG picture, ``pnr/<name>.draft.connection-sheet.svg`` under
``run/``. ``verify-open`` prints its path and opens nothing:

.. code-block:: bash

    packaging-flow verify-open $RUN connection_sheet assembly.connection_sheet

Open the file in a web browser, or in any program that shows SVG pictures.
The sheet is drawn and shown, not signed: the assembly signature of this
release binds the review schematic, not the sheet. A name the picture cannot
hold stops the run at that row (``refused (undrawable_text)``) and says what
to rename. A sheet larger than 8 MiB is still written, with a warning.

The verdict
-----------

After the last signature, ``resume`` writes the verdict. Then:

.. code-block:: bash

    packaging-flow status $RUN
    packaging-flow verify $WD/manifest.json
    packaging-flow review-levels $WD $RUN/review

``status`` prints one row per stage. ``verify`` recomputes the manifest from
the files and prints its verdict, the tier, the dies built and admitted, then
one line per level. ``verify --json`` carries the verdict as one word, in
``verdict``. The verdicts are:

- ``OK``: every check held, and every die was built in this run. It is not a
  fabrication qualification.
- ``not every die was built in this run`` (the word
  ``NOT_ALL_DIES_BUILT_IN_RUN`` in ``--json``): every check that applies held,
  but the run placed dies it did not build, so the all-dies-built verdict does
  not apply. It exits 1 and is not a failed run. It is what a run of ready dies
  expects: ``mixed_gf180`` expects ``verify: not every die was built in this
  run (tier full; built none; admitted U1, U2)``.
- ``FAILED``: at least one check did not hold on the files; each reason
  names one. It exits 1.
- ``NOT EVALUATED``, in ``--json`` only: ``verify`` did not complete, and the
  document says nothing about the run. Text ``verify`` prints no verdict then,
  only its one error line on stderr. It exits with the code of the refusal, 7
  for an internal error.

``review-levels`` fills ``$RUN/review/`` by level, ``1-chiplet/<die>/``,
``2-interposer/``, ``3-assembly/`` and ``4-external/``, with ``levels.txt``
naming each file and its digest. ``views`` draws one picture per gate whose
layout the run holds, into ``$RUN/views/``; a picture binds and signs nothing.
``fab-file`` writes the carrier GDS that would be sent to the fab, from a
completed run whose ``interposer-drc``, ``drc`` and ``package-drc`` rows
passed: it removes layers outside the technology's set, checks the top cell,
grid and database unit, and runs the carrier and package decks again on the
result. Anything else is refused. A failed DRC row is refused even when a
person waived it at its gate. The run's check plan must also require every DRC
check the flow has, the die DRC among them: one the run's checks section
removed or replaced, or one that was skipped or informative, is refused as
``FabDrcNotInPlan``, which names each one. Every shipped template keeps all of
them. ``fab-file`` is not a fabrication approval.

Each check is read as one status word: ``PASS``, ``FAIL``, ``INCONCLUSIVE``,
``ERROR``, ``UNRESOLVED``, ``NOT_DECLARED``, ``NOT_AVAILABLE``, ``MISSING``,
``STALE``, ``SKIPPED``, ``CURRENT`` or ``WAIVED``. Only a ``FAIL`` of a kind
that allows it can be waived.

Assembly LVS in a run
---------------------

The ``assembly-lvs`` row derives the resolved input from the run's own records,
writes it to ``out/assembly-lvs/resolved.json``, runs ``assembly-lvs`` on it
and keeps its report at ``out/reports/assembly_lvs.json``.
:ref:`The flow-run mapping <assembly_lvs_flow_run>` on
:doc:`/tools/09_assembly_lvs` says how the nine assembly-lvs states read as the
four flow words, what a match does not claim, and how ``lvs-bundle`` and
``lvs-verify`` repeat the check on a completed run's copies.

.. _packaging_flow_black_box:

Dies of a technology the flow has no tables for
-----------------------------------------------

A die of a process the flow has no layer sheet, pad-layer row or design-rule
deck for can still be placed. It enters as a ready die (its four files:
layout, pin list, build record, die contract), built elsewhere, under an
admission: a small JSON file beside the system file with three keys,
``reason``, ``scope`` and ``not_verified``, named on the die's row as
``admission:`` (format 1.4 of the system file), and a run started with
``--admitted-by <role>``. The role is kept in the run's manifest, never in the
file; give a role, not a person. A die from a partner's package
(:doc:`/formats/09_partner_die_package`) enters this way.

Its technology is the id its contract states, and the system file declares
nothing else of it. The attachment method on the die's row must list that id
among the die processes it attaches; the shipped registry lists ``sg13g2`` and
``sg13cmos5l``, so a die of another technology needs a registry row that names
it (the ``registry:`` key of the system file points the run at a registry
folder of your own). A method that does not list the die's technology refuses
at the first stage, before anything is built.

The die's own layout is never composed into the assembly: its layer numbers
would land on the carrier's layers of the same number and every deck would
read them. The admit stage writes an abstract instead, from the contract and
the pin list alone: the outline, and one rectangle and one name per pad
opening, shifted into a layer window of the run's own (one window per such
technology, from layer 3000 upwards, recorded on the admit row). Placement,
routing, the exported board and the assembly LVS read that abstract; the
layout stays an input of the admission and of the run identity only. The
assembly LVS maps the die on the one pad pair its openings name.

The admit row records the contract's facts, the build status its record
states (``partner-declared`` for a die from a partner package, not qualified)
and that the die's internals are not claimed. The run itself completes, but
``verify`` never reads it as verified, because a placed die was not built by
this run: it prints ``die <instance> internals: unverified; admitted`` and
ends with "not every die was built in this run", reason (g).
The die gate is accepted by a person (``verify-accept <run> --gate
die:<instance>``), whatever its checks read; a checks template that drops a
die check never lets ``verify-sign`` sign it instead.

The refusals you will meet:

- A die row without an admission, or a run without ``--admitted-by``, refuses
  at the admit stage (``ReadyDieRefused``).
- A contract that states no ``process.technology`` refuses when the system
  file is read.
- A method that does not list the technology refuses before any build
  (``DieProcessRefused``).
- A run can hold at most 29 such technologies, one layer window each.

``verify-open <run> layout die.layout:<instance>`` opens the admitted die's
layout in KLayout with the pad sheet, the layer sheet of the shared pad
vocabulary, since the die's own process has no sheet here.
``verify-open <run> abstract_over_layout ...`` shows the abstract over the
layout. The repository's test fixtures hold a frozen partner die, a package of
a fictional ``fx-pdk`` process and the four files the writer wrote from it, as
a complete worked input.

Changing the design
-------------------

A run never rewrites its own records, and a hand edit under ``run/`` is
refused on resume (exit 3). Changes go through commands that record them:

- ``edit $RUN --board <copy>`` takes an edited copy of the run's board, and
  ``edit $RUN --sheet <file.kicad_sch>`` a saved system schematic, and writes
  the change into the ``system.chiplet`` the run read. The next run starts
  from it.
- ``edit <file.chiplet> --move ID=X,Y[,ROT]`` sets a placed die's position, in
  um in the carrier frame the file states, and optionally its rotation (0, 90,
  180 or 270). Repeat ``--move`` for several dies: every move is checked
  together, as ``place`` checks a file, before anything is written. On a
  carrier with no size the dies are shifted together to the margins, so their
  positions relative to each other are the ones you asked for. It prints the
  reasons and the diff, writes the file, keeps its working files under
  ``edits/<UTC time>/`` beside it, and ends with ``wrote <file> (sha256 ...);
  start a new run of it``. A die without a position yet is refused: run
  ``place`` first. A placement the placer refuses exits 22, and nothing is
  written.
- ``place <file.chiplet>`` asks interposer-pnr to place the dies the file
  leaves without a position, size the carrier when the file gives no size, and
  put each unplaced external pin on an edge. It writes the result into the
  file, prints why each number is what it is and the diff, and keeps its
  decisions under ``edits/<UTC time>/`` beside the file. ``--again`` places
  every die again. Placement is a proof of concept (see
  :doc:`/tools/11_interposer_pnr`).
- ``compare-nets <file> <reference>`` compares the nets of two files; it exits
  0 when they agree and 21 when they differ.
- ``gds-xor <a.gds> <b.gds>`` says whether two layouts draw the same geometry,
  for example a layout before and after a change. It compares every layer
  either file holds, flattened through the hierarchy, by the XOR of its
  shapes; a layer in one file only differs as a whole. ``--tolerance-dbu N``
  (an even number, default 0) drops a difference up to N database units wide,
  ``--cell`` names the cell when a file has more than one top cell, and
  ``--json`` prints the answer as a document. Texts are not compared. It prints
  each layer that differs with its area and box, then whether the digests of the
  two files' canonical forms are equal, which it does not grade. It exits 0 when every layer
  holds and 24 when one does not. It reads the two files only, not a run.

After a placement, ``place`` and ``edit --move`` also draw it as a picture,
``placement-view.svg`` in the same ``edits/<UTC time>/`` folder, and end with
``Placement picture: <path>. Open it in a web browser, or in any program that
shows SVG pictures.`` The picture shows the carrier with its size, each die
with its id, size and turn, and the external pads by edge, before any routing.
It binds and signs nothing. When it cannot be drawn, the last line says why,
and that the placement was written, or that it is unchanged.

In VS Code, the design's map (open the design's item in the Packaging Flow
view) shows the newest placement picture after a ``place``, with its path
under it. When it cannot show it, it says so in the picture's place: "<file>
is the newest placement picture, but it cannot be shown here. Open it in a web
browser. If a new place gives the same, report it." For a picture larger than
8 MiB it says "<file> is larger than 8 MiB, the most this view shows. Open it
in a web browser."

A system can also start from a blank KiCad sheet. Its ``.chiplet`` leaves the
die-to-die links out, and ``python -m packaging_flow.sheet_handout
<file.chiplet>`` writes a handout folder beside it, named by its stem, with
the die symbol library and an empty KiCad project. Draw the links in a copy of
that folder; ``edit <file.chiplet> --sheet <saved .kicad_sch>`` then writes
them into the file with no run.

From an editor
--------------

``tasks`` prints the verbs the VS Code tasks of the image run, each with its
command and when it applies. ``tasks --vscode --out <folder>`` writes them as
``.vscode/tasks.json`` under that folder, and refuses to overwrite a different
one. Output from version 0.1.0:

.. code-block:: text

    run: packaging-flow run {system} (always, on the system file)
    continue: packaging-flow resume {run} (every gate the halt waits on is signed, or a hand step)
    check-results: packaging-flow verify-run {run} --gate {gate} (a dropped gate whose checks do not sign as they read, or a check asked for again)
    sign: packaging-flow verify-sign {run} --gate {gate} --answers {request} (a checked gate, its signature dropped or not)
    accept: packaging-flow verify-accept {run} --gate {gate} --answers {request} (a gate that needs acceptance)
    open: packaging-flow verify-open {run} {instrument} {subject} (a result row)
    open-row: packaging-flow verify-open {run} {instrument} {subject} --row {row} --as {verb} (each verb a sheet row's open names)
    validate: packaging-flow validate {system} (always, on the system file)
    views: packaging-flow views {run} (a gate whose layout the run holds and has no picture of yet)

Each VS Code task is labelled ``Flow: <verb>`` and runs the command on its
line. A task has no terminal, so ``Flow: sign`` signs only from a request file.

Exit codes and messages
-----------------------

A refusal prints ``ClassName: message`` on standard error. Each message has an
id, ``PFL-`` and four digits, and the catalog ``messages/catalog.json`` in the
package lists them all: ``PFL-00xx`` for refusals, ``PFL-01xx`` for the
``verify`` family and ``compare-nets``, ``PFL-02xx`` for notes, warnings and
the refusals of ``fab-file`` and ``edit --sheet``.

Exit codes are never renumbered:

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - 0
      - Success.
    * - 1
      - A typed refusal, or a definite assembly LVS finding.
    * - 2
      - A halt at a gate, an invalid LVS input or tool, or an input the run
        cannot derive.
    * - 3
      - A hand edit inside the run, or an ambiguous LVS result.
    * - 4
      - The run's identity does not match its records.
    * - 5
      - ``resume`` found no recorded halt.
    * - 6
      - A die build could not be bound to one result folder.
    * - 7
      - Internal error.
    * - 8, 9
      - The source of an engine cannot be resolved, or is refused.
    * - 10, 11
      - A ready die is refused, or cannot be read.
    * - 12
      - A check is ``STALE`` or ``MISSING``.
    * - 13
      - A ``FAIL`` or ``NOT_DECLARED`` that nothing covers.
    * - 14
      - An ``ERROR`` or ``UNRESOLVED``, or a torn or empty check set.
    * - 15
      - An ``INCONCLUSIVE`` check.
    * - 16
      - Every finding is covered by a waiver or an acceptance.
    * - 17
      - A check was ``SKIPPED``.
    * - 18
      - An edit is stale against the run it names.
    * - 19
      - An edit of the system file is refused.
    * - 20
      - ``kicad-cli`` is missing.
    * - 21
      - ``compare-nets``: the nets differ.
    * - 22
      - The placer refused.
    * - 23
      - A source has no placement.
    * - 24
      - ``gds-xor``: the two layouts do not draw the same geometry.
    * - 130
      - Interrupted.

Codes 12 to 17 come from the ``verify`` commands. When several apply, the first
of 14, 12, 15, 13, 16 and 17 wins.
