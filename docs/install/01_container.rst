The ADK-Tools image
===================

.. include:: /common.inc

The supported way to run the flow is the ADK-Tools container. It carries every
tool of the ecosystem, compiled against each other and pre-wired: the KiCad
fork with the chiplet export plugin preloaded, Chiplet Studio, gds2kicad, the
HyperLynx to GDS converter, the assembly DRC runner, KLayout with the
interposer technology registered, both PDKs, and the reference design. Nothing
inside needs to be installed, configured or pointed at anything.

This page takes you from a clone to a green end-to-end self test. If you cannot
use Docker, :doc:`/install/02_host` derives a host installation from the same
recipe, but it is a best-effort route.

.. note::
    There is no pre-built image to pull. The image is built locally from the
    pinned sources with ``build.sh``. What that pins, and why the build gates
    itself on a full regeneration of the reference design, is described in
    :doc:`/tools/07_adk_tools_image`.

Prerequisites
-------------

- **Docker**, with the daemon running and your user able to talk to it. The
  build uses BuildKit, which ships with current Docker releases.
- **git**, to clone the repository and its submodules.
- **Network access** to github.com and gitlab.com during the build. The build
  fetches the KiCad libraries and the SG13G2 PDK slice directly.
- **An X server** if you want the GUIs. Local X, ThinLinc and WSLg all work.
  The command-line tools do not need one.
- **Disk and time.** The build compiles KiCad and KLayout from source. Expect
  roughly an hour for the first build on a machine with the default eight
  parallel jobs, and generous free space for the Docker build cache.
- **Memory.** ``run.sh`` caps the container at 20 GiB by default, so a runaway
  tool cannot exhaust host RAM. The build itself is bounded by the job count,
  not by that cap.

Clone with submodules
---------------------

The submodules are the version lockfile. A clone without them cannot build.

.. code-block:: bash

    git clone --recurse-submodules https://github.com/IHP-GmbH/ADK-Tools.git
    cd ADK-Tools

If you already cloned without ``--recurse-submodules``:

.. code-block:: bash

    git submodule update --init --recursive

Build the image
---------------

.. code-block:: bash

    ./build.sh

That is the whole command. It produces ``adk-tools:dev``.

``build.sh`` takes an optional tag and one option:

.. code-block:: bash

    [JOBS=N] ./build.sh [TAG] [--skip-verify]

``TAG``
    Image tag, default ``dev``. The result is ``adk-tools:TAG``.

``JOBS``
    Parallel compile jobs for the heavy stages, default 8. Lower it on a small
    machine, raise it on a large one. The job count keys the heavy layers, so
    changing it invalidates their cache and forces one full recompile of KiCad
    and KLayout.

``--skip-verify``
    Skips the verify stage. For quick local iteration only. The verify stage is
    what proves the pinned combination works end to end, so an image built with
    this flag carries no such guarantee.

The build runs the ``verify`` stage before it tags anything: it runs every
tool's test suite inside the image, regenerates the reference design headless
through the full pipeline, and requires the assembly DRC on the result to pass.
A broken combination of pins therefore fails the build instead of producing a
tagged image. Subsequent builds reuse the cached stages and only rebuild what
actually changed.

.. tip::
    Set ``JOBS`` to leave headroom rather than to saturate the machine.
    ``build.sh`` deliberately sequences the KiCad build ahead of the Chiplet
    Studio build so the two heavy stages never run concurrently, because
    BuildKit would otherwise double the effective job count and exhaust RAM.

Run the image
-------------

.. code-block:: bash

    ./run.sh                              # interactive shell
    ./run.sh kicad example/kicad/two_die_interposer.kicad_pro
    ./run.sh chiplet-studio example/outputs/two_die_interposer.chiplet
    ./run.sh adk-smoke                    # end-to-end self test

``run.sh`` wires up everything a bare ``docker run`` would leave to you:

- Mounts the host work directory at ``/work`` and makes it the working
  directory.
- Runs the container as your own user and group, with a minimal private
  ``passwd``/``group`` pair so the shell has a real user name, and sets
  ``HOME=/tmp``.
- Passes ``DISPLAY`` and the X11 socket through, plus your Xauthority file when
  one exists.
- Caps memory, with container swap disabled so the kernel kills a runaway
  process inside the container instead of thrashing host swap.
- Allocates a TTY only when there is one, so scripted and CI launches behave.
- Uses ``--rm``, so containers do not accumulate. Nothing you care about lives
  in the container: it lives in ``/work``.

Three environment variables control it:

.. list-table::
    :header-rows: 1
    :widths: 24 26 50

    * - Variable
      - Default
      - Effect
    * - ``ADK_TOOLS_IMAGE``
      - ``adk-tools:dev``
      - Image to run. Set it if you built with a different tag.
    * - ``ADK_WORK``
      - ``~/adk-work``
      - Host directory mounted at ``/work``. Created on first run.
    * - ``ADK_MEM_LIMIT``
      - ``20g``
      - Hard memory ceiling for the container and everything in it.

Graphics
--------

The GUIs need an X server. ``run.sh`` handles the wiring; what you need to know
is why the image renders in software by default.

The image forces Mesa's software path with ``LIBGL_ALWAYS_SOFTWARE=1`` and
``GALLIUM_DRIVER=llvmpipe``. The container is started without a GPU device, and
remote X servers such as ThinLinc advertise GLX while being unable to provide a
DRI3 device. KiCad's accelerated canvas then probes the hardware path and
segfaults the moment a GL canvas is built; the symbol chooser preview is the
usual trigger. The software renderer is always available and gives KiCad,
Chiplet Studio, gds2kicad and KLayout a stable context.

If you do have a GPU and want hardware acceleration, pass the device through
and opt back in:

.. code-block:: bash

    docker run --rm -it \
        --device /dev/dri \
        -e LIBGL_ALWAYS_SOFTWARE=0 \
        -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v ~/adk-work:/work -w /work \
        --user "$(id -u):$(id -g)" -e HOME=/tmp \
        --memory 20g --memory-swap 20g \
        adk-tools:dev

Without ``--user`` the container runs as root and every file it writes into
``/work`` lands on your host owned by root.

The shared folder
-----------------

``/work`` is the boundary between the container and your machine. Files written
on either side are immediately visible on the other, which is the intended way
to work: edit and run with the tools inside the container, keep the files and
their git history on the host.

Two subdirectories are seeded on start:

.. code-block:: text

    /work/example              two-die interposer reference design (disposable)
    /work/heterogenic-designs  your persistent designs (survives image rebuilds)

``/work/example`` is a copy of the design bundled in the image, so you can open,
break and delete it freely. It is seeded when absent, and refreshed when a newer
image ships a changed design: the entrypoint compares a content hash baked at
build time against the copy on disk, and if they differ it moves the old copy
aside to ``/work/example.prev`` and re-seeds.

``/work/heterogenic-designs`` is left alone entirely. It is where your own work
belongs.

.. note::
    Seeding is skipped silently when ``/work`` is missing or not writable, which
    is what happens with a plain ``docker run`` that does not mount it.

The entrypoint also copies KiCad's global configuration templates into the
runtime ``HOME`` when they are absent, so neither the library table dialog nor
the first-run setup wizard appears. Since ``HOME=/tmp`` keeps nothing between
``--rm`` runs, this happens on every start; an existing file is never
overwritten.

Scaffold a project
------------------

.. code-block:: bash

    adk-new-project my_design

This creates ``/work/heterogenic-designs/my_design`` with the same layout as
the bundled reference design, which is what the rest of the flow expects. The
three directories are created empty, with a ``.gitkeep`` each so they survive a
commit; the annotations below say what you put in them:

.. code-block:: text

    my_design/
      kicad/       KiCad source you author (schematic, PCB, .pretty, fp-lib-table)
      chiplets/    die GDS inputs and pin lists for the gds2kicad prior steps
      outputs/     export products: <board>.chiplet and MANIFEST.md at the root,
                   the GDS layouts and DRC sidecars under outputs/layout/,
                   the DRC reports under outputs/reports/

It also writes a project ``.gitignore`` and a one-line ``README.md``. The
``.gitignore`` keeps the heavy regenerable files out of git while tracking the
light deliverables that let a fresh clone open the design in Chiplet Studio and
keep its DRC results; the tracked set is listed explicitly as comments at the
bottom of the file. A ``git init`` in the project directory is ready to use.

The base directory can be overridden with ``ADK_PROJECTS_DIR``. Project names
are restricted to a single path segment of letters, digits, dot, dash and
underscore, and an existing non-empty directory is never overwritten.

The workflow from there is, with ``/work`` as the working directory:

#. ``kicad heterogenic-designs/my_design/kicad`` and author the board.
#. Run the Chiplet Export plugin in pcbnew with its output directory set to the
   sibling ``outputs/``. See :doc:`/tools/02_chiplet_export_plugin`.
#. ``chiplet-studio heterogenic-designs/my_design/outputs/<board>.chiplet`` to
   inspect the result.

``adk-new-project`` prints the same three steps with absolute paths when it
finishes.

List the tools
--------------

Inside the container, ``adk-tools`` prints the available commands with the
pinned revision of each, the data roots, and the layout of ``/work``:

.. code-block:: bash

    adk-tools

.. list-table:: Commands
    :header-rows: 1
    :widths: 22 18 60

    * - Command
      - Kind
      - Tool
    * - ``kicad``
      - GUI
      - KiCad fork, with ``pcbnew`` and ``kicad-cli`` installed and the chiplet
        export plugin preloaded
    * - ``chiplet-studio``
      - GUI
      - 3D assembly viewer and ``.chiplet`` editor
    * - ``gds-to-kicad``
      - GUI
      - GDS to KiCad symbol and footprint generator, unified window
    * - ``hyp-to-gds``
      - CLI
      - HyperLynx to GDS converter
    * - ``adk-drc``
      - CLI
      - ADK assembly DRC runner
    * - ``klayout``
      - GUI/CLI
      - KLayout, at the revision pinned by the Chiplet Studio submodule
    * - ``adk-smoke``
      - CLI
      - End-to-end self test
    * - ``adk-new-project``
      - CLI
      - Scaffold a new design

The version numbers come from the manifest baked into the image at build time.
Quote that block when reporting a problem: it identifies the exact combination of
revisions you are running.

Two text editors are bundled for in-container edits of files under ``/work``:
``vim`` in the terminal, and ``featherpad``, a light Qt GUI editor that needs X
like the other GUIs.

The interposer KLayout technology is pre-registered, so exported interposer and
assembly GDS files open with named, coloured layers:

.. code-block:: bash

    klayout -n intm4tm2 outputs/layout/<board>_interposer.gds

You can also pick ``intm4tm2`` in KLayout's technology selector.

Run the self test
-----------------

.. code-block:: bash

    adk-smoke

``adk-smoke`` verifies a running image in one command, and it is the same check
the build uses as its last gate. It:

#. Confirms the ``intm4tm2`` technology is registered in KLayout and that its
   layer properties file resolves.
#. Exports the two-die interposer reference design headless through the full
   pipeline: ``pcbnew``, the HyperLynx writer, the ``hyp_to_gds`` worker, then
   the ADK assembly DRC.
#. Fails unless the assembly DRC passes.

Everything is written to a temporary directory that is removed on exit, so the
test leaves nothing behind. A green run prints ``adk-smoke: PASS (export +
assembly DRC green)``.

If it fails, the failing stage names itself. A failure in the first step points
at KLayout's search path; later failures are the pipeline itself, and since the
reference design is a known good input the fault is in the image or the
environment rather than in a design.

Where to go next
----------------

- :doc:`/flow/01_overview` for what the pipeline actually does.
- :doc:`/flow/08_reference_design` for a walk through the bundled two-die
  design.
- :doc:`/install/03_environment` if you need to point a tool at a checkout of
  your own.
- :doc:`/tools/07_adk_tools_image` for the pin, build and release model.
