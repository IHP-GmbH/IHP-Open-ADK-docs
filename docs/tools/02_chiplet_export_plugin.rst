Chiplet export plugin
=====================

.. include:: /common.inc

The chiplet export plugin, |plugin-repo|, is the pcbnew action plugin that turns
a finished interposer board into the artefacts the rest of the flow consumes: a
canonical ``.chiplet`` assembly file, the GDS layouts it references, the machine
readable sidecars the assembly checks read, and, optionally, an assembly DRC
verdict.

It is the sole entry point for chiplet export. The KiCad fork's native
``File > Export > Chiplet...`` menu action was removed so that this is the only
path: the C++ exporter writes an *intermediate* ``.chiplet``, anchored on the PCB
bounding box and carrying ``_metadata.finalize_required: true``, which every
consumer refuses. Only ``hyp_to_gds.py --update-chiplet-file`` can re-anchor it
into the canonical frame, and only after generating the GDS whose bounding box
defines that frame. The plugin exists to make the two steps inseparable.

What one run produces
---------------------

.. code-block:: text

    <output-dir>/
      <board>.chiplet                        canonical assembly file
      <board>.chiplet.exportcontent.sha256   digest of the exporter-owned content
      <board>.hyp                            the HyperLynx netlist that drove the run
      MANIFEST.md                            what was produced this run, ticked
      layout/
        <board>_interposer.gds               interposer layout
        <board>_interposer.boundaries.json   chiplet boundary manifest
        <board>_interposer.pillars.json      as-drawn Cu-pillar centres
        <board>_interposer.fill_coverage.json  coarse fill coverage map (with fill)
        <board>_complete.gds                 interposer plus placed dies
        <board>_complete.boundaries.json
        <board>_complete.pillars.json
        <board>_complete.ixn_methods.json    per-method interconnect scoping
      reports/
        <board>_assembly_drc.lyrdb           ADK assembly DRC results
        <board>_cupillar_drc.json            Cu-pillar connection DRC summary
        <board>_fill_density.json            per-metal fill density (with fill)
        assembly_drc/                        DRC scratch directory
      logs/
        <timestamp>_<board>.log              one file per run

The convention is deliberate and the orchestrator enforces it in one place, the
``layout_path()`` helper, so the writer arguments and the DRC input can never
drift apart.

- The ``.chiplet`` stays at the **root**, because that is the file a user opens.
  Its ``.exportcontent.sha256`` sidecar sits beside it: the digest of the
  exporter-owned content recorded after each successful export. The next
  export refuses to replace a ``.chiplet`` whose exporter-owned content was
  edited by hand since, unless a headless caller sets ``ExportOptions.force``.
  Blocks the exporter does not own, such as ``flow:``, are carried over and
  never trip it.
- The GDS layouts go under ``layout/`` **with their sidecars**. Each manifest is
  discovered by its GDS's stem, as a sibling, so a layout and its contract move
  together or not at all. The ``.chiplet`` points at the interposer GDS with a
  relative ``layout/<file>`` path, resolved against the ``.chiplet``'s own
  directory.
- DRC output goes under ``reports/``, which is regenerable and safe to delete.
- ``logs/`` holds one timestamped log per run. The dialog's log widget is
  cleared on every run; this is the copy that survives. Two runs of the same
  board within the same second do not collide: the file is opened exclusively
  and a counter suffix is appended.

``MANIFEST.md`` is written at the end of every run. It lists the ``.chiplet``,
the eight ``layout/`` products and the three reports, each with a checkbox
ticked according to what actually appeared on disk, so a partial run is visible
without comparing directory listings. Optional products, the fill files for
example, stay unticked when the run did not ask for them. The manifest also
reports what the previous-export content guard found. Writing it is best effort: a manifest that
cannot be written never fails the export.

.. tip::
   ``adk-new-project`` in the container scaffolds exactly this layout, with a
   ``.gitignore`` that tracks the light deliverables and ignores the heavy ones
   (the complete GDS, the intermediate ``.hyp``, the DRC working directory and
   the logs).

Reaching it
-----------

Inside the container the plugin is already registered. It is symlinked into
``/usr/share/kicad/scripting/plugins/``, and the worker interpreter is the
image's venv, pre-set as ``KICAD_CHIPLET_PYTHON``. Open pcbnew and go to
*Tools > External Plugins > Chiplet Export*.

On a host install there are two steps, with the commands in
:ref:`host_plugin_install`. First, link the repository's
``plugins/chiplet_export`` directory, not the repository root, into KiCad's
scripting plugins folder. The version segment of that folder is the KiCad
version whose configuration you are extending, ``9.0`` for a stock KiCad 9 and
``9.99`` for the ADK fork (:doc:`/tools/01_kicad_adk_mod`). Second, give the
plugin a worker Python: the plugin itself runs inside KiCad's bundled
interpreter, which has neither the KLayout module nor PyYAML, so the GDS worker
runs as a subprocess under a venv of its own.

Then restart pcbnew. If the plugin does not appear, use
*Tools > External Plugins > Refresh Plugins*; a registration failure prints its
import error to KiCad's stdout.

The interpreter is resolved by a four-step chain, first hit wins:

1. The ``KICAD_CHIPLET_PYTHON`` environment variable.
2. ``<plugin_dir>/.venv/bin/python3``.
3. The ``KICAD_CHIPLET_PYTHON`` project text variable, from
   *Board Setup > Text Variables*.
4. ``python3`` from ``PATH``, but only if a subprocess probe can
   ``import klayout.db, yaml`` with it.

Note that step 2 beats step 3: a present-but-broken ``.venv`` wins over a
project text variable. The dialog's *Worker Python* field is the way past that,
and it is the only override that takes effect without restarting KiCad.

What the dialog controls
------------------------

The dialog shows the values the discovery chain resolved as placeholders rather
than leaving fields blank, so an untouched field reads as provenance rather than
as something missing.

Output directory
~~~~~~~~~~~~~~~~

Where the tree above is written. Defaults to the directory holding the loaded
``.kicad_pcb``. In a scaffolded project you point it at the sibling
``outputs/``.

Outputs
~~~~~~~

The canonical ``.chiplet`` and the interposer GDS are **not** toggles. The
worker writes the GDS on every run regardless, and the ``.chiplet`` is unusable
until the same run finalises it, so an opt-out could only throw away work
already done. Two things are optional:

*Complete assembly GDS* (default off)
    The interposer plus every chiplet instance flattened into one layout. This
    is what the assembly DRC checks, so leaving it off also means no assembly
    DRC.

*Annotate chiplet boundaries* (default off)
    A viewer-only annotation layer, discussed below.

The HyperLynx ``.hyp`` is always staged into the output directory next to the
``.chiplet``, so a downstream tool can consume the exact netlist the layout was
generated from.

PDK roots
~~~~~~~~~

Three pickers for the interposer PDK, the interconnect PDK and the ADK
checkout. Each is pre-filled by the ecosystem discovery chain (environment
variable, project text variable, then an upward walk for a conventionally named
sibling checkout, accepting both the ecosystem name and the GitHub repository
name), so the provenance of every dependency is on screen.

Editing one exports the matching environment variable
(``INTERPOSER_PDK_ROOT``, ``INTERCONNECT_PDK_ROOT``, ``ADK_ROOT``) into the
worker subprocesses. Explicit selection *is* the convention's environment leg,
so pointing the export at a vendor's interconnect PDK or a pinned release needs
no code change. Changing the interconnect PDK re-reads the connection-stack list
from that PDK's manifest. See :doc:`/install/03_environment`.

The interposer root is held to IntM4TM2. A tree counts as one when it has
``libs.tech/intm4tm2_stack.json``, the stack descriptor; ``libs.tech/klayout``
cannot tell, because every KLayout PDK has it, the SG13G2 die PDK included. A
set ``INTERPOSER_PDK_ROOT`` (or project text variable) without that file is
shown in the picker as given, and the run is refused with
``CARRIER_UNSUPPORTED_ROOT``, exit 1. It never falls back to a sibling
checkout, which would draw with a PDK you did not choose. Point the variable at
an IntM4TM2 checkout, or unset it to use the sibling one.

Pipeline options
~~~~~~~~~~~~~~~~

*Top cell* (default ``INTERPOSER``)
    The top-level cell name written into the interposer GDS.

*Connection stack*
    The assembly-wide default attachment method, populated from the selected
    interconnect PDK's manifest. Each entry is labelled with the numbers the
    choice turns on, and a line underneath spells the method out in full: pitch,
    minimum spacing, passivation opening, body diameter, stack height by layer,
    vendor. Pitch and spacing are exactly the rules the assembly DRC will check
    against, so the dropdown is showing you the checks you are selecting. When
    no manifest is readable the dropdown falls back to bare method ids rather
    than displaying numbers it cannot source. Empty means the writer leaves each
    die's existing connection untouched.

*Interposer technology LYP*
    The KLayout layer-properties file of the interposer technology. Pre-filled
    from ``INTERPOSER_LYP`` (environment, then project text variable), then the
    PDK's canonical ``libs.tech/klayout/tech/intm4tm2.lyp``. The ``.lyp``
    belongs to the interposer PDK, not to the plugin, so there is no bundled
    copy: when nothing resolves the field stays blank and the export fails
    asking you to set ``INTERPOSER_PDK_ROOT``. Do not point it at the
    interconnect ``.lyp``, which carries bump layers only and is consumed
    automatically through the ``.chiplet``.

*Interposer export report*
    A file picker for the report ``interposer-pnr export`` wrote beside the
    board. Empty by default, and never guessed from the board's path. It is
    required when an export-drawn carrier pad links a sheet symbol, and
    checked against the board whenever it is given; see
    :ref:`chiplet_export_report`. The headless equivalent is
    ``chiplet-export --export-report PATH``.

*I/O pads*
    Auto-extracted from the board's ``IO_CLASS`` footprints, rendered into the
    interposer GDS and injected under the interposer component. A headless
    caller can override with an explicit sidecar via
    ``ExportOptions.io_pads_json``, which must already be in the planner's net
    names; the worker never renames them.

*Cu-pillars*
    Auto-generated from each flip-chip die's footprint pads when that die's
    connection is a Cu-pillar stack. A pre-generated GDS can be supplied through
    ``ExportOptions.cupillar_gds``, which disables the auto-extraction.

.. _export_per_die_settings:

Per-die settings
~~~~~~~~~~~~~~~~

One row per die footprint, with two columns, *Interconnect method* and
*Outline layer (L/D)*. The die thickness sits in the collapsed *3D / advanced*
pane below the table. All three are initialised from the footprint's fields and
written back to them on Run, so the board remains the source of truth and the
choice survives in version control.

**Interconnect method** maps to the ``CONNECTION`` field. A die left on *(use
default)* follows the assembly-wide connection stack; an explicit selection
gives that die its own stack, its own 3D bodies and its own DRC numbers. A value
the current PDK does not declare is kept in the list rather than dropped, so
pointing at another checkout never silently rewrites a board's selection.
Unknown method ids fail the export before the worker starts, rather than
degrading somewhere downstream.

**Outline layer** maps to the ``DIE_OUTLINE_LAYER`` field: the
``LAYER/DATATYPE`` on which the die's own GDS, the file its ``GDS_FILE`` names,
draws the die outline. Use ``39/4``, the SG13G2 ``EdgeSeal`` boundary, for an
SG13G2 die, and ``206/0`` for a black-box die written by gds2kicad's
``blackbox_chiplet.py``. The worker reads that layer from the die GDS, merges
it, and takes the die's width and height in the ``.chiplet``, and its boundary
in the complete GDS, from the one rectangle it finds. It never sizes a die from
the footprint courtyard. The layer must merge to exactly one axis-aligned
rectangle under the file's one top cell; anything else is refused.

The field has no default. A die whose field is empty, or is not two integers from 0
to 65535 separated by ``/``, refuses the run before any output exists, with
``Die outline layer refused:`` followed by every die at fault and the cause.
Two kinds of footprint need no value, and their row shows a note instead of a
text box: a die marked with ``CHIPLET_PAD_DOMAINS``, which keeps the size
archived with its pin list and is passed to the worker as exempt, and a
footprint the ``.chiplet`` does not export as a die (excluded from the bill of
materials, an ``IO_CLASS`` pad, or a ``cap_cmim`` capacitor). Every other
footprint is exported as a die, so it needs a ``GDS_FILE`` and an outline
layer. gds2kicad can write the field into the library footprint
(``--die-outline-layer``, :doc:`/tools/03_gds2kicad`).

**Die thickness** maps to the ``DIE_THICKNESS_UM`` field and becomes the
``.chiplet``'s ``components[].dimensions.thickness``. This is the z-extent of
the *silicon body*, not of the interconnect. A method's stack height comes from
the interconnect PDK manifest and lands in ``position.z``; it is fabrication
data and is deliberately not editable here.

.. note::
   Leaving die thickness empty is not a neutral default. The die exports with
   ``thickness: 0.0``, which the 3Dblox exporter (:doc:`/adk/07_chiplet2dbx`)
   rejects outright and which two
   other consumers each silently replace with a different guess. The export logs
   a warning naming every die that ships a zero, and a second warning for values
   outside roughly 50 to 2000 um, which are almost always millimetres or
   nanometres typed into a micrometre field.

Assembly DRC
~~~~~~~~~~~~

When a complete assembly GDS is produced, the export then runs the ADK's
``run_drc.py`` over it and appends a verdict line to the log:
``assembly DRC: PASSED``, ``FAILED`` or ``NOT RUN``.

A DRC failure does not invalidate the exported artefacts. The export exit code
stays 0 and the verdict is reported separately, because the geometry is a
faithful rendering of the board whether or not the board obeys the rules. A
consumer of ``ExportResult`` must surface ``describe_assembly_drc()`` or check
``assembly_drc_exit_code`` itself; folding the two together would let a failing
deck read as a green run. The headless command does that folding for you and
exits 3 when the DRC did not pass (`Headless use`_). See
:doc:`/adk/05_run_drc`.

.. _chiplet_export_report:

I/O pad carriers and the export report
--------------------------------------

The interposer's I/O pads, its carriers, are the board footprints with an
``IO_CLASS`` field. Each becomes an entry under the interposer's ``io_pads`` in
the ``.chiplet``, and in the ``io_pads.json`` sidecar the worker draws them
from, with an id and a net. Both files are written from the same carrier set,
BOM-excluded carriers included, so they always agree on which pads exist.

**The id.** ``interposer-pnr export`` draws every carrier pad from the
``chiplet_carrier`` footprint library and writes its io_pad id into a hidden
``IO_PAD_ID`` property, because on a board drawn against a sheet the reference
is the sheet's designator (``J1``), not the id. So on a board where any carrier
comes from ``chiplet_carrier`` or carries ``IO_PAD_ID``, every carrier is read
by its ``IO_PAD_ID``. A carrier without one, or two carriers with the same one,
refuse the export. On a board drawn by hand the reference is the id.

**The net.** A carrier's net is the one net all its pads carry. A carrier whose
pads carry different nets is refused, naming them; an unnetted pad counts as a
net of its own.

**The names.** A board that ``interposer-pnr export`` drew against a sheet
carries the sheet's net names, while the ``.chiplet`` and the sidecar name nets
as interposer-pnr, the planner, does. The report that export wrote beside the
board says how to go back, in its ``round_trip`` block. Give it with
``--export-report``, or the dialog's *Interposer export report* field, whenever
an export-drawn carrier links a sheet symbol: a board drawn against a sheet, or
a draft board you updated from its draft sheet in KiCad. A routed net goes back
to its planner name, a pad no routed net binds is written with an empty net,
and a net the report names nowhere is refused. The ``.hyp`` keeps the board's
own names. A board you drew by hand from your own sheet, with carriers from
another library and no ``IO_PAD_ID``, names its nets itself and needs no
report.

The report is checked against the board before anything is taken from it:

- it must be an ``interposer_pnr.export`` report, version 1;
- ``round_trip`` versions up to 6 are read. A newer one is refused with advice
  to update the plugin. A version 6 feature the plugin does not know is
  ignored, because a feature may only add a block, never rename a net;
- a report written for another board, one with other carrier references or
  another ``IO_PAD_ID`` on one of them, is refused;
- a report of a board that follows a sheet is refused on a board where no
  carrier links a sheet symbol, or where no carrier was drawn by export.

All of this runs before the output directory is created, so a refused board
leaves nothing behind. The message says which input is at fault.
``Export report refused: ...`` means the file is not a report the plugin reads.
``IO pad carriers refused: ...`` means the board's carriers and the report (or
its absence) do not fit; a carrier is named by its reference, followed by
``(io_pad <id>)`` where the two differ. When the report is the cause, the
command line appends ``; the export report is the file given with
--export-report`` and the dialog appends ``; the export report is the file in
'Interposer export report'``. A ``--export-report`` path that does not exist
exits 2 before the run starts.

The rules for reading the report are interposer-pnr's own, vendored into the
plugin as ``vendor/round_trip_names.py``. gds2kicad's ``kicad_pcb_to_iopads.py``
carries the same file, so both read a board's carriers alike
(:doc:`/tools/03_gds2kicad`).

The orchestrator
----------------

``pipeline/orchestrator.py`` is where the flow actually lives. It imports
neither wx nor pcbnew at module load, which is what makes its argument
construction unit-testable on plain host Python, and it exposes three things:
``ExportOptions``, ``build_cli_args`` and ``run_export``.

The sequence
~~~~~~~~~~~~

``run_export`` runs this, in order:

1. Preflight the board, before anything exists on disk: a selected
   interconnect PDK root must hold its manifest, the die footprints marked
   with ``CHIPLET_PAD_DOMAINS`` must carry usable pad metadata, every other die
   must declare its ``DIE_OUTLINE_LAYER`` (`Per-die settings`_), and the
   board's carriers are checked against the export report, when one is given
   (:ref:`chiplet_export_report`). A refusal here returns with nothing
   written.
2. Create the output directory and its ``layout/`` subdirectory. The worker does
   not create parent directories, so this has to happen first.
3. Resolve the worker Python and ``hyp_to_gds.py``, failing immediately if
   either is missing.
4. Create a scratch workspace directory.
5. Write the HyperLynx ``.hyp`` and the intermediate ``.chiplet`` into the
   workspace using the Python ports of the two C++ exporters.
6. Auto-extract, from the board, whatever was not supplied explicitly: the I/O
   pads, the per-die pad locations that drive Cu-pillar generation, the per-die
   ``CONNECTION`` methods and the per-die ``DIE_THICKNESS_UM`` values.
7. Validate the per-die method ids against the interconnect PDK manifest.
8. Only now stage the intermediate ``.chiplet`` and the ``.hyp`` into the output
   directory, so a validation failure leaves no partial artefact behind.
9. Run ``hyp_to_gds.py`` as a subprocess, streaming stdout and stderr into the
   log.
10. Run the assembly DRC, if there is a complete GDS to check.
11. Write ``MANIFEST.md`` and remove the workspace.

.. note::
   Step 9 rewrites the staged ``.chiplet`` in place. If the worker fails or is
   cancelled it never gets that far, which would leave an unfinalised file
   sitting under the exact name a good one would have. The orchestrator renames
   it to ``<board>.chiplet.unfinalized`` and says so in the log, and
   ``ExportResult.chiplet_path`` is left empty. A headless caller therefore
   never receives a path to a file its consumer will reject.

Turning a design into runner flags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``build_cli_args`` is a pure function from ``ExportOptions`` to the argv handed
to ``hyp_to_gds.py``. The mapping is direct:

.. list-table::
    :header-rows: 1
    :widths: 38 62

    * - Option
      - Flag
    * - always
      - ``-o layout/<board>_interposer.gds``
    * - ``top_cell``
      - ``-c <name>``
    * - ``lyp_override``
      - ``-l <path>``
    * - ``emit_complete_gds``
      - ``--with-chiplets --complete-output layout/<board>_complete.gds``
    * - ``annotate_boundaries``
      - ``--annotate-boundaries``
    * - ``emit_chiplet``
      - ``--update-chiplet-file <output-dir>/<board>.chiplet``
    * - ``connection_type``
      - ``--connection-type <id>``
    * - ``die_connections``
      - ``--die-connections REF=method,...``
    * - ``die_thicknesses``
      - ``--die-thicknesses REF=um,...``
    * - ``io_pads_json``
      - ``--io-pads <path>``
    * - ``cupillar_gds``
      - ``--cupillar-gds <path>``
    * - ``pad_locations``
      - ``--pad-locations REF=path,...``

``export_report`` has no runner flag. The writers apply it in steps 5 and 6,
so the ``io_pads.json`` the worker reads is already in the planner's names.

The ``-o`` flag is unconditional for a specific reason: without it the worker
writes the interposer GDS next to the ``.hyp``, which lives in the workspace
directory the orchestrator deletes on the way out. The boundary and pillar
sidecars would go with it, and the finalised ``.chiplet`` would be left pointing
``layout:`` at a path that no longer exists.

The ``REF=VALUE,...`` encodings are split on ``,`` and then ``=``, so a
reference or a value containing either character is rejected before the run
starts rather than silently corrupting the mapping. Pad-location *values* are
exempt, because they are plugin-generated temporary paths.

The two adapter axes
~~~~~~~~~~~~~~~~~~~~

When it comes to the assembly DRC, the orchestrator reads two independent
adapter axes from the ``.chiplet`` and forwards each only when it applies. Both
are read with a small hand-rolled parser, because KiCad's bundled Python has no
PyYAML: a block header counts only at column zero, quoted and unquoted values
are both accepted, and ``#`` comments are stripped except inside quotes.

**Interposer axis.** ``interposer.adapter`` becomes
``--interposer-adapter <value>``, and it is always emitted. When the field is
absent, unreadable or empty it falls back to ``intm4tm2``, which is the only
interposer adapter shipped today.

.. code-block:: yaml

    interposer:
      adapter: "intm4tm2"

**Interconnect axis.** ``interconnect.adapter`` becomes
``--interconnect-adapter <value>``, and it is emitted **only when the design
declares one**. Its default is the empty string, meaning no interconnect axis at
all.

.. code-block:: yaml

    interconnect:
      adapter: "ihp_cupillar"

The asymmetry is deliberate. A ``.chiplet`` written before the interconnect axis
existed carries no ``interconnect:`` block. Defaulting that to a Cu-pillar
adapter would mean that opening an old design and re-exporting it silently
subjects it to bump pitch and spacing rules it was never designed against, and
the user would see new violations with no change to the design to explain them.
A design opts into the IXN axis by declaring an adapter; it never acquires it by
accident. See :doc:`/adk/02_adapter_contract` and :doc:`/adk/04_ixn_rules`.

There is a third input on the same axis. When the orchestrator can derive a
``{method: [dies]}`` mapping from the ``.chiplet``'s per-die connections and the
interconnect PDK manifest, it writes an ``.ixn_methods.json`` sidecar next to
the complete GDS and passes ``--interconnect-methods <path>``. Dies the boundary
manifest does not declare are dropped from that mapping first, because the deck
raises on a sidecar naming a die it cannot find. Either flag activates the IXN
axis. Derivation is best-effort: if it fails, the run falls back to
assembly-global interconnect behaviour and logs a warning.

An override on either axis, passed as ``ExportOptions.interposer_adapter`` or
``interconnect_adapter``, beats the file. When ``emit_chiplet`` is off and there
is no staged file to read, the adapters are read from the intermediate in the
workspace, so the DRC still honours the design's real adapters instead of
falling back to ``intm4tm2``.

Boundaries: manifest, not layer
-------------------------------

Alongside the assembly GDS the worker writes a ``<stem>.boundaries.json``
manifest: one mechanical boundary polygon per placed chiplet, each carrying its
identity (``instance``, ``source_die``, ``transform``) in both database units
and micrometres, plus the layout's DBU, the top cell name and a SHA-256 of the
GDS it describes. It is written on every run, even when there are zero
boundaries, so a manifest is always present beside a layout. The assembly DRC
runner auto-discovers it as a sibling of ``--path``.

The boundary lives **only** in the manifest. It is never stamped on a GDS layer,
which keeps the assembly contract PDK-agnostic and stops assembly metadata
aliasing process geometry. :doc:`/formats/04_boundary_manifest` records why the
boundary left the fabrication-layer namespace.

For eyeball inspection, ``--annotate-boundaries`` paints the same polygons plus
an instance label onto an annotation layer, 1000/0 by default and overridable
with ``--boundary-viz-layer``, well outside the fabrication range. Open the GDS
in KLayout and you can see where each die sits.

.. note::
   That layer is read by **no** rule. It carries no contract, it cannot produce
   a false clean result, and it cannot alias a fabrication layer. The manifest
   remains the sole assembly contract. The option is off by default so the
   production GDS carries no synthetic geometry, and painting is idempotent: the
   layer is cleared in the top cell before each pass, so repeated writes do not
   accumulate duplicate shapes.

The worker writes a second sidecar, ``<stem>.pillars.json``, whenever the bump
generation path runs, including runs that place zero bumps. It records one entry
per drawn bump with its device reference, pin name, connection method, body
diameter and centre coordinates. Those coordinates are rebased into the same
canonical frame the ``.chiplet``'s die positions and I/O pads use, which is what
lets a manifest-level check compare the two sidecars directly rather than
re-deriving geometry from the GDS. Bumps that the collision auto-resolve moved
are flagged. See :doc:`/formats/04_boundary_manifest` and
:doc:`/formats/05_pillar_manifest`.

Headless use
------------

Two headless entry points exist.

``chiplet_export_cli.py`` is the first-class command-line face of the pipeline,
and ``chiplet-export`` in the tools image runs it. It must run under an
interpreter that can ``import pcbnew``, which means the KiCad fork's
interpreter; the image's command already does. The worker Python for the GDS
step is resolved separately through the discovery chain.

.. code-block:: bash

    chiplet-export \
        --board /path/to/board.kicad_pcb \
        --output-dir /path/to/outputs

Unlike the dialog, the command always asks for the complete assembly GDS and
always runs the assembly DRC; the top cell is fixed at ``INTERPOSER``. The DRC
is required by default, and the exit status says how the run ended:

.. list-table::
    :header-rows: 1
    :widths: 10 90

    * - Exit
      - Meaning
    * - 0
      - The files were written and the assembly DRC passed.
    * - 1
      - Nothing trustworthy was written: a refused board, a failed worker, a
        ``.chiplet`` that could not be replaced, or a crash before the DRC.
    * - 2
      - The board, or the file given with ``--system-chiplet``,
        ``--export-report`` or ``--die-layouts``, is missing, or KiCad cannot
        read the board; also a usage error.
    * - 3
      - The files were written and the assembly DRC did not pass: it failed,
        was refused or did not run.

``--allow-drc-fail`` turns exit 3 into 0, and the last line still says how the
DRC ended. ``--require-drc`` is accepted for older callers and changes nothing.
``--interposer-adapter``, ``--interconnect-adapter`` and ``--connection``
override the corresponding options.

A board ``interposer-pnr export`` drew against a sheet takes its export report,
exactly as the dialog's field does (:ref:`chiplet_export_report`):

.. code-block:: bash

    chiplet-export \
        --board pnr/<system>.draft.kicad_pcb \
        --system-chiplet design.chiplet \
        --export-report pnr/export.json \
        --output-dir out/export

``--system-chiplet`` names the System ``.chiplet`` the assembly was built from;
the interposer and each die take the technology of the System component with
the same id. The interposer's technology must be ``intm4tm2``: a System whose
carrier names another technology is refused with
``CARRIER_UNSUPPORTED_TECHNOLOGY``, exit 1, nothing written. IntM4TM2 is the
only carrier the export models. The plugin's command reference, linked at the
foot of this page, lists every flag.

``run_export`` is the Python API the dialog itself calls. The package is
``chiplet_export``, so the repository's ``plugins/`` directory has to be on
``sys.path``:

.. code-block:: python

    import sys
    sys.path.insert(0, "/path/to/Chiplets-KiCad-Plugin/plugins")

    import pcbnew
    from chiplet_export.pipeline.orchestrator import (
        ExportOptions, run_export, describe_assembly_drc,
    )

    board = pcbnew.LoadBoard("/path/to/board.kicad_pcb")
    options = ExportOptions(
        output_dir="/path/to/outputs",
        emit_complete_gds=True,
        top_cell="INTERPOSER",
    )
    result = run_export(board, options,
                        plugin_dir="/path/to/Chiplets-KiCad-Plugin/plugins/chiplet_export",
                        on_log=print)
    assert result.exit_code == 0 and not result.error
    print(describe_assembly_drc(result))

.. tip::
   ``plugins/chiplet_export/tests/regenerate_wirebond_demo.py`` in the plugin
   repository is a complete worked example, and it is what the container's
   verify stage runs to regenerate the reference design headless on every image
   build. See
   :doc:`/flow/08_reference_design`.

Writer parity
-------------

The plugin does not call the C++ exporters at run time.
``writers/chiplet_writer.py`` and ``writers/hyperlynx_writer.py`` are Python
ports that
reproduce them, driven through the pcbnew SWIG bindings, and the SWIG-exposed
``ExportBoardToChipletFile`` and ``ExportBoardToHyperlynxFile`` are used as the
reference in a byte-exact regression test rather than in the pipeline.

Two consequences follow, and both are checked by the test suite. The Python
writers must not diverge even in details that look harmless: the chiplet writer
looks ``INTERPOSER_ADAPTER`` and ``INTERCONNECT_ADAPTER`` up in the project text
variables *only*, never in the board properties, because the C++ exporter does
the same and a board property shadowing a text variable would break parity. And
the HyperLynx writer needs to walk the physical stackup, which is why the fork
exposes ``BOARD_STACKUP`` to SWIG at all. See :doc:`/tools/01_kicad_adk_mod`.

Troubleshooting
---------------

.. list-table::
    :header-rows: 1
    :widths: 42 58

    * - Symptom
      - Cause
    * - "Could not locate a usable worker Python"
      - No step of the interpreter chain resolved. Create the ``.venv``, set
        ``KICAD_CHIPLET_PYTHON``, or point the dialog's *Worker Python* field at
        an interpreter directly.
    * - "Hyperlynx writer aborted"
      - Most commonly the board has no closed ``Edge.Cuts`` outline. The writer
        needs one to derive the bounding box. Add an enclosing polygon.
    * - Run button never re-enables
      - A previous run is still in flight. Cancel terminates the worker
        subprocess.
    * - Output directory empty, no ``.chiplet``
      - Check the exit code in the status line. Worker stderr is preserved in
        the log under a ``[stderr]`` prefix, and in the run log under
        ``logs/``.
    * - Cu-pillars missing in the 3D view
      - Pillars are generated only when a die's connection is a Cu-pillar stack.
        Set it per die or assembly-wide, then re-run.
    * - Plugin absent from External Plugins
      - Check the symlink, then *Tools > External Plugins > Refresh Plugins*.
        A failed import prints its traceback to KiCad's stdout.
    * - "IO pad carriers refused: carrier pad J1 is linked to a sheet
        symbol, ..."
      - The board was drawn by ``interposer-pnr export`` and follows a sheet.
        Give the report export wrote beside it in *Interposer export report*
        or with ``--export-report``.
    * - "... was written for another board: its carrier pads differ"
      - The report belongs to another board, or to the draft when you gave
        the sheet board, or the reverse. Give the report written with this
        board.
    * - "Export report refused: ... unsupported round_trip version"
      - The report is newer than the plugin reads. Update the plugin.
    * - ``CARRIER_UNSUPPORTED_ROOT``
      - ``INTERPOSER_PDK_ROOT`` points at a tree without
        ``libs.tech/intm4tm2_stack.json``, often the SG13G2 die PDK. Point it
        at an IntM4TM2 checkout or unset it.
    * - "ERROR: track ends refused" in the log
      - Two nets' traces touch on one layer once their ends are drawn square.
        Widen the clearance at the places it names; see
        :doc:`/flow/05_hyp_to_gds`.

The plugin's own pages
----------------------

The plugin repository keeps its README, its command reference and its status
for this site. They are built from the pinned checkout as they stand.

.. toctree::
    :maxdepth: 2

    /_repos/Chiplets-KiCad-Plugin/docs/index
