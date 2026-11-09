Building and running the image
==============================

.. include:: /common.inc

.. warning::
    packaging-flow, interposer-pnr, assembly-lvs, chiplet-die-flow,
    chiplet-cosim and the worked examples (adk-examples) are not public
    yet. The image build stages the first five and reads die records from
    the examples, so a public reader cannot build the full image until
    they are.

The supported way to run the flow is the ADK-Tools container. It carries every
tool of the ecosystem, compiled against each other and pre-wired: the KiCad
fork with the chiplet export plugin preloaded, Chiplet Studio, gds2kicad, the
HyperLynx to GDS converter, the assembly DRC runner, KLayout with the
interposer technology registered, the interposer and interconnect PDKs, a
KLayout slice of the SG13G2 PDK, and the flow's engines with the OpenROAD,
LibreLane and simulation tools they drive. Nothing inside needs to be
installed, configured or pointed at anything.

This page takes you from a clone to a green end-to-end self test. If you cannot
use Docker, :doc:`/install/02_host` derives a host installation from the same
recipe, but it is a best-effort route.

.. note:: No image is published, to a registry or otherwise: you build the
    image you run, locally, from the pinned sources with ``build.sh``. What
    that pins, and why the build gates itself on a full regeneration of a
    reference design, is described in :doc:`/tools/07_adk_tools_image`. To run
    the examples of the preview release, :doc:`/install/00_release` gives the
    order.

Prerequisites
-------------

- **Docker**, with the daemon running and your user able to talk to it. The
  build uses BuildKit, which ships with current Docker releases.
- **Nix** on the host. ``build.sh`` copies OpenROAD, LibreLane and its
  interpreter, the SG13G2 PDK and the simulation engines and viewers from the
  host's Nix store into the image's own store, and refuses to build unless
  each one is there. Running an image built this way needs no Nix.
- **git** and **python3**, for the clone and the build scripts.
- **The staged sources.** A checkout of each sibling repository that
  ``staging.pin`` lists, at the commit it pins, beside the clone or in the
  directory ``STAGE_SIBLINGS`` names, and the die records the image carries:
  the ``die-views/`` folder of an adk-examples checkout at the same release
  tag.
- **Network access** to github.com, gitlab.com and the Ubuntu snapshot archive
  during the build. The build fetches the KiCad libraries, the PDK slices and
  the pinned Ubuntu packages directly.
- **An X server** if you want the GUIs. Local X, ThinLinc and WSLg all work.
  The command-line tools do not need one.
- **Disk and time.** The build compiles KiCad and KLayout from source. Expect
  roughly an hour for the first build on a machine with the default eight
  parallel jobs, and generous free space for the image, the Docker build cache
  and the Nix store.
- **Memory.** ``run.sh`` caps the container at 8 GiB and 4 CPUs by default, so
  a runaway tool cannot exhaust the host. The build itself is bounded by the
  job count, not by that cap.

Build the image
---------------

The ADK-Tools README, section Build, gives the sequence, up to reading the ID
of the image you built:

.. literalinclude:: /install/_recipe/build.sh
    :language: bash

The submodules under ``tools/`` are part of the version lockfile, so a clone
without ``--recurse-submodules`` cannot build; ``git submodule update --init
--recursive`` repairs one. The two ``--check`` calls write nothing and name a
missing sibling checkout or die record in seconds. ``nix build`` realises the
pinned Nix packages in the host's store; run it once at the commit you build and
keep the ``result`` links it leaves, which protect those paths from garbage
collection. Most come from the binary cache; the Verilog-AMS shell, Xschem and
the mixed-signal Icarus build locally.

``build.sh`` takes an optional tag, two environment variables and two options:

.. code-block:: text

    [JOBS=N] [VERIFY_TAG=T] ./build.sh [TAG] [--skip-verify] [--tools-only]

``TAG``
    Image tag, default ``dev``. The result is ``adk-tools:TAG``.

``JOBS``
    Parallel compile jobs for the heavy stages, default 8. Lower it on a small
    machine, raise it on a large one. The job count keys the heavy layers, so
    changing it invalidates their cache and forces one full recompile of KiCad
    and KLayout.

``VERIFY_TAG``
    Tag of the verify-stage image the build leaves beside the runtime image,
    default ``verify``, so the result is ``adk-tools:VERIFY_TAG``. Each build
    moves that tag onto its own verify image; pass another name to keep the
    previous one. It has to be a valid Docker tag and differ from ``TAG``.

``--skip-verify``
    Skips the verify stage. For quick local iteration only. The verify stage is
    what proves the pinned combination works end to end, so an image built with
    this flag carries no such guarantee.

``--tools-only``
    Builds only the tools image, the part of the ``Dockerfile`` above its
    thin-layer line, for this tree's key, and stops. This is for maintainers
    whose change moved that key: the two lock files under ``docker/`` are read
    from that image.

The build runs the ``verify`` stage before it tags anything: it runs every
tool's test suite inside the image, regenerates the two-die reference design
headless through the full pipeline, and requires the assembly DRC on the
result to pass. A broken combination of pins therefore fails the build instead
of producing a tagged image. Subsequent builds reuse the cached stages and only
rebuild what actually changed.

``build.sh`` refuses before Docker starts when the sources would not match the
labels it writes: ``ci/pin-set.json`` must be tracked, unmodified and equal to
what the pins regenerate, and the interposer PDK submodule
``tools/OpenIntM4TM2`` must be checked out at its committed gitlink with no
tracked file changed, because the image's copy of that PDK reports the gitlink
commit as its version.
``--tools-only`` skips the second check.

.. tip::
    Set ``JOBS`` to leave headroom rather than to saturate the machine. The
    tools image, which holds the KiCad compile, is built before the stage that
    compiles KLayout and Chiplet Studio, so the two heavy compiles never run
    concurrently; BuildKit would otherwise double the effective job count and
    exhaust RAM.

Run the image
-------------

With ``ADK_TOOLS_IMAGE`` set to the ID of your build:

.. code-block:: bash

    "$ADK_TOOLS_ROOT/run.sh"                    # interactive shell
    "$ADK_TOOLS_ROOT/run.sh" --examples "$ADK_EXAMPLES_ROOT"
    "$ADK_TOOLS_ROOT/run.sh" bash < script.sh   # a script piped in, no terminal

Call ``run.sh`` by its path from wherever you work, and leave the clone at the
version of the image you run. ``run.sh`` wires up everything a bare
``docker run`` would leave to you:

- Mounts the host work directory at ``/work`` and makes it the working
  directory. It refuses to start when that directory holds the clone, which
  the container could then write, or lies inside it, where a ``git clean`` in
  the clone would delete your runs.
- Runs the container as your own user and group, with a minimal private
  ``passwd``/``group`` pair so the shell has a real user name, and sets
  ``HOME=/tmp``.
- Picks a display (``ADK_DISPLAY``, else a local ``DISPLAY``, else your newest
  ThinLinc session) and passes its X socket and cookie through.
- Caps memory and CPUs, with container swap disabled so the kernel kills a
  runaway process inside the container instead of thrashing host swap.
- Allocates a TTY only when there is one, so scripted and CI launches behave.
- Uses ``--rm``, so containers do not accumulate. Nothing you care about lives
  in the container: it lives in ``/work``.
- With ``--examples DIR``, mounts that adk-examples checkout read-only at
  ``/examples`` and holds the image to its ``release-lock.json``, as
  :doc:`/install/00_release` describes. ``--lock FILE`` names another lock.

Before the container starts, ``run.sh`` prints one ``run.sh:`` line on stderr
for each choice it made: the work directory, the image, the display, the caps,
the OpenROAD the image carries and, with a lock, the lock it held the image
to. ``--dry-run`` makes every check and prints the ``docker`` command instead
of running it. The clone's ``docs/RUN_SH.md`` states what a launcher calling
``run.sh`` can rely on: its notes, refusals and exit codes.

These environment variables control it:

.. list-table::
    :header-rows: 1
    :widths: 24 26 50

    * - Variable
      - Default
      - Effect
    * - ``ADK_TOOLS_IMAGE``
      - none, required
      - ID of the image to run, ``sha256:<64 hex>``. A tag is refused.
    * - ``ADK_WORK``
      - ``~/adk-work``
      - Host directory mounted at ``/work``. Created on first run; a relative
        path is taken from the current directory.
    * - ``ADK_MEM_LIMIT``
      - ``8g``
      - Hard memory ceiling for the container and everything in it. Do not set
        it below ``2g``: at ``1g``, ``packaging-flow edit`` is killed for lack
        of memory (exit -9). A container the cap kills exits 137, and
        ``run.sh`` says so.
    * - ``ADK_CPUS``
      - ``4``
      - CPU cap for the container.
    * - ``ADK_DISPLAY``
      - ``DISPLAY``, else ThinLinc
      - X display as ``:N``, or ``none`` for no display.
    * - ``ADK_NETWORK``
      - Docker's default network
      - ``none`` runs the container with no network; any other value is
        refused.

Without an ID, or with a tag, ``run.sh`` refuses before it does anything else.
``ADK_TOOLS_IMAGE=adk-tools:dev ./run.sh`` prints:

.. code-block:: text

    error: ADK_TOOLS_IMAGE must be an image ID, sha256:<64 hex> (got 'adk-tools:dev')
           A tag is not taken: the daemon is shared and a tag can be moved.
           For an image you built, read its ID right after ./build.sh:
             docker image inspect --format '{{.Id}}' adk-tools:dev

``run.sh`` never fetches an image. An ID the daemon does not hold is refused
with the advice to build the image and pass its ID.

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
        --memory 8g --memory-swap 8g --cpus 4 \
        "$ADK_TOOLS_IMAGE"

Without ``--user`` the container runs as root and every file it writes into
``/work`` lands on your host owned by root.

The shared folder
-----------------

``/work`` is the boundary between the container and your machine. Files written
on either side are immediately visible on the other, which is the intended way
to work: edit and run with the tools inside the container, keep the files and
their git history on the host.

The image writes nothing into ``/work`` unless you ask. Two kinds of
subdirectory are the usual layout:

.. code-block:: text

    /work/<example>            an example copied in from /examples, as its page says
    /work/heterogenic-designs  your persistent designs (survives image rebuilds)

The runtime image carries neither the examples nor the reference design. The
worked examples come from an adk-examples checkout that ``run.sh --examples``
mounts at ``/examples``, and each example's first block copies it into
``/work``. Inside the container, ``adk-example`` prints the ``run.sh`` line
that starts it that way. ``/work/heterogenic-designs`` is made by
``adk-new-project`` the first time you use it.

The entrypoint copies KiCad's global configuration templates into the runtime
``HOME`` when they are absent, so neither the library table dialog nor the
first-run setup wizard appears. Since ``HOME=/tmp`` keeps nothing between
``--rm`` runs, this happens on every start; an existing file is never
overwritten.

Scaffold a project
------------------

.. code-block:: bash

    adk-new-project my_design

This creates ``/work/heterogenic-designs/my_design`` with the same layout as
the reference design in the clone's ``examples/two_die_interposer``, which
is what the rest of the flow expects. The three directories are created empty,
with a ``.gitkeep`` each so they survive a commit; the annotations below say
what you put in them:

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

The commands it lists include these:

.. list-table:: Commands
    :header-rows: 1
    :widths: 26 14 60

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
    * - ``chiplet-export``
      - CLI
      - Headless export of a board to ``.chiplet``, ``.hyp``, GDS and DRC
    * - ``adk-drc``
      - CLI
      - ADK assembly DRC runner
    * - ``klayout``
      - GUI/CLI
      - KLayout, at the revision pinned by the Chiplet Studio submodule
    * - ``packaging-flow``
      - CLI
      - The flow's orchestrator: dies, then the interposer, then assembly LVS
    * - ``interposer-pnr``
      - CLI
      - Placement and routing of the interposer, a proof of concept
    * - ``chiplet-die-flow``
      - CLI
      - One LibreLane die build, to a ready die
    * - ``assembly-lvs``
      - CLI
      - Assembly-stage LVS
    * - ``chiplet-system-description``
      - CLI
      - System description over a source ``system.chiplet``
    * - ``adk-smoke``
      - CLI
      - End-to-end self test
    * - ``adk-new-project``
      - CLI
      - Scaffold a new design
    * - ``adk-example``
      - CLI
      - Says how to start the image with the examples, which it does not carry

The version numbers come from the manifest baked into the image at build time.
Quote that block when reporting a problem: it identifies the exact combination
of revisions you are running.

Scripts the pages run with ``python3``, such as the ADK checks, the gds2kicad
converters and the PDK DRC runner, import ``klayout``, ``yaml`` or ``jinja2``.
Only the image's venv carries them, so inside the container run those scripts
with ``/opt/adk-tools/venv/bin/python3``; the system ``python3`` on the path stops with
``ModuleNotFoundError``.

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

``adk-smoke`` takes one board and has no default, because the runtime image
carries no copy of the reference design. The board it is written for is the
reference design in the clone's ``examples/two_die_interposer``. Copy it into
the work directory once, on the host, then run the test:

.. code-block:: bash

    mkdir -p ~/adk-work
    cp -r "$ADK_TOOLS_ROOT/examples/two_die_interposer" ~/adk-work/example
    "$ADK_TOOLS_ROOT/run.sh" adk-smoke /work/example/kicad/two_die_interposer.kicad_pcb

``adk-smoke`` verifies a running image in one command, and it is the same check
the build runs in its verify stage. It:

#. Confirms the ``intm4tm2`` technology is registered in KLayout and that its
   layer properties file resolves.
#. Exports the board headless through the full pipeline: ``pcbnew``, the
   HyperLynx writer, the ``hyp_to_gds`` worker, then the ADK assembly DRC.
#. Fails unless the assembly DRC passes.

Everything is written to a temporary directory that is removed on exit, so the
test leaves nothing behind and does not touch the copied design. A green run
prints ``adk-smoke: PASS (export + assembly DRC green)``. Without a board it
exits 2 and says where to copy the design from; a path that is not a file
exits 1.

If it fails, the failing stage names itself. A failure in the first step points
at KLayout's search path; later failures are the pipeline itself, and since the
reference design is a known good input the fault is in the image or the
environment rather than in a design.

Calling the flow from the host
------------------------------

Two launchers in the clone's ``bin/`` start the image for you. They are host
programs and are not in the image.

``bin/flow`` runs one ``packaging-flow`` or ``chiplet-system-description``
call in a container of its own, and refuses any other program:

.. code-block:: text

    bin/flow [--dry-run] [--lock FILE] [--image ID] -- <program> <args ...>

- Run it from a directory inside ``ADK_WORK``: the container starts in the
  same place below ``/work``, so relative paths in the arguments mean the same
  file inside as outside. A current directory outside ``ADK_WORK`` is refused.
- The release lock is ``--lock``, else ``ADK_FLOW_LOCK``, else a
  ``release-lock.json`` in the current directory, which is where the examples
  put it. Without one, ``bin/flow`` refuses.
- The image is ``--image``, else ``ADK_TOOLS_IMAGE``, else the reference image
  the lock names (or its ``image_manifest`` when only that one is on the
  daemon). Any image runs held to the lock's pin set, as with ``run.sh``.
- Each call is capped at 2 CPUs and 5 GiB unless ``ADK_CPUS`` and
  ``ADK_MEM_LIMIT`` are set, lower than ``run.sh``'s own 4 and 8 GiB, which is
  how the examples' shell runs are capped. LibreLane takes its thread count
  from the CPUs it sees. Export both before you start a larger design.
- The call has no stdin, no terminal and no display, except that
  ``packaging-flow verify-open`` gets the display and ``verify-sign`` and
  ``verify-accept`` get the terminal when you are at one.
- The exit code is the container's, or 1 for a refusal.

``bin/adk-vscode`` opens a folder under ``ADK_WORK`` in VS Code with the
settings the flow's tasks read:

.. code-block:: text

    bin/adk-vscode [--lock FILE] [--image ID] [--vsix PATH] <folder>

It writes four keys into ``<folder>/.vscode/settings.json`` and keeps every
other key: ``adkTools.root`` (the clone), ``adkTools.work`` (``ADK_WORK``),
``adkTools.image`` (the image the tasks run: ``--image``, else
``ADK_TOOLS_IMAGE``, else the lock's reference image) and ``adkTools.lock``.
The image has to carry the lock's pin set, as with ``run.sh``. A folder with
no ``.vscode/tasks.json`` gets the flow's tasks first: ``adk-vscode`` runs
``packaging-flow tasks --vscode`` through ``bin/flow`` and puts the result in
place only when it is whole. A ``tasks.json`` already there is kept as it is,
and a link to nothing is refused. ``--vsix`` installs an editor extension
first, and only when a ``SHA256SUMS`` beside it lists that file with a
matching sha256. Every check runs before anything is installed, written or
opened; the exit code is 0, or 1 for a refusal.

Each task VS Code runs is a ``bin/flow`` call with ``ADK_WORK``,
``ADK_TOOLS_IMAGE`` and ``ADK_FLOW_LOCK`` taken from those settings. A folder
opened without ``adk-vscode`` leaves them empty, and ``bin/flow`` refuses an
empty one by name. The examples' ``AUTOMATION.md`` pages walk through this
route.

Where to go next
----------------

- :doc:`/install/00_release` and :doc:`/examples` to run the worked examples.
- :doc:`/flow/01_overview` for what the pipeline actually does.
- :doc:`/flow/08_reference_design` for a walk through the reference design.
- :doc:`/install/03_environment` if you need to point a tool at a checkout of
  your own.
- :doc:`/tools/07_adk_tools_image` for the pin, build and release model.
