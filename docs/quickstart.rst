Quickstart
==========

.. include:: /common.inc
.. include:: /install/_release_tag.inc

.. warning::
    packaging-flow, interposer-pnr, assembly-lvs, chiplet-die-flow,
    chiplet-cosim and the worked examples (adk-examples) are not public
    yet. The image build stages the first five and reads die records from
    the examples, so a public reader cannot build the full image until
    they are.

The shortest path from nothing to a checked assembly, in four steps. The first
builds the image and takes about an hour.

You need Linux with Docker (a running daemon), Nix and git, network access to
github.com, gitlab.com and the Ubuntu snapshot archive during the build, and an
X server only for the graphical tools. The build also needs the sibling
sources ADK-Tools stages and the die records in an adk-examples checkout. :doc:`/install/01_container` states the
prerequisites in full.

1. Build the image
------------------

.. literalinclude:: /install/_recipe/build.sh
    :language: bash

|release-tag| is the release tag. The submodules are part of the version
lockfile, so a clone without them cannot build. ``build.sh`` compiles KiCad
and KLayout from source, which is where the hour goes, and refuses to tag the
image unless a two-die reference design regenerates end to end and its
assembly DRC passes.

2. Check the image
------------------

``adk-smoke`` needs a board, and the runtime image carries none. Copy the
reference design from the clone into your work directory once, then run the
test:

.. code-block:: bash

    mkdir -p ~/adk-work
    cp -r "$ADK_TOOLS_ROOT/examples/two_die_interposer" ~/adk-work/example
    "$ADK_TOOLS_ROOT/run.sh" adk-smoke /work/example/kicad/two_die_interposer.kicad_pcb

``run.sh`` mounts ``~/adk-work`` on the host as ``/work`` inside the
container. ``adk-smoke`` exports the board headless through the whole pipeline
and fails unless the assembly DRC passes. A green run prints
``adk-smoke: PASS (export + assembly DRC green)`` and leaves nothing behind.
That single line is the evidence that the toolchain works on your machine.

3. Look at the assembly
-----------------------

.. code-block:: bash

    "$ADK_TOOLS_ROOT/run.sh" chiplet-studio example/outputs/two_die_interposer.chiplet

The container starts in ``/work``, so ``example/`` is the copy you made. It is
yours: open, break and delete it freely, and copy it again from the clone when
you want it back.

The same design opens in the board tool with
``"$ADK_TOOLS_ROOT/run.sh" kicad example/kicad/two_die_interposer.kicad_pro``.

4. Start your own design
------------------------

.. code-block:: bash

    "$ADK_TOOLS_ROOT/run.sh" adk-new-project my_design

This scaffolds ``/work/heterogenic-designs/my_design`` with the reference
design's directory layout, which is what the rest of the flow expects, and
prints the next three steps with absolute paths.

The scaffold is the board-first layout: a KiCad project, the dies' folders and
an outputs folder. A design that starts from a system file instead, with no
board yet, continues with :doc:`/from_scratch`, which writes that file from
an empty folder and runs it to the verdict.

Where to go next
----------------

- :doc:`/install/00_release`, then :doc:`/examples`, to run the worked
  examples of the release in the image you just built.
- :doc:`/flow/01_overview` for what the pipeline you just ran actually does.
- :doc:`/flow/08_reference_design` for a walk through the reference design,
  file by file.
- :doc:`/intro/01_what_is_the_adk` if you want the problem before the tooling.
- :doc:`/install/01_container` for build options, graphics, the shared folder
  and the bundled commands.
- :doc:`/install/02_host` if you cannot use Docker. It is a best-effort route.
