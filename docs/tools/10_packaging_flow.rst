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
``views``, ``edit``, ``place``, ``compare-nets``, ``lvs-bundle``,
``lvs-verify``, ``fab-file`` and ``tasks``. ``packaging-flow --help`` lists
every subcommand of the version in your image, and ``packaging-flow <command>
--help`` its options.

Where it runs
-------------

packaging-flow runs inside the image (:doc:`/tools/07_adk_tools_image`). It
starts the other tools from ``PATH``: ``interposer-pnr``, KLayout,
``chiplet-export``, ``adk-verify-carrier-drc``, ``assembly-lvs``, and
``chiplet-die-flow`` when a die is built in the run. It finds the ADK, the
interposer PDK and the interconnect PDK through ``ADK_ROOT``,
``INTERPOSER_PDK_ROOT`` and ``INTERCONNECT_PDK_ROOT``, which the image sets;
:doc:`/install/03_environment` describes the discovery chain. A run starts only
from a file inside the workspace, ``/work`` by default (``--workspace``).

A die can enter a run in two ways. A ready die, built elsewhere, is admitted
from its contract; :doc:`/tools/12_chiplet_flow` describes one. A die built in
the run goes through ``chiplet-die-flow build-die`` and LibreLane, which the
image carries for IHP SG13G2 only.

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
``export``, ``gds``, ``drc``, ``terminal-map``, ``assembly-lvs``,
``package-drc``, ``signoff-check`` and ``verdict``, with a ``halt:<gate>`` row at
each checkpoint. A design finding before a checkpoint does not stop the run:
it is recorded on its row, and the run is not green.

Checkpoints and signatures
--------------------------

A run halts at four gates in turn: ``die:<instance>`` (one per die), then
``interposer``, ``assembly`` and ``external``. ``verify`` reports them as
``level 1`` (chiplet) to ``level 4`` (external). At each halt the run exits 2
with a ``GatePending`` line that names the gate and the command that signs it.
A halt is not a failure. A later run of the same design reuses a gate's
signature while what it signed is unchanged: ``map`` names each gate it reused
and the run that signed it, and the run halts at the first gate whose signature
no longer holds.

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

The verdict
-----------

After the last signature, ``resume`` writes the verdict. Then:

.. code-block:: bash

    packaging-flow status $RUN
    packaging-flow verify $WD/manifest.json
    packaging-flow review-levels $WD $RUN/review

``status`` prints one row per stage. ``verify`` recomputes the manifest from
the files and prints one word, the tier, the dies built and admitted, then one
line per level. The words are:

- ``OK``: every check held, and every die was built in this run. It is not a
  fabrication qualification.
- ``NOT_ALL_DIES_BUILT_IN_RUN``: every check that applies held, but the run
  placed dies it did not build, so the all-dies-built verdict does not apply.
  It exits 1 and is not a failed run. It is the word a run of ready dies
  expects: ``two_die_echo_shifted_gf180`` expects ``verify:
  NOT_ALL_DIES_BUILT_IN_RUN (tier full; built none; admitted U1, U2)``.
- ``FAILED``: at least one check did not hold on the files; each reason
  names one. It exits 1.
- ``NOT EVALUATED``: ``verify`` did not complete, and says nothing about the
  run (exit 7).

``review-levels`` fills ``$RUN/review/`` by level, ``1-chiplet/<die>/``,
``2-interposer/``, ``3-assembly/`` and ``4-external/``, with ``levels.txt``
naming each file and its digest. ``views`` draws one picture per gate whose
layout the run holds, into ``$RUN/views/``; a picture binds and signs nothing.
``fab-file`` writes the carrier GDS that would be sent to the fab, from a
completed run whose carrier and package decks passed: it removes layers outside
the technology's set, checks the top cell, grid and database unit, and runs
both decks again on the result. Anything else is refused. It is not a
fabrication approval.

Each check is read as one status word: ``PASS``, ``FAIL``, ``INCONCLUSIVE``,
``ERROR``, ``UNRESOLVED``, ``NOT_DECLARED``, ``NOT_AVAILABLE``, ``MISSING``,
``STALE``, ``SKIPPED``, ``CURRENT`` or ``WAIVED``. Only a ``FAIL`` of a kind
that allows it can be waived.

Assembly LVS in a run
---------------------

The ``assembly-lvs`` row derives the resolved input from the run's own records,
writes it to ``out/assembly-lvs/resolved.json``, runs ``assembly-lvs`` on it
and keeps its report at ``out/reports/assembly_lvs.json``.
:ref:`assembly_lvs_flow_run` says how the nine assembly-lvs states read as the
four flow words, what a match does not claim, and how ``lvs-bundle`` and
``lvs-verify`` repeat the check on a completed run's copies.

Changing the design
-------------------

A run never rewrites its own records, and a hand edit under ``run/`` is
refused on resume (exit 3). Changes go through commands that record them:

- ``edit $RUN --board <copy>`` takes an edited copy of the run's board, and
  ``edit $RUN --sheet <file.kicad_sch>`` a saved system schematic, and writes
  the change into the ``system.chiplet`` the run read. The next run starts
  from it.
- ``place <file.chiplet>`` asks interposer-pnr to place the dies the file
  leaves without a position, size the carrier when the file gives no size, and
  put each unplaced external pin on an edge. It writes the result into the
  file, prints why each number is what it is and the diff, and keeps its
  decisions under ``edits/<UTC time>/`` beside the file. ``--again`` places
  every die again. Placement is a proof of concept (see
  :doc:`/tools/11_interposer_pnr`).
- ``compare-nets <file> <reference>`` compares the nets of two files; it exits
  0 when they agree and 21 when they differ.

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
    * - 130
      - Interrupted.

Codes 12 to 17 come from the ``verify`` commands. When several apply, the first
of 14, 12, 15, 13, 16 and 17 wins.
