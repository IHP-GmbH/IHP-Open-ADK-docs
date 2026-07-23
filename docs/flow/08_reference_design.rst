Reference design
================

.. include:: /common.inc

``two_die_interposer`` is the worked example of the whole flow: two dies mounted
face down on an IntM4TM2 interposer, attached by two *different* interconnect
methods, with wire-bond I/O pads at the interposer edge. It ships in the
|tools-repo| repository under ``examples/two_die_interposer/`` and is baked into
the ADK-Tools image at ``/opt/adk-tools/examples/two_die_interposer``. On first
container start a disposable copy is seeded at ``/work/example``.

It is also the template ``adk-new-project`` scaffolds, so its directory layout
is the recommended one for your own designs.

.. tip::
    Work on the seeded copy under ``/work/example``, not on
    ``/opt/adk-tools/examples``. The seeded copy is disposable: delete
    ``~/adk-work/example`` on the host and the next container start reseeds it
    from the image.

What the demo assembles
-----------------------

.. list-table::
    :header-rows: 1
    :widths: 18 18 64

    * - Component
      - Technology
      - Description
    * - ``interposer``
      - ``intm4tm2``
      - 6492.312 x 5602.001 um, 300 um thick. Four routed metals, Cu-pillar
        landing pads under each die, 35 wire-bond I/O pads of 100 x 100 um on
        ``TopMetal2`` around the edge.
    * - ``U1``
      - ``sg13g2``
      - 770 x 2606.339 um, 750 um thick, ``orientation: flip_chip``, attached
        with ``cupillar_opt1`` (44 um body, 75 um pitch, 40 um spacing).
    * - ``U2``
      - ``sg13g2``
      - The same die layout, attached with ``vendorx_microbump`` (40 um body,
        50 um pitch, 15 um spacing). A demo, non-IHP method.

Both dies are instances of the same ``Metal_Test`` layout, an SG13G2 test die
whose 58 external I/O pads sit on ``TopMetal2`` (134/0) with their names on the
text layer 134/25.

The two connection stacks are what make the demo interesting, because they are
what forces every per-method mechanism in the flow to actually do something. The
die z values follow from them directly. The interposer's attachment surface is
at 13.83 um; ``cupillar_opt1`` is a 28 um Cu pillar plus a 16 um SnAg cap, so
``U1`` sits at 57.83 um; ``vendorx_microbump`` is 18 um plus 6 um, so ``U2``
sits at 37.83 um. That arithmetic is not decoration: the 3Dblox exporter
verifies it exactly and refuses assemblies that do not satisfy it.

Directory tree
--------------

.. code-block:: text

    two_die_interposer/
      README.md
      chiplets/                              gds2kicad prior-step inputs
        README.md
        Metal_Test.gds                       the full die layout, shared by U1 and U2
        Metal_Test_stripped.gds              curated: only the 58 I/O pads, with names
        metal_test_chiplet.pins.json         58-pad pin list with reviewed side/type
        metal_test_chiplet.g2kproj           saved gds-to-kicad GUI session
      kicad/                                 the human-authored source
        two_die_interposer.kicad_pro
        two_die_interposer.kicad_sch
        two_die_interposer.kicad_pcb
        two_die_interposer.kicad_sym         project symbols, produced by gds2kicad
        two_die_interposer.pretty/
          metal_test_chiplet.kicad_mod       die footprint, produced by gds2kicad
          interposer_bondpad.kicad_mod       wire-bond I/O pad footprint, parametric
        sym-lib-table
        fp-lib-table
      outputs/                               everything the export writes
        two_die_interposer.chiplet           open this in Chiplet Studio
        MANIFEST.md                          index of the products
        layout/
          two_die_interposer_interposer.gds
          two_die_interposer_interposer.boundaries.json
          two_die_interposer_interposer.pillars.json
          two_die_interposer_complete.boundaries.json
          two_die_interposer_complete.pillars.json
          two_die_interposer_complete.ixn_methods.json
        reports/
          two_die_interposer_assembly_drc.lyrdb
          two_die_interposer_cupillar_drc.json

Four more paths appear once you regenerate, and are deliberately not tracked:
``outputs/two_die_interposer.hyp``, ``outputs/layout/two_die_interposer_complete.gds``,
``outputs/reports/assembly_drc/`` (the DRC scratch directory) and
``outputs/logs/``. Everything else is committed on purpose, so a fresh clone
opens in Chiplet Studio and carries its DRC results without a rebuild.

.. note::
    To open ``two_die_interposer_complete.gds`` in KLayout, or run the assembly
    DRC yourself, regenerate the outputs first. The ``*_complete.*.json``
    sidecars *are* shipped, so the boundary and pillar manifests can be read
    straight from a clone.

What each file is
-----------------

``chiplets/``
~~~~~~~~~~~~~

``Metal_Test.gds`` is the canonical die layout. Both the footprint and the
``.chiplet`` reference it board-relative as ``../chiplets/Metal_Test.gds``, so
the export and Chiplet Studio read the die geometry from the example itself and
not from any external tool tree.

``Metal_Test_stripped.gds`` is the frozen result of the pad review described in
:doc:`/flow/02_die_to_kicad`: 58 external I/O pads out of about 474 shapes on
``TopMetal2``. Shipping the curated version makes the footprint a reproducible
conversion rather than the one hand-made artefact in the project.

``metal_test_chiplet.pins.json`` carries each pad's name and geometry *plus* the
reviewed symbol-layout fields ``side`` and ``type``, which cannot be re-extracted
from a footprint. That is why the file exists rather than being derived.

``metal_test_chiplet.g2kproj`` is a saved gds-to-kicad session bundling the
inputs, the layer selections and the embedded pin list. It stores
image-absolute paths, so it is meant for use inside the container.

``kicad/``
~~~~~~~~~~

The board and its project libraries. The symbol library and the ``.pretty``
footprint library are *outputs* of the prior steps below, committed so the board
opens without running them, and registered with the project through
``sym-lib-table`` and ``fp-lib-table``.

``outputs/``
~~~~~~~~~~~~

``two_die_interposer.chiplet`` is the assembly description and the entry point
for Chiplet Studio. It declares both technologies, all five connection stacks,
the interposer with its 35 I/O pads, and the two dies with their placement,
orientation, thickness and connection method.

Under ``layout/``, the interposer GDS is the one the ``.chiplet`` references.
Each GDS has its own boundary manifest and pillar manifest as siblings, which is
how the assembly DRC and the viewer macro find them without being told.
``two_die_interposer_complete.ixn_methods.json`` maps each interconnect method to
the dies that use it, so the DRC checks ``U1``'s pads at 75/40 and ``U2``'s at
50/15 instead of applying one number to the whole assembly.

Under ``reports/``, the ``.lyrdb`` is the assembly DRC result database, openable
in the KLayout Marker Browser, and the ``_cupillar_drc.json`` is the Cu-pillar
DRC summary the producer wrote while generating the pillars.

Walking the flow
----------------

Step 0: open what is already there
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From the host, using the launcher in the ADK-Tools checkout:

.. code-block:: bash

    ./run.sh chiplet-studio example/outputs/two_die_interposer.chiplet
    ./run.sh kicad          example/kicad/two_die_interposer.kicad_pro

Or from a shell inside the container, where both tools are on the path. Expect
Chiplet Studio to show the interposer slab with two dies standing off it on
their pillars, and the wire-bond pads with their fan-out traces around the edge;
switch a
die to a detailed render mode to see its actual artwork as geometry. See
:doc:`/flow/07_view_and_inspect`.

Step 1: the gds2kicad prior steps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These run once per die, before any board work, and produce the KiCad library the
board is built on. They are reproducible from the shipped inputs, and the image
build gates them against the committed library.

The die footprint, read straight out of the curated GDS:

.. code-block:: bash

    gds_to_kicad.py Metal_Test_stripped.gds \
        --layer TopMetal2.drawing --text-layer-number 134/25 \
        --lyp-file $GDS_TO_KICAD_ROOT/pdks/sg13g2.lyp --flip-chip \
        -o metal_test_chiplet.kicad_mod

The die symbol, from the reviewed pin list, with no GDS involved:

.. code-block:: bash

    gds_to_kicad_symbol.py --from-pin-list metal_test_chiplet.pins.json \
        -o Metal_Test.kicad_sym

The wire-bond I/O pad, generated parametrically rather than converted:

.. code-block:: bash

    $GDS_TO_KICAD_ROOT/io_pads/generate_io_pad.py --io-class wire_bond --size 100x100

The same three steps are available from the ``gds-to-kicad`` GUI, and
``metal_test_chiplet.g2kproj`` reopens the session at exactly the state that
produces the footprint and the symbol. See :doc:`/flow/02_die_to_kicad`.

.. note::
    ``--flip-chip`` on the footprint conversion is not cosmetic. The die is
    mounted face down, so its pads are mirrored in the board frame. This is the
    same mirror the assembly generator applies to the die artwork, and the same
    one the pad-to-pillar check models. Getting it wrong produces an assembly
    where every pad is on the wrong side and every individual check still passes.

Step 2: author the board
~~~~~~~~~~~~~~~~~~~~~~~~

The board is drawn in the KiCad fork, with the physical stackup naming the
copper layers after the process metals and a closed ``Edge.Cuts`` outline. That
is covered by :doc:`/flow/03_interposer_design`; the demo's ``.kicad_pcb`` is
the finished result.

Step 3: export and generate the GDS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Normally this is the Chiplet Export plugin inside pcbnew, with its output
directory pointed at the sibling ``outputs/``. The demo's headless equivalent,
which is exactly what the image build runs, is:

.. code-block:: bash

    python3 /opt/adk-tools/chiplet_kicad_plugin/tests/regenerate_wirebond_demo.py \
        --require-drc \
        --board   example/kicad/two_die_interposer.kicad_pcb \
        --output-dir example/outputs

One command drives the whole chain: the HyperLynx writer produces the ``.hyp``,
the chiplet writer produces the intermediate ``.chiplet``, ``hyp_to_gds``
produces both GDS files with their sidecars and finalises the ``.chiplet``, and
the ADK assembly DRC runs on the complete GDS. ``--require-drc`` makes a DRC
failure a non-zero exit, which is what turns this into a build gate.

The script prints the resolved artefact paths as it goes, and echoes the worker
command lines it runs, so it doubles as a way to see the exact ``hyp_to_gds``
invocation for a given board.

Step 4: the assembly DRC on its own
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The export runs the DRC for you. To run it again by hand against the
regenerated complete GDS, with the same adapters and per-method scoping the
pipeline derives from the ``.chiplet``:

.. code-block:: bash

    adk-drc \
        --path      example/outputs/layout/two_die_interposer_complete.gds \
        --interposer-adapter   intm4tm2 \
        --interconnect-adapter vendorx_microbump \
        --interconnect-methods example/outputs/layout/two_die_interposer_complete.ixn_methods.json \
        --report    example/outputs/reports/two_die_interposer_assembly_drc.lyrdb \
        --run_dir   example/outputs/reports/assembly_drc

The boundary manifest is not on the command line because the runner
auto-discovers ``two_die_interposer_complete.boundaries.json`` next to the GDS.
The runner logs a pass or fail banner and the report path; a violation leaves
items in the ``.lyrdb`` under the rule that flagged them.

Step 5: checks the demo does not run for you
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Only stage 3, the KLayout assembly DRC of step 4, is part of the demo pipeline.
The other three of the four :doc:`verification stages
</flow/06_verification_stages>` are not. Two of them you can run yourself
against the shipped artefacts, and they are given below. The third, the KiCad
design-time check, cannot be run here at all: the demo ``kicad/`` tree ships no
generated ``.kicad_dru``, so there is nothing for pcbnew to enforce. Generate
one as :doc:`/adk/06_kicad_dru` describes before using this example as the
template for a design of your own.

Pad-to-pillar alignment, which needs the ``.chiplet``, the pillar manifest and a
pad source per die:

.. code-block:: bash

    python3 $ADK_ROOT/checks/pads_vs_pillars.py \
        --chiplet example/outputs/two_die_interposer.chiplet \
        --pillars example/outputs/layout/two_die_interposer_complete.pillars.json \
        --pins U1=example/chiplets/metal_test_chiplet.pins.json \
        --pins U2=example/chiplets/metal_test_chiplet.pins.json \
        --json pads_vs_pillars.json

The 3Dblox export, whose own consistency checks run without OpenROAD installed:

.. code-block:: bash

    python3 $ADK_ROOT/openroad/chiplet2dbx.py \
        --chiplet example/outputs/two_die_interposer.chiplet \
        --out-dir build/3dblox \
        --pins U1=example/chiplets/metal_test_chiplet.pins.json \
        --pins U2=example/chiplets/metal_test_chiplet.pins.json

Running ``check_3dblox`` on the result additionally needs an OpenROAD image
carrying the 3Dblox commands. See :doc:`/flow/06_verification_stages`.

Step 6: the one-command self test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    adk-smoke

``adk-smoke`` verifies that the ``intm4tm2`` KLayout technology is registered
and its layer properties resolve, then exports the demo end to end into a
throwaway directory with ``--require-drc`` and asserts the DRC passed. It is the
fastest way to tell whether a container, or a hand-assembled toolchain, is
wired correctly. On success it ends with the line
``adk-smoke: PASS (export + assembly DRC green)``; any failure exits non-zero
before that.

What the committed reports say
------------------------------

Two result files are tracked, so you can read the demo's verification outcome
without running anything.

``reports/two_die_interposer_cupillar_drc.json`` records the producer-side
Cu-pillar checks: version 2 of the report format, the per-die method assignment
(``U1`` to ``cupillar_opt1``, ``U2`` to ``vendorx_microbump``), the parameter set
each method was checked with, and a summary of zero errors, zero warnings and
ten informational results across ten checks over two devices, with ``passed``
true.

``reports/two_die_interposer_assembly_drc.lyrdb`` records the assembly DRC. It
carries eleven rule categories and no violation items:

.. code-block:: text

    ASM.a  ASM.b  ASM.e  ASM.f
    IXN.b.cupillar_opt1        IXN.e.cupillar_opt1
    IXN.b.vendorx_microbump    IXN.e.vendorx_microbump
    IXN.x.cupillar_opt1.vendorx_microbump
    IXN.b.unclaimed            IXN.e.unclaimed

That list is the interesting part. The per-method categories show the two dies
being checked at their own numbers; ``IXN.x`` is the conservative cross-method
spacing between the two bump fields, at the larger of the two spacings; and the
``unclaimed`` categories cover any attachment pad that falls under no die's
boundary, checked with the assembly-level adapter's numbers.

Reproducibility
---------------

The demo outputs are not decorative. The image build regenerates them headless
from the board and then compares the fresh regeneration against the committed
tree, failing the build on any semantic difference: a committed deliverable a
fresh run no longer produces, a new sidecar a fresh run emits that is not
committed, or a change in the ``.chiplet``, the manifests, the reports or the
GDS geometry.

The comparison is not a naive byte diff. GDS files are hashed with the
``BGNLIB`` and ``BGNSTR`` timestamps zeroed, so a real geometry, layer or cell
change is caught while KLayout's per-run header timestamp is not. Boundary
manifests are compared with ``assembly_gds_sha256`` dropped, for the same
reason. Per-run artefacts, the logs, the DRC scratch directory, the ``.lyrdb``,
the complete GDS and the ``.hyp``, are ignored.

The gate exists because the runtime image bakes the tracked deliverables rather
than the regeneration, so a tracked set that had drifted from what the current
board and toolchain produce could ship on a green build. A stale ``.chiplet`` and
a missing pillar manifest reached a release candidate that way.

What the demo demonstrates
--------------------------

- A die layout becoming a KiCad symbol and footprint, reproducibly, from
  shipped inputs.
- An interposer authored in KiCad on process-named copper layers, exported to a
  ``.chiplet`` assembly and a HyperLynx netlist.
- Routing becoming fabrication geometry: paths on real process layers, vias from
  the base PDK's ``via_stack`` PCells, the board outline on ``prBoundary``.
- Cu-pillar generation from per-die pin lists, with **two different interconnect
  methods in one assembly**, each checked against its own rules.
- Flip-chip placement of both dies, mirrored per layer in the assembly GDS.
- Wire-bond I/O pads placed on the interposer and recorded in the ``.chiplet``.
- The manifest sidecars, and both consumers of them: the assembly DRC and the
  boundary viewer.
- A per-method assembly DRC run that passes, including cross-method spacing.
- 3D inspection of the finished assembly, with drill-down into the real layouts.

What it does not demonstrate
----------------------------

- **Two different dies.** ``U1`` and ``U2`` are two instances of the same
  layout. Nothing in the flow requires that, but the demo does not exercise a
  genuinely heterogeneous die set.
- **A stacked or multi-tier assembly.** Everything sits on one tier. The
  assembly rules assume that, and ``ASM.a`` would flag legally stacked dies as
  overlapping.
- **Automated 2.5D place and route.** That work is a proof of concept and is not
  part of this example. See :doc:`/roadmap`.
- **The interposer's or the dies' own fabrication rules.** The example runs the
  assembly checks only. The interposer PDK and the die PDK own their decks, and
  running them is a separate step.
- **Thermal, power-integrity or timing analysis.** Those ADK domains are
  reserved names with no implementation.
- **A fabricated assembly.** The interposer process has been fabricated several
  times at IHP, which is a statement about process maturity. This example is a
  design flow demonstration, and no complete assembly built from it has been
  manufactured.
- **A vendor-qualified fine-pitch method.** ``vendorx_microbump`` is a
  deliberately synthetic, non-IHP method, present so that the per-method
  machinery has two methods to distinguish. Its numbers are demonstration
  values.

Starting your own design
------------------------

.. code-block:: bash

    adk-new-project my_design

This scaffolds ``/work/heterogenic-designs/my_design`` with the same
``kicad/`` plus ``chiplets/`` plus ``outputs/`` split, and a ``.gitignore``
already keeping the heavy and scratch files out of version control while
tracking the light deliverables. Author the board under ``kicad/``, run the
Chiplet Export plugin with its output directory set to the sibling
``outputs/``, and open the result with ``chiplet-studio``.
