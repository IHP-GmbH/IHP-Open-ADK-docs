Running the assembly DRC
========================

.. include:: /common.inc
.. include:: tables/_rule_counts.inc

``klayout/drc/run_drc.py`` is the standalone entry point to the assembly DRC. It
resolves the adapters, finds and validates the boundary manifest, invokes
KLayout in batch mode on ``adk_assembly.drc``, parses the resulting report and
returns an exit code you can branch on in a script.

This page is about running it. For what the rules actually check, see
:doc:`/adk/03_asm_rules` and :doc:`/adk/04_ixn_rules`.

Prerequisites
-------------

**KLayout 0.29.11 or newer, on ``PATH``.**
    The runner shells out to ``klayout -b`` and checks the version first. An
    older KLayout, or none at all, aborts before anything else happens. The
    container image ships a suitable build; see :doc:`/install/01_container`.

**The ``klayout`` Python module.**
    Imported at module load to read the layout's top cells. It is a separate
    package from the KLayout application binary and both are needed.

**An assembly layout.**
    ``.gds``, ``.gds.gz``, ``.gds2``, ``.gds2.gz`` or ``.oas``. The extension
    is checked before the file is opened; a file with the right extension that
    is not a valid stream fails with a clean message rather than a KLayout
    traceback.

**The boundary manifest sidecar.**
    ``<gds-stem>.boundaries.json``, emitted next to the layout by the producer
    (``hyp_to_gds`` or ``blackbox_chiplet``). This is where the chiplet
    boundaries come from. See :doc:`/formats/04_boundary_manifest`.

**An interposer adapter.**
    Required, always. The deck is interposer-agnostic and has no default: with
    no adapter it does not know what geometry on the substrate means
    "attachment". See :doc:`/adk/02_adapter_contract`.

The minimal invocation
----------------------

.. code-block:: bash

    python klayout/drc/run_drc.py \
        --path design.gds \
        --interposer-adapter intm4tm2 \
        --run_dir /tmp/adk_drc

That runs the |asm-rule-count| ASM rules and nothing else. The boundary manifest
is discovered next to ``design.gds``, the top cell is auto-detected, and the
report lands in ``/tmp/adk_drc``.

``--interposer-adapter`` takes either form:

* a **shortname**, resolved against ``pdk_adapters/interposer/<name>.drc``, so
  ``intm4tm2`` finds the shipped IHP IntM4TM2 adapter; or
* an **explicit path** to a ``.drc`` file, used as given.

The resolver tries the literal path first and the shortname second, and if
neither exists it reports both candidates it looked for.

Adding the interconnect axis
----------------------------

Supply an interconnect adapter to add the bump-to-bump pitch and spacing checks:

.. code-block:: bash

    python klayout/drc/run_drc.py \
        --path design.gds \
        --interposer-adapter intm4tm2 \
        --interconnect-adapter ihp_cupillar \
        --run_dir /tmp/adk_drc

Scope those checks per attachment method by adding the exporter's methods
sidecar:

.. code-block:: bash

    python klayout/drc/run_drc.py \
        --path design.gds \
        --interposer-adapter intm4tm2 \
        --interconnect-adapter ihp_cupillar \
        --interconnect-methods design.ixn_methods.json \
        --run_dir /tmp/adk_drc

``--interconnect-adapter`` resolves the same way as the interposer flag, against
``pdk_adapters/interconnect/``. Unlike the manifest, the methods file is never
auto-discovered: you pass it explicitly or the axis stays assembly-global.

.. tip::

    Passing both, as above, is the combination that leaves nothing unchecked.
    The methods file gives each die the numbers its own method demands; the
    adapter supplies the fallback for attachment geometry no method claims. With
    a methods file and no adapter, unclaimed pads are simply not checked on this
    axis, and the deck logs a line saying so.

Command-line reference
----------------------

.. literalinclude:: _usage/run_drc.txt
   :language: text

Flags in detail
---------------

``--path`` (required)
    The assembly layout. Validated for existence and extension, then resolved to
    an absolute path.

``--interposer-adapter`` (required)
    Shortname or path, as described above.

``--interconnect-adapter``
    Optional. Enables the IXN axis. Omit it and the evaluated deck is identical
    to a run from before the axis existed.

``--interconnect-methods``
    Optional. Per-method IXN scoping. Requires the boundary manifest, and is
    rejected together with ``--legacy-exchange0`` before KLayout is spawned.
    Validated for schema string and exact version by the runner; per-method keys
    and die names are validated by the deck.

``--topcell``
    The cell to check. Auto-detected when omitted. Auto-detection is strict: a
    layout with several top cells is an error telling you to pick one, and a
    layout with none is an error too. It is never guessed.

``--run_dir``
    Where the log and, by default, the report are written. Created if missing.
    Omitted, empty or the literal string ``pwd`` all mean "a timestamped
    subdirectory of the current directory".

``--report``
    An explicit report path, overriding the default naming. Useful when a CI job
    wants a fixed filename to publish.

``--threads``
    Threads per KLayout invocation. Default 4.

``--run_mode``
    ``tiling`` (default), ``deep`` or ``flat``. See below.

``--manifest``
    An explicit boundary manifest, overriding auto-discovery.

``--legacy-exchange0``
    Compatibility mode. See below.

.. note::

    Arguments reach KLayout as an ``argv`` list, not a shell string. Each
    ``-rd key=value`` is one token, so paths, report names and top-cell names
    containing spaces, quotes or shell metacharacters are passed through
    verbatim. This matters because a top-cell name can come straight out of an
    untrusted GDS.

Manifest discovery and validation
---------------------------------

With no ``--manifest``, the runner looks for the layout's stem plus
``.boundaries.json`` in the layout's own directory: ``design.gds`` implies
``design.boundaries.json``.

**A missing manifest is a hard error, not a warning.** This is deliberate. The
chiplet boundaries are the only thing the ASM rules have to check; a run with no
boundary source would evaluate every rule against an empty region and report a
clean result. That vacuous pass is more dangerous than a failure, so the runner
refuses, and the error message tells you the two ways forward: produce the
sidecar, or pass ``--legacy-exchange0``.

When the manifest is found it is opened and validated in the runner, before
KLayout is started:

* it must parse as JSON and be an object;
* ``schema`` must be exactly ``adk-boundary-manifest``;
* ``version`` must be exactly the version this runner supports, currently
  ``1.0.0``. There is no range and no forward compatibility: a mismatch tells
  you to regenerate the sidecar with a current producer or to update the ADK;
* ``boundaries`` must be a list, and every entry must be an object carrying a
  ``polygon_dbu`` of at least three ``[x, y]`` pairs.

The last check duplicates part of the JSON schema without taking a
``jsonschema`` dependency. The reason is narrow and worth knowing:
``layers_def.drc`` reads ``polygon_dbu`` blind, so a structurally malformed but
version-valid sidecar would otherwise surface as a Ruby backtrace from inside a
KLayout batch run, which is a much worse thing to debug than a one-line Python
error.

The legacy exchange0 path
-------------------------

Before the manifest existed, chiplet boundaries travelled on a fabrication
layer: IHP SG13G2 Exchange0, GDS 190/0. ``--legacy-exchange0`` restores that
behaviour, reading the boundary from that layer instead of from a sidecar.

.. code-block:: bash

    python klayout/drc/run_drc.py \
        --path old_design.gds \
        --interposer-adapter intm4tm2 \
        --legacy-exchange0

Use it for exactly one thing: checking an assembly GDS produced before the
migration, for which no sidecar exists and cannot be regenerated. Nothing in the
current toolchain emits 190/0, and ``config/layers.json`` is marked
legacy-compat for this reason alone.

In this mode ``--manifest`` is ignored, with a warning, and
``--interconnect-methods`` is rejected outright, because legacy layouts carry no
per-die instance names for a method to refer to.

.. note::

    The two paths are not merely similar. A regression test runs the same
    fixture through both modes and asserts that the violation sets agree, which
    is what makes the migration verifiable rather than asserted. A second test
    pins the other direction: a chiplet-internal 190/0 shape, which a real die
    might legitimately contain, is ignored in manifest mode. That aliasing
    hazard is precisely why the boundary left the fabrication namespace.

Run modes
---------

``--run_mode`` selects how KLayout evaluates the deck.

``tiling`` (default)
    Splits the layout into tiles and evaluates them in parallel, honouring
    ``--threads``. The right default for a full assembly: assembly geometry is
    spread over a large area with modest hierarchy, which is the case tiling
    handles best.

``deep``
    Hierarchical evaluation. Exploits repetition rather than area, so it is
    worth trying on an assembly with many identical dies.

``flat``
    Flattens everything first. The slowest and most memory-hungry option, and
    the one whose result is the easiest to reason about. Use it to rule out a
    mode-dependent artefact when a violation looks suspicious.

All three check the same rules with the same numbers. If two modes disagree on
the same layout, that is a bug worth reporting, not a tuning choice.

What lands in the run directory
-------------------------------

.. code-block:: text

    /tmp/adk_drc/
        adk_drc_run_2026_07_23_09_14_02.log
        design_TOP_assembly.lyrdb

The log
    Named for the UTC timestamp of the run. It carries the full DEBUG-level
    record: the resolved adapter paths, the manifest path and the number of
    boundaries loaded, one line per rule as the deck reaches it
    (``ADK: ASM.a``, ``ADK: IXN.b.<method>``, and so on), the pass or fail
    banner, the sorted list of violated rules and the elapsed time. The same
    stream goes to the console.

The report
    A KLayout results database. The default name is
    ``<layout-stem>_<topcell>_assembly.lyrdb``, so the example above is
    ``design.gds`` with top cell ``TOP``. ``--report`` overrides it.

The report is always written, including on a clean run, where it contains zero
items. The runner treats a missing report as a failure of the run rather than as
a pass.

Reading the report in KLayout
-----------------------------

Open the layout with the report attached:

.. code-block:: bash

    klayout design.gds -m /tmp/adk_drc/design_TOP_assembly.lyrdb

``-m`` loads a marker database into the layout view. The Marker Browser opens
from ``Tools`` and lists the violations grouped by category, one category per
rule name: ``ASM.a``, ``ASM.b``, ``IXN.b.<method>`` and so on. Selecting an
entry zooms the layout view to the offending geometry and highlights it.

The category names are exactly the rule names, and the description string
alongside each category carries the number that was checked, for example
``ASM.b : Min. chiplet-to-chiplet spacing is 50.0 um``. That is the fastest way
to confirm which value an adapter override actually put into effect.

.. tip::

    The chiplet boundaries themselves are not in the GDS, so a report full of
    ASM markers can be hard to interpret against a layout that shows only
    interposer metal. The ``show_boundaries`` KLayout macro reads the same
    ``.boundaries.json`` sidecar the checker reads and displays each chiplet
    outline as markers. Because it is the same file, the outlines are exactly
    what the checker saw. See :doc:`/flow/07_view_and_inspect`.

Exit codes
----------

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - ``0``
      - The run completed and the report contains no violations.
    * - ``1``
      - The run completed and the report contains violations.
    * - ``2``
      - A tooling failure with no more specific code available.
    * - other
      - KLayout's own non-zero exit code, passed through.

The distinction between the last two rows is worth being precise about. When the
KLayout subprocess exits non-zero, for example because an adapter did not
declare a required input, or the deck raised on an unresolvable die instance,
the runner does not dump a Python traceback on top of an error KLayout has
already printed. It returns KLayout's exit code, falling back to ``2`` if that
code was somehow zero.

.. note::

    Exit code ``1`` is overloaded. The runner also exits ``1`` on its own
    precondition failures: no KLayout, unreadable layout, ambiguous top cell,
    unresolvable adapter, missing or invalid manifest. Those are distinguishable
    from a violation result by the absence of a report file, and the log always
    carries the reason on its last lines. A script that must tell the two apart
    should test for the report rather than trust the code alone. On a
    well-formed input the runner returns only ``0`` or ``1``, and the regression
    suite asserts exactly that.

A shell wrapper therefore looks like this:

.. code-block:: bash

    python klayout/drc/run_drc.py \
        --path design.gds \
        --interposer-adapter intm4tm2 \
        --run_dir "$RUN_DIR"
    status=$?

    case $status in
        0) echo "assembly DRC clean" ;;
        1) echo "assembly DRC violations, see $RUN_DIR" ;;
        *) echo "assembly DRC did not run (code $status)"; exit $status ;;
    esac

Troubleshooting
---------------

The messages below are the ones the runner and the deck actually emit, shortened
to their identifying phrase.

``KLayout not found. Make sure it is installed and in PATH.``
    The runner could not execute ``klayout -b -v``. A related message,
    ``KLayout did not report a version``, means the binary ran but printed
    nothing, which usually indicates a broken or partial installation. See
    :doc:`/install/03_environment`.

``Minimum KLayout version is 0.29.11.``
    Upgrade, or use the container image.

``Layout has multiple top cells. Specify one with --topcell.``
    Pass ``--topcell``. The runner will not pick for you, because checking the
    wrong top cell produces a confidently wrong result.

``Could not read layout '<path>'``
    The extension check passed but KLayout could not parse the stream.
    Truncated or mislabelled file.

``Interposer adapter not found: '<name>'.``
    The message lists both candidates that were tried, the literal path and
    ``pdk_adapters/interposer/<name>.drc``. The same message with
    ``Interconnect`` names the other axis and directory. Note that the IHP
    interposer adapter is ``intm4tm2`` and has no aliases.

``Boundary manifest not found: <path>``
    The sidecar is missing. Regenerate it with the producer, point at it with
    ``--manifest``, or check a pre-migration layout with ``--legacy-exchange0``.

``Unsupported boundary-manifest version in <path>``
    The sidecar's ``version`` is not the one this runner pins. Regenerate it
    with a current producer, or check out an ADK that matches the sidecar. The
    match is exact by design.

``Not an ADK boundary manifest``
    The file parses but its ``schema`` key is not ``adk-boundary-manifest``.
    Usually a different sidecar passed by mistake.

``boundaries[N].polygon_dbu must be a list of >= 3 [x, y] pairs``
    Structurally malformed manifest. The index tells you which entry. This is a
    producer bug; report it against the tool that wrote the sidecar.

``--interconnect-methods requires the boundary manifest and cannot be combined with --legacy-exchange0``
    Exactly what it says. Per-method checking needs per-die instance names, and
    the legacy path has none.

``ADK requires an interposer adapter.``
    Raised by the deck when it is invoked directly rather than through the
    runner and ``-rd adapter=`` was not set.

``Interposer adapter (<path>) must declare 'chiplet_attachment_input'.``
    The adapter was evaluated but did not define the required abstract input.
    See :doc:`/adk/02_adapter_contract`.

``Interconnect adapter (<path>) must set interconnect_rules['IXN_pitch'].``
    An interconnect adapter is a parameter pack and must set all three of
    ``IXN_spacing``, ``IXN_pitch`` and ``IXN_pad_size``. The message names the
    one that is missing.

``Interconnect methods entry '<id>' missing '<key>'``
    A method in the sidecar lacks one of ``IXN_spacing``, ``IXN_pitch``,
    ``IXN_pad_size`` or ``dies``.

``Per-method interconnect references die instance(s) not in the boundary manifest``
    A method's ``dies`` list names something the manifest does not contain. The
    message prints both the unresolved names and the instances the manifest
    does have, which nearly always makes the typo obvious. This is a hard error
    rather than a warning because the alternative is silently checking fewer
    pads than you think. See :doc:`/adk/04_ixn_rules`.

``Interconnect method '<id>': IXN_pitch (...) must exceed IXN_pad_size (...)``
    The pitch-to-spacing conversion would produce a zero or negative spacing,
    that is, a check that can never fail. Fix the numbers in the methods file or
    the adapter.

``Result database not generated: <path>``
    KLayout exited zero but wrote no report. Check the log for what the deck did
    before it stopped.
