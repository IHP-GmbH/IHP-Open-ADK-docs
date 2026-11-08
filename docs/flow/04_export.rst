Exporting the assembly
======================

.. include:: /common.inc

Export is the point where a KiCad board stops being a board and becomes an
assembly: a set of GDS layouts, a machine-readable assembly description, the
manifests the checks need, and the reports those checks produce. One dialog
does all of it.

This page covers running the export and understanding every file it leaves
behind. :doc:`/tools/02_chiplet_export_plugin` is the reference for the plugin
itself, and :doc:`/flow/05_hyp_to_gds` for the converter it drives.

Running the export
------------------

1. Open the assembly board in ``pcbnew``.
2. *Tools > External Plugins > Chiplet Export*.
3. Fill in the dialog and click **Run**. Log lines stream into the dialog while
   the worker runs; **Cancel** terminates the worker subprocess.

The fields that matter:

**Output directory.**
   Where the artefacts land. Point it at your project's ``outputs/``
   directory, the sibling of ``kicad/``. In a scaffolded project the dialog
   already does that for you: when the loaded board sits in a directory named
   ``kicad`` that has a sibling ``outputs/``, that sibling is the default.
   Anywhere else the default is the directory holding the ``.kicad_pcb``,
   which is rarely what you want once the project has grown an ``outputs/``
   tree.

**Complete assembly GDS** (default off).
   The interposer plus every die instance flattened into one GDS. Enable it:
   the ADK assembly DRC needs it, and with it off there is no assembly check.

**Annotate chiplet boundaries** (default off).
   Paints each chiplet boundary and its instance label onto a viewer-only
   annotation layer, ``1000/0``, for eyeball inspection in KLayout. No rule
   reads that layer. The assembly contract lives in the boundary manifest, not
   in the GDS, which is what stops it aliasing a fabrication layer.

**PDK roots.**
   The interposer, interconnect and ADK checkouts the pipeline will use. Each
   field is pre-filled by the discovery chain, so the provenance of every
   dependency is visible rather than implicit. Edit one to export against a
   different checkout.

**Connection stack (default).**
   The assembly-wide attachment method, drawn from the interconnect manifest.
   Each entry is labelled with the numbers it turns on, for example
   ``cupillar_opt1 - 75um pitch, 44um dia``, and those are the very numbers the
   interconnect rules will check. Per-die ``CONNECTION`` fields override it.

**Per-die settings.**
   One row per die footprint, initialised from the board and written back to it
   on Run: the interconnect method and the outline layer
   (``DIE_OUTLINE_LAYER``), with the die thickness in the collapsed
   *3D / advanced* pane. The outline layer is required: an empty one stops the
   run. :doc:`/flow/03_interposer_design` describes the fields and
   :ref:`export_per_die_settings` has the rules.

**Interposer export report.**
   Only for a board ``interposer-pnr export`` drew against a sheet, or a draft
   board you updated from its draft sheet. Pick the report export wrote beside
   the board; the export then names the I/O pad nets as the planner does. A
   board you drew by hand needs none. The headless equivalent is
   ``chiplet-export --export-report PATH``, and
   :ref:`chiplet_export_report` has the rules.

**Worker Python.**
   The interpreter that runs ``hyp_to_gds.py`` and the ADK DRC. The placeholder
   shows what the discovery chain resolved, so an empty field reads as
   provenance rather than as something missing.

What happens when you press Run
-------------------------------

.. code-block:: text

    0. preflight the board                               (refuses, nothing written)
         interconnect PDK manifest, carrier pad domains,
         die outline layers, I/O pad carriers, export report
    1. resolve the worker Python and hyp_to_gds.py       (fails early if absent)
    2. write <board>.hyp                                 (HyperLynx writer)
    3. write the intermediate <board>.chiplet            (chiplet writer)
    4. stage both into the output directory
    5. run hyp_to_gds.py
         -> layout/<board>_interposer.gds
         -> layout/<board>_complete.gds        (when enabled)
         -> layout/*.boundaries.json
         -> layout/*.pillars.json
         -> rewrite <board>.chiplet in place, finalised
    6. run the ADK assembly DRC over the complete GDS    (when enabled)
         -> reports/<board>_assembly_drc.lyrdb

Step 0 checks, in this order: that a selected interconnect PDK root holds its
``manifest/interconnect_methods.json``; that every die footprint marked with
``CHIPLET_PAD_DOMAINS`` carries pad metadata the export can use; that every
other die declares a usable ``DIE_OUTLINE_LAYER``; and that the I/O pad
carriers can be named, which refuses a carrier on two nets, a missing or
repeated ``IO_PAD_ID`` on a board export drew, or a missing or wrong export
report. Each refusal is listed under `Common failures`_. Steps 2 and 3 are
Python ports of the KiCad C++ exporters, and they are held byte-exact against
them by the plugin's regression tests. Step 5 is where the geometry is actually
built. Step 6 is a check, not a gate: a DRC failure does not invalidate the
exported artefacts, the dialog's run still succeeds, and the verdict is
reported separately as ``assembly DRC: PASSED / FAILED / NOT RUN`` with the
report path. The headless command, below, exits 3 in that case unless you pass
``--allow-drc-fail``.

Headless
--------

The same pipeline runs without the GUI. In the tools image, the end-to-end self
test exercises it on the reference design, copied to ``/work/example`` as
:doc:`/install/01_container` describes:

.. code-block:: bash

    adk-smoke /work/example/kicad/two_die_interposer.kicad_pcb

To export a specific board headless, run the command the dialog's **Run** stands
for. From ``/work``, on the board you drew in a project ``adk-new-project`` made:

.. code-block:: bash

    chiplet-export \
        --board       heterogenic-designs/my_design/kicad/my_design.kicad_pcb \
        --output-dir  heterogenic-designs/my_design/outputs

It always writes the complete assembly GDS and always runs the assembly DRC.
Exit 0 means the files were written and the DRC passed, and exit 3 that they
were written but the DRC did not pass; ``--allow-drc-fail`` turns that 3 into
0. Add ``--export-report PATH`` for a board drawn against a sheet.
:ref:`chiplet_export_headless` has the full exit table and the flags.

.. note::
   Anything headless must run under a Python that can ``import pcbnew``, which
   means the KiCad build's own interpreter. The worker Python for
   ``hyp_to_gds.py`` is resolved separately through the discovery chain, and
   the two are usually different interpreters.

The output tree
---------------

This is the reference design's ``outputs/`` directory, exactly as it ships,
with the regenerated files that its ``.gitignore`` keeps out shown in
parentheses:

.. code-block:: text

    outputs/
      two_die_interposer.chiplet                        deliverable
      two_die_interposer.chiplet.exportcontent.sha256   deliverable
      MANIFEST.md                                       deliverable
      (two_die_interposer.hyp)                          regenerated
      layout/
        two_die_interposer_interposer.gds               deliverable
        two_die_interposer_interposer.boundaries.json   deliverable
        two_die_interposer_interposer.pillars.json      deliverable
        two_die_interposer_complete.boundaries.json     deliverable
        two_die_interposer_complete.pillars.json        deliverable
        two_die_interposer_complete.ixn_methods.json    deliverable
        (two_die_interposer_complete.gds)               regenerated
      reports/
        two_die_interposer_assembly_drc.lyrdb           deliverable
        two_die_interposer_cupillar_drc.json            deliverable
        (assembly_drc/)                                 scratch
      (logs/)                                           scratch

The split is deliberate. The ``.chiplet`` sits at the root and references its
interposer GDS by a ``layout/<file>`` relative path, resolved against the
``.chiplet``'s own directory. It then auto-detects the ``_complete.gds`` from
that same directory, and the assembly DRC finds each sidecar next to its GDS.
So layouts and their sidecars travel together under ``layout/``, reports under
``reports/``, and only the two index files and the ``.chiplet``'s digest
sidecar sit at the root.

The reference design runs without metal fill. With fill on
(:ref:`hyp_to_gds_fill_seal_ring`), two more files appear:
``layout/<board>_interposer.fill_coverage.json`` and
``reports/<board>_fill_density.json``.

File by file
------------

``<board>.chiplet``
~~~~~~~~~~~~~~~~~~~

The assembly description, and the file you open in Chiplet Studio. YAML,
readable, diffable. It names the assembly, the interposer adapter, every
technology with a path to its layer-properties file, the expanded connection
stacks, and one component entry per interposer and per die.

The version written in step 3 is **intermediate**: board coordinates are not
yet in the canonical frame, and the file carries a
``_metadata.finalize_required: true`` marker. ``hyp_to_gds.py`` rewrites it in
place once the interposer GDS exists, re-anchors every position to the GDS
bounding-box corner frame, and strips the marker. Readers refuse a file that
still carries it, so an aborted export cannot be mistaken for a finished one.

If you find a ``.chiplet`` with ``finalize_required`` still set, the worker
step failed. Read the dialog log rather than the file.

:doc:`/formats/01_chiplet` and :doc:`/formats/02_chiplet_components` are the
field reference; :doc:`/formats/03_coordinate_frames` explains the frame.

``<board>.chiplet.exportcontent.sha256``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A digest of the exporter-owned content of the ``.chiplet``, recorded after each
successful export. The next export compares the file on disk against it before
replacing the ``.chiplet``: if you edited an exporter-owned field by hand, a
position for example, the re-export stops instead of overwriting your edit.
Blocks the exporter does not own, such as ``flow:`` and ``netlist:``, are
carried over and do not change the digest. ``MANIFEST.md`` reports what the
check found under *Previous-export content guard*. It says nothing about
whether the content is correct. Keep it next to the ``.chiplet``.

``MANIFEST.md``
~~~~~~~~~~~~~~~

A generated index of everything the run produced, one line per file with its
role, and a note on which directories are safe to archive or delete. It is
regenerated by every export, so it always describes the run that produced it.
Read it first when you come back to an old project.

``<board>.hyp``
~~~~~~~~~~~~~~~

The HyperLynx file: the board's netlist and geometry in the format
``hyp_to_gds.py`` consumes. It is written on every run and staged into the
output directory as a first-class output, so other tools can consume the exact
netlist the layout was generated from.

It is also the largest purely intermediate artefact in the tree. The scaffolded
``.gitignore`` excludes it: it is regenerated from the board on every export,
and the GDS it produced is committed instead.

``layout/<board>_interposer.gds``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The interposer layout alone: routing mapped onto the technology's metals by
layer name, vias built from real PDK parametric cells rather than plain
rectangles, the I/O pads rendered from the board's ``IO_CLASS`` footprints, and
the Cu pillars or bumps generated from each flip-chip die's footprint pads.

This is the file the ``.chiplet`` references, and it is a deliverable: it is
the fabrication-oriented view of what you designed.

It is not a copy of what KiCad shows. A free trace end that KiCad draws as a
round cap is square in the GDS, reaching half a track width past its endpoint,
so the GDS can hold slightly more copper at a trace end than the board.
:doc:`/flow/05_hyp_to_gds` explains which ends are drawn square and what that
does to clearance.

``layout/<board>_complete.gds``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The same interposer with every die instance placed into it, at its exported
position, rotation and mirroring. This is what the assembly DRC runs on.

It is heavy, it is fully derived from the interposer GDS plus the ``.chiplet``,
and the scaffolded ``.gitignore`` keeps it out of version control. Regenerate
it by re-running the export.

``layout/<stem>.boundaries.json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The chiplet boundary manifest, schema ``adk-boundary-manifest``, version
``1.0.0``. One record per placed chiplet: the instance reference, the source
die cell, the placement transform (origin, rotation, mirror, magnification) and
the boundary polygon in both database units and micrometres. The header carries
the database unit, the top cell and the SHA-256 of the GDS it describes.

.. code-block:: json

    {
      "instance": "U2",
      "source_die": "Metal_Test",
      "class": "chiplet",
      "transform": {
        "origin_um": [134670.234, -68981.73],
        "rotation_deg": 0.0,
        "mirror_x": true,
        "magnification": 1.0
      },
      "polygon_um": [[134281.234, -70280.528], "..."]
    }

This manifest is the assembly contract. The DRC runner auto-discovers the
sidecar next to the GDS and aborts if it is absent.

Both GDS files get one. The interposer manifest has an empty ``boundaries``
array, because the interposer alone contains no placed chiplets; the complete
manifest carries one entry per die. Keep both: they are small, and the SHA-256
ties each one to the exact GDS it was generated from.
:doc:`/formats/04_boundary_manifest` is the schema reference.

``layout/<stem>.pillars.json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Cu-pillar manifest, schema ``adk-pillar-manifest``, version ``1.1.0``. One
record per placed bump, as drawn:

.. code-block:: json

    {
      "device_ref": "U1",
      "pin_name": "DIV_OUTn",
      "method": "cupillar_opt1",
      "x_um": 2154.121,
      "y_um": 1122.685,
      "diameter_um": 44,
      "moved_by_auto_resolve": false
    }

Positions are in the same canonical frame as the ``.chiplet`` die positions and
the I/O pads, y-up and in micrometres, recorded *after* collision auto-resolve.
Bumps the auto-resolve moved are flagged, which is the cheapest way to find out
that a pad pitch was tighter than the method allows. The x and y values are
authoritative for manifest-level checks; the GDS remains the fabrication ground
truth.

The file is written whenever the bump-generation path runs, including runs that
place no bumps at all, in which case the ``pillars`` array is empty. An absent
file and an empty one mean different things.

The reference design's manifest holds 116 pillars, 58 per die, two of which
were moved by auto-resolve. :doc:`/formats/05_pillar_manifest` is the schema
reference, and :doc:`/adk/08_pads_vs_pillars` explains how pads and pillars
relate.

``layout/<stem>.ixn_methods.json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The per-method interconnect sidecar, schema ``adk-ixn-methods``, version
``1.0.0``. It is derived from the ``.chiplet``'s per-die ``connection``
identifiers and the interconnect manifest, and it tells the assembly DRC which
numbers apply to which dies:

.. code-block:: json

    {
      "methods": {
        "cupillar_opt1":     {"dies": ["U1"], "IXN_spacing": 40.0,
                              "IXN_pitch": 75.0, "IXN_pad_size": 35.0},
        "vendorx_microbump": {"dies": ["U2"], "IXN_spacing": 15.0,
                              "IXN_pitch": 50.0, "IXN_pad_size": 35.0}
      }
    }

Without it the interconnect checks are assembly-global, which means an assembly
mixing a 75 um pitch method with a 50 um pitch method has to be checked against
one of them. With it, each method's numbers run on the attachment pads under
its own dies, a conservative cross-method spacing covers the gap between
different methods, and the adapter numbers cover any pad outside every method
region. It is written only when the export can derive a per-method mapping.
See :doc:`/formats/06_ixn_methods`.

``reports/<board>_assembly_drc.lyrdb``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ADK assembly DRC result, a KLayout marker database. Open it over the
complete GDS in KLayout to see each violation in place. Its structure is
identical to the interposer technology's own DRC output, so the same review
workflow applies to both.

The DRC's scratch working directory, ``reports/assembly_drc/``, is created
alongside it and is not worth keeping.

``reports/<board>_cupillar_drc.json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Cu-pillar connection check, as JSON: the parameters used per method and the
result per device. It exists so that warn-and-continue violations, which scroll
past in the dialog log, survive the run in a form you can diff.

Deliverables and intermediates
------------------------------

The scaffolded project ``.gitignore`` encodes the split. Ignored:

.. code-block:: text

    outputs/layout/*_complete.gds
    outputs/*.hyp
    outputs/reports/assembly_drc/
    outputs/logs/

Everything else under ``outputs/`` is tracked on purpose: the ``.chiplet`` and
its digest sidecar, the ``MANIFEST.md``, the interposer GDS, the boundary,
pillar and interconnect sidecars, and the DRC reports.

The obvious split, track sources and ignore all outputs, is not the one used
here. A fresh clone should open the design in Chiplet Studio and show the
recorded DRC results without re-running the flow, which needs the ``.chiplet``,
the interposer GDS and the sidecars. It does not need the two artefacts that are
large and fully derived: the complete GDS and the ``.hyp``.

Checking the export
-------------------

**Read the status line.** ``assembly DRC: PASSED`` is the one you want.
``NOT RUN`` usually means the complete assembly GDS was not enabled, or the
KLayout command line is unavailable.

**Read ``MANIFEST.md``.** The ``.chiplet``, every ``layout/`` product and every
report is listed, ticked ``[x]`` when it is on disk. An unticked ``[ ]`` entry
is either an output the run did not ask for, such as the fill files without
fill, the pillar files without a Cu-pillar stack, or the complete GDS, its
sidecars and the assembly DRC report with the complete GDS off, or a stage that
failed quietly. Compare the unticked entries against the options you ran with.

**Check the ``.chiplet`` was finalised.** No ``_metadata`` block should remain.

**Open the result:**

.. code-block:: bash

    chiplet-studio outputs/<board>.chiplet

Dies at the wrong height, missing pillars or a die at the wrong place are all
visible immediately, and all of them trace back to a board field rather than to
the export. :doc:`/flow/07_view_and_inspect` covers the inspection workflow.

**Re-run the DRC on its own** when you want to change adapters or scoping
without re-exporting. To repeat what the export ran, pass the interconnect
adapter the ``.chiplet`` declares under ``interconnect.adapter``
(``vendorx_microbump`` in the reference design) and the per-method sidecar:

.. code-block:: bash

    adk-drc --path outputs/layout/<board>_complete.gds \
            --interposer-adapter intm4tm2 \
            --interconnect-adapter vendorx_microbump \
            --interconnect-methods outputs/layout/<board>_complete.ixn_methods.json \
            --run_dir outputs/reports/assembly_drc

Both interconnect flags are optional. Leave them out and the run checks the
placement rules only: the interconnect checks are dropped without an error,
and the report is clean of IXN violations because none were looked for.
:doc:`/adk/05_run_drc` documents every flag.

Common failures
---------------

``Interconnect PDK source refused: the resolved interconnect PDK root at ... does not contain manifest/interconnect_methods.json``
    The interconnect PDK root in the dialog, or ``INTERCONNECT_PDK_ROOT``,
    points at a directory that is not a complete interconnect PDK checkout.
    Point it at one.

``Carrier pad domains refused: ...``
    A die footprint marked with ``CHIPLET_PAD_DOMAINS`` carries pad metadata
    the export cannot render as carrier copper. The message names the
    footprint and the cause.

``Die outline layer refused: U1, U2: ...``
    The message names every footprint at fault and its cause, so one run
    reports them all. A missing or malformed ``DIE_OUTLINE_LAYER`` is fixed in
    the dialog's *Outline layer* column or on the footprint (``39/4`` for an
    SG13G2 die). A part that is not a die, such as a resistor or a connector,
    has no ``GDS_FILE`` and no dialog row: set *Exclude from bill of materials*
    on its symbol, or give it a ``GDS_FILE`` if it is a die. A reference two
    parts share is fixed by renaming one. :ref:`export_per_die_settings` has
    the rules.

``Attach frame refused: ...``
    The worker could not read the mount plane from the interposer PDK, which
    every export needs. Set ``INTERPOSER_PDK_ROOT`` to an IntM4TM2 checkout;
    :ref:`hyp_to_gds_attach_frame` explains why there is no fallback.

``Die outline refused: U1: ...``
    The worker found the declared layer in the die GDS empty, or not one
    axis-aligned rectangle, or the GDS has more than one top cell. Nothing is
    written. Check the layer in KLayout against the ``GDS_FILE`` the footprint
    names.

``Hyperlynx writer aborted``
    Most commonly the board has no closed ``Edge.Cuts`` outline. The writer
    needs one to derive units and the bounding box.

``Could not locate a usable worker Python``
    Create the plugin virtual environment, set ``KICAD_CHIPLET_PYTHON``, or
    point the dialog's *Worker Python* field at an interpreter. The dialog
    field is the only override that takes effect without restarting KiCad,
    which matters when a present-but-broken virtual environment is winning over
    the project text variable.

No Cu pillars in the rendered assembly
    Pillars are generated only for a die whose connection is a Cu-pillar stack.
    Check the die's ``CONNECTION`` field or the assembly-wide default, then
    re-run.

A die exported with ``thickness: 0.0``
    ``DIE_THICKNESS_UM`` was never set on that die. The export names every die
    that ships a zero in its warnings.

``Export report refused: export report ...``
    The file given as the export report cannot be read, or is not a report
    ``interposer-pnr export`` writes. Give the report written with this board;
    see :ref:`chiplet_export_report`.

``IO pad carriers refused: carrier pad J1 is linked to a sheet symbol, ...``
    The board was drawn by ``interposer-pnr export`` against a sheet, or is a
    draft updated from its sheet, so its nets may be the sheet's. Give the
    report export wrote beside it in *Interposer export report*. A report
    "written for another board" is the wrong one: take the report written
    with this board.

``IO pad carriers refused: carrier ...: its pads carry different nets``
    One I/O pad footprint has pads on two nets, an unconnected pad included.
    A carrier carries one net; fix the board.

``ERROR: track ends refused: ... place(s) where two nets' traces touch``
    Once their ends are drawn square, traces of two nets meet on one layer. The
    worker writes no GDS and the run fails. Widen the clearance at each place
    the message names; :doc:`/flow/05_hyp_to_gds` has the geometry.

Next
----

:doc:`/flow/05_hyp_to_gds` explains what the worker actually does with the
``.hyp``, and :doc:`/flow/06_verification_stages` covers what the assembly DRC
checks and what it cannot see.
