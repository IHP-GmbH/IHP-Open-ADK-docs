The ADK-Tools image
===================

.. include:: /common.inc

.. warning::
    packaging-flow, interposer-pnr, assembly-lvs, chiplet-die-flow,
    chiplet-cosim and the worked examples (adk-examples) are not public
    yet. The image build stages the first five and reads die records from
    the examples, so a public reader cannot build the full image until
    they are.

ADK-Tools is the distribution channel of the ecosystem: one Docker image that
carries every tool of the heterogeneous integration flow, compiled and
pre-wired, callable by name. It is not a codebase. It is a version lockfile
plus a build recipe, and the image built from one of its commits *is* that
locked combination.

The repository is |tools-repo|. If you are looking for the getting-started
instructions rather than the design of the image, read
:doc:`/install/01_container`.

.. note::
    ADK-Tools is a |current-status|. The pages under :doc:`/tools` describe
    the individual repositories; this page describes how they are pinned,
    built and shipped together.

The pins
--------

The image's versions are pinned three ways: the submodules under ``tools/``,
the staged sources and engines in ``staging.pin``, and the Nix inputs in
``flake.lock``.

The submodules
~~~~~~~~~~~~~~

The tools that have a public repository are registered here as git submodules
under ``tools/``:

.. code-block:: text

    tools/kicad                       KiCad-ADK-MOD (the KiCad fork)
    tools/chiplet-studio              chiplet-studio (+ its own KLayout submodule)
    tools/chiplet_kicad_plugin        Chiplets-KiCad-Plugin
    tools/gds_to_kicad                gds2kicad
    tools/adk                         IHP-Open-ADK
    tools/OpenIntM4TM2                interposer PDK
    tools/IHP-Interconnect-IntM4TM2   interconnect PDK

The submodule directory names are names the discovery walk described in
:doc:`/install/03_environment` accepts, and the runtime image lays the same
names out as siblings under ``/opt/adk-tools``, so each tool finds the others
without configuration. The canonical repository names live in the
``.gitmodules`` URLs, which point at the upstream IHP repositories. One commit of
ADK-Tools therefore names one exact revision of each of these seven, and
``git clone --recurse-submodules`` at that commit fetches them.

Staged sources and Nix packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The flow's engines are not submodules. ``staging.pin`` names each one by
commit, and ``stage-sources.sh`` clones it from a sibling checkout into
``staging/`` at exactly that commit, so nothing uncommitted can ride along:

.. code-block:: text

    staging/assembly-lvs      assembly-stage LVS
    staging/interposer-pnr    interposer placement and routing
    staging/packaging-flow    the flow's orchestrator
    staging/chiplet-flow      die builds (chiplet-die-flow)
    staging/chiplet-cosim     co-simulation
    staging/chiplet-spec      the .chiplet specification and its reader

The image installs them into its Python environment and carries each one as a
git checkout at its pinned commit under ``/opt/adk-tools/staging/<tree>``.

``staging.pin`` also names the Nix store paths of OpenROAD, LibreLane and its
interpreter, the SG13G2 PDK, the co-simulation, mixed-signal and Verilog-AMS
engines and the waveform viewers. They come from the flake that
``flake.lock`` pins, are realised in the build host's store, and are copied
into the image's own ``/nix/store``; the image needs no Nix to run them.
Last, it pins the die views: ``die-views.sha256`` lists every file of the die
records the image carries under ``/opt/adk-tools/die-views``, and
``staging.pin`` holds the sha256 of that listing. The records come from the
``die-views/`` folder of an adk-examples checkout at the same release.

``ci/pin-set.json`` records every pinned commit in one file. ``build.sh``
writes its sha256 on the image as the ``org.ihp.adk-tools.pin-set`` label,
and that label is what a release lock holds an image to
(:doc:`/install/00_release`).

Build arguments
~~~~~~~~~~~~~~~

The remaining reproducibility-relevant pins live as build arguments in the
``Dockerfile`` and are bumped deliberately, in their own commits:

.. list-table:: Non-submodule pins in the Dockerfile
    :header-rows: 1
    :widths: 26 74

    * - Build argument
      - What it pins
    * - ``UBUNTU_IMAGE``
      - The ``ubuntu:24.04`` base image, by digest.
    * - ``APT_SNAPSHOT``
      - The time of the Ubuntu archive snapshot every apt step installs from,
        so a rebuild on another day installs the same package versions. The
        image records what it installed in ``/opt/adk-tools/tools/apt.lock``.
    * - ``KICAD_LIBS_TAG``
      - Release tag of the official KiCad symbol and footprint libraries
        (currently ``9.0.9.1``). The fork reports itself as 9.99, the v10
        development line, but predates the ``.kicad_symdir`` format, so the v9
        libraries are the compatible set. 3D model packages are deliberately
        not shipped.
    * - ``SG13G2_REF``
      - IHP-Open-PDK commit the SG13G2 KLayout slice is cut from. The slice
        also carries ``sg13cmos5l.lyp``, the ihp-sg13cmos5l layer sheet that
        packaging-flow's technology table names, and ``sg13cmos5l.lyt`` beside
        it. They are the only ihp-sg13cmos5l files in the image, which carries
        no ihp-sg13cmos5l PDK.
    * - ``PYCELL_API_REF``, ``PYPREPROCESSOR_REF``
      - The two IHP-Open-PDK submodules that the PCell library needs, cloned at
        their gitlink pins.
    * - ``GF180MCU_REF``
      - Commit of the GF180MCU PDK that the image's gf180mcuD layer sheet,
        rule decks and ngspice model files come from, each held to a sha256.
        No GF180MCU cell library is carried.
    * - ``KLAYOUT_PIP``, ``PYYAML_PIP``, ``PYQT6_PIP``, ``JINJA2_PIP``,
        ``JSONSCHEMA_PIP``, ``PSUTIL_PIP``, ``PYTEST_PIP``, ``PLUGGY_PIP``,
        ``PYTEST_XDIST_PIP``, ``Z3_SOLVER_PIP``, ``RICH_PIP``
      - Exact versions of the worker venv's direct dependencies.
        ``z3-solver`` is assembly-lvs's requirement; ``rich`` lets
        packaging-flow's console draw progress and tables on stderr.

The direct Python dependencies are exact-pinned on purpose. With only
``klayout`` pinned, the behaviour-defining packages were free to drift against
live PyPI on a cache-cold rebuild, which can silently flip a verify-stage
suite. Every package they pull in is pinned too, by
``docker/venv-constraints.txt``.

.. note::
    The build still needs live network access to github.com, gitlab.com and
    the Ubuntu snapshot archive. The image is reproducible at the level of the
    tool set, not byte for byte.

Build stages
------------

The ``Dockerfile`` is a multi-stage build in two parts. Above its thin-layer
line are the tools: everything ADK-Tools does not write. ``build.sh`` keys
that part on its text and on every file and build argument it reads, tags the
result ``adk-tools:tools-<key>``, and builds it only when no image carries the
key, so a change to ADK-Tools' own code rebuilds only the part below the line.
``build.sh`` is the way to build: it also packs the Nix closures the
``Dockerfile`` copies in. ``verify`` is the default target, so that a bare
build never produces an untested image.

.. list-table:: Stages
    :header-rows: 1
    :widths: 20 80

    * - Stage
      - What it does
    * - ``deps``
      - One shared apt layer holding the union of the KiCad build
        dependencies, the Chiplet Studio and KLayout build dependencies, and
        the runtime utilities. Every stage that compiles or runs the flow
        derives from it, so there are no missing-library hunts and the cache is
        reused everywhere. The stages that only fetch libraries and PDK data
        start from the bare base image instead, because they need no
        toolchain.
    * - ``kicad-builder``
      - Compiles the KiCad fork with ``KICAD_SCRIPTING_WXPYTHON=ON``, which is
        what makes the headless ``pcbnew`` module available to the export
        pipeline, plus OCC and SPICE support. QA tests are off.
    * - ``kicad-libs``
      - Shallow-clones the official symbol and footprint libraries at
        ``KICAD_LIBS_TAG``.
    * - ``sg13g2-pdk``, ``sg13g2-models``
      - Checks out a few megabytes of IHP-Open-PDK: the SG13_dev PCell library
        and the SG13G2 KLayout technology files, not the multi-gigabyte PDK.
        This is what lets ``hyp-to-gds`` build vias from real ``via_stack``
        PCells instead of the rectangle fallback. The models stage adds the
        ngspice model files a transistor-level co-simulation reaches.
    * - ``gf180mcu-sheet``, ``gf180mcu-models``, ``gf180mcu-decks``,
        ``gf180mcu-pdk``
      - The gf180mcuD layer sheet, ngspice models and rule decks at
        ``GF180MCU_REF``, for GF180MCU dies in a system.
    * - ``tools``
      - The end of the upper part: the runtime packages, KiCad, the libraries,
        the PDK slices and models, the Nix engines and viewers, the worker
        venv's third-party packages, and the lock files that name every
        package in it.
    * - ``studio-builder``
      - Below the line from here, on the tools image. Builds the in-tree
        KLayout first, then Chiplet Studio against it, at the final runtime
        path ``/opt/adk-tools/chiplet-studio``. Building at the final path
        matters: CMake bakes an absolute ``CONFIGS_DIR`` into the binary, and
        the ctest metadata under ``build/`` stays usable in the verify stage.
    * - ``runtime``
      - The lean image. Chiplet Studio, the submodules and the staged trees
        land as siblings under ``/opt/adk-tools`` mirroring the development
        layout, the staged trees are installed into the worker venv with no
        network, the command wrappers from ``bin/`` are installed into
        ``/usr/local/bin``, the manifest and die views are added, and the
        ecosystem discovery variables are exported.
    * - ``verify``
      - Derives from ``runtime`` and adds the full Chiplet Studio tree over the
        lean copy, then runs every suite. Not shipped; it exists to decide
        whether the runtime image may be tagged.

The tools image, which holds the KiCad compile, is complete before
``studio-builder`` starts, so the two heavy compile stages never run
concurrently and the total stays at or below ``JOBS`` compile jobs; BuildKit
would otherwise double the effective job count and exhaust RAM on large
machines.

The verify stage is the release gate
------------------------------------

``build.sh`` builds ``verify`` before it tags anything, which is the single
invariant that makes a pin trustworthy:

    One commit of ADK-Tools equals one combination that passed the verify gate.

The stage does not just run unit tests. It regenerates a two-die reference
design headless through the whole pipeline and re-checks it. Its steps
include, in this order:

#. Identity checks: the image's tool identity table, the commit each staged
   tree reads back, the pin set the image is labelled with, the vendored
   ``.chiplet`` readers against the staged chiplet-spec, and the plane the
   dies mount on in every IntM4TM2 ``.chiplet`` the image carries.
#. Three checks before the tool suites: the tracked-tree digest test
   (``nix/test_tracked_tree.py``), KLayout's date stamp (its commit's day, not
   the build day), and
   interposer-pnr's live single-layer route cases on the image's OpenROAD,
   where a skip counts as a failure.
#. ADK suite: boundary manifest validation, DRC regressions through the KLayout
   CLI wrapper, and the DRU generator. Cheap and fail-fast, so it runs before
   the other tool suites.
#. gds2kicad suite: footprint and symbol writers, blackbox chiplets, and the
   GUI pieces under the offscreen Qt platform.
#. The reference design's gds2kicad prior steps: its footprints and symbols are
   reproduced from the shipped die GDS and pin list and diffed against the
   committed library, so an upstream change that silently alters its artefacts
   fails before they reach the board.
#. Interposer PDK suite (bump mirror PCell regressions) and interconnect PDK
   suite (manifest contract, schema, 3D body generator). ``jsonschema`` is in
   the verify venv, so the schema check actually executes.
#. The reference design's tracked outputs are snapshotted and the output tree
   is then cleared, so the regeneration writes into an empty directory. Without
   the clear, a regeneration would overwrite in place and any tracked file the
   current pipeline no longer emits would survive unnoticed.
#. The reference design is regenerated headless: ``pcbnew`` to the writers to
   ``hyp_to_gds`` to the assembly DRC. The DRC is required by default, so a
   combination that breaks assembly DRC fails the image build.
#. Reproducibility gate: the shipped deliverables must equal the fresh
   regeneration, compared on die geometry, pillar manifests, boundary geometry
   and a timestamp-normalised geometry digest of the interposer GDS. The clone
   ships the tracked tree, not the regeneration, so without this check a stale
   reference design could ship on a green build. It also guards determinism
   between the GUI and headless paths.
#. Carrier foundry DRC: the interposer PDK's own DRC deck runs on the
   regenerated carrier, and its findings are compared against a committed
   baseline.
#. chiplet-die-flow's die-view XOR tests under the image's KLayout, which also
   check that the ``klayout`` binary is the version of the Python ``klayout``
   module.
#. Chiplet Studio full suite through ``ctest``, with the regenerated
   ``.chiplet`` handed to the gated tests.
#. Plugin suite, with ``pcbnew`` present so the env-gated byte-exact writer
   tests run instead of self-skipping.
#. ``adk-smoke``, exactly as a user would run it.
#. The engines and data the staged trees use: the co-simulation,
   mixed-signal and Verilog-AMS engines and the viewers are the ones
   ``staging.pin`` names and each one runs, every layer sheet packaging-flow
   declares resolves, and a die build finds its tools in the image's own
   store.

``--skip-verify`` exists for local iteration only. It must never be used for a
commit that lands on the release branch.

Pinned components
-----------------

The matrix below is generated from the submodule pins of *this documentation
site*, which is how the site guarantees that what it describes matches the code
it was built against.

.. csv-table:: Pinned components
   :file: tables/versions.csv
   :header: "Repository", "Role", "License", "Version", "Commit"
   :class: adk-wide-table

Two entries need reading carefully. ``KiCad-ADK-MOD`` shows *not pinned here*
because the documentation site does not carry the KiCad tree as a submodule:
nothing on this site is generated from it. The image does pin it, at
``tools/kicad``. And the pins above are the documentation pins, which are not
required to equal the pins of any particular image tag. The authoritative
answer for a running image is the manifest baked into it.

.. _staged_engines:

Staged engines
~~~~~~~~~~~~~~

The flow engines are not submodules of this site either. This table takes the
commit of each one from ``staging.pin`` in the pinned ADK-Tools, and the
distribution and version from the ``pyproject.toml`` at that commit. The engine
pages quote these versions. The chiplet specification is staged too, but it is
a submodule here, so it is in the matrix above, and the build fails unless
``staging.pin`` stages it at the commit this site pins.

.. csv-table:: Staged engines
   :file: tables/staged_engines.csv
   :header: "Staged tree", "Distribution", "Version", "Commit"
   :class: adk-wide-table

The version story
-----------------

There is no single ecosystem version number, and inventing one would be a lie.
Four independent axes exist:

Semantic version of the ADK
    ``IHP-Open-ADK`` carries a ``VERSION`` file. It describes the rule decks,
    the adapters and the registries, and it moves when their behaviour moves.

Calendar tag of the image
    ADK-Tools releases as ``vYYYY.MM``. It describes a combination of tools,
    not a feature set, so a calendar tag is the honest scheme: the only thing
    the tag really asserts is *this set of revisions was verified together on
    this date*.

Format version of the assembly file
    ``.chiplet`` carries its own ``format_version``, owned by the specification
    repository, not by any tool.

Schema version of each sidecar
    Every manifest sidecar carries a schema identifier and version, and each is
    pinned separately by the module that reads it. Readers compare the file's
    version against a constant and treat a mismatch as a hard error, never as a
    warning.

.. csv-table:: Format and schema versions
   :file: tables/schema_versions.csv
   :header: "Artefact", "Identifier", "Version", "Pinned by"
   :class: adk-wide-table

.. tip::
    When you report a problem, quote the image manifest, not a tool version.
    Inside a running container, ``adk-tools`` prints the meta-repository
    describe string, the build timestamp and the pinned reference of every
    bundled tool. That single block identifies the exact combination. Add the
    ``format_version`` or schema version of the file involved when the problem
    is about a file rather than a tool.

    .. code-block:: bash

        adk-tools
        cat /opt/adk-tools/manifest.json

The manifest is generated by ``build.sh`` from ``git submodule status`` and
baked into the image; it is not edited by hand and is not tracked in git. Its
``meta`` field comes from ``git describe --tags --always --dirty`` on the
ADK-Tools repository itself, so an image built from a tagged commit
self-reports ``vYYYY.MM`` and one built a few commits later reports
``vYYYY.MM-<n>-g<sha>``, which still points back at the release.

Updating a clone
----------------

To run a newer release, check out its tag and build it.

A release clone sits on its tag, not on a branch, so fetch the tags and check
out the new one rather than pulling. This is the recipe of the ADK-Tools
README, with the ``nix build`` step of its build recipe added before
``./build.sh``: ``build.sh`` copies OpenROAD, LibreLane and the other Nix
packages from the host's store, and they have to be realised at the commit you
build.

.. literalinclude:: /install/_recipe/update.sh
    :language: bash

The sibling checkouts have to hold the new pins (a ``git fetch`` in each), and
the adk-examples checkout has to be at the new tag; the two ``--check`` calls
say which one does not.

Depending on how old the clone is, one of these one-time cleanups may apply:

- Clones predating the move of the reference design into ``examples/`` still
  carry the removed ``kicad_designs`` submodule as leftovers. Remove both the
  worktree and the gitdir: ``rm -rf tools/kicad_designs
  .git/modules/tools/kicad_designs``.
- If the default job count changed since your last build, the heavy stages
  rebuild once, because ``JOBS`` keys those layers. After that the cache
  behaves normally again.
- A ``/work/example`` from an older image stays as it is. Older images seeded
  it with the reference design; the runtime image now carries none, and the
  worked examples come from adk-examples.

Testing one tool at a different revision
----------------------------------------

This is the main reason the image exists: it lets you change exactly one
variable and hold the other six fixed.

.. code-block:: bash

    # follow the branch .gitmodules names (dev for every tool at this release)
    git submodule update --remote tools/adk
    git add tools/adk
    python3 -B ci/pin_set.py    # the pin set records every staged gitlink
    git commit -am "Bump adk to <ref>"
    ./build.sh

    # or try an arbitrary branch of one tool against the rest of the pinned stack
    cd tools/chiplet-studio && git fetch && git checkout feature/x && cd ../..
    ./build.sh

The pin set takes each tool's commit from the gitlink git has staged, not from
the submodule's checkout, so stage the bump before you regenerate it. The
image is labelled with the committed pin set: ``build.sh`` refuses a
``ci/pin-set.json`` that differs from the commit or from what the staged pins
give, so commit the regenerated file before you build. In the second case
nothing is staged: the image carries ``feature/x`` while its
``org.ihp.adk-tools.pin-set`` label still names the pinned commit, so do not run
such an image under an examples checkout's ``release-lock.json``.

Either way the verify stage decides. If the candidate revision breaks any
suite, the reference design regeneration or the assembly DRC, no image is
tagged and you have your answer without having touched a single other pin.

Keep each bump in its own commit so a regression bisects cleanly, and bump only
to a commit that exists on the tool's tracked branch, so that a later
``--remote`` bump stays on the intended line of development.

Mounting a development checkout
-------------------------------

For iterating on a Python tool, do not rebuild at all. Bind-mount your working
checkout over the baked-in copy, which keeps every other tool, the venv and the
PDK data exactly as the image pinned them:

.. code-block:: bash

    docker run --rm -it \
        -v /path/to/Chiplets-KiCad-Plugin:/opt/adk-tools/chiplet_kicad_plugin \
        -v ~/adk-work:/work -w /work \
        --user "$(id -u):$(id -g)" -e HOME=/tmp \
        "$ADK_TOOLS_IMAGE"

The ``--user`` and ``HOME`` flags are what ``run.sh`` would have set for you.
Without them the container runs as root and writes root-owned files into both
your work directory and your mounted checkout.

The same works for ``/opt/adk-tools/adk``, ``/opt/adk-tools/gds_to_kicad`` and
either PDK tree. Compiled tools cannot be substituted this way; those need a
rebuild.

.. note::
    A mounted checkout is not covered by the verify gate. It is a development
    convenience, and any result obtained with one should be reproduced against
    a properly pinned build before it is trusted.

Releases
--------

Releases use calendar versioning, ``vYYYY.MM``. Development happens on a ``dev``
branch, where submodule bumps and new tools land first and are verified.
``main`` is the stable branch: it moves only at a release, by promotion from
``dev``, and it carries the release tags.

A release is this repository at its tag. No image is published: whoever runs
a release builds the image from the tag, as :doc:`/install/01_container`
describes, and gets an image ID of their own. The adk-examples checkout of the
same release names, in its ``release-lock.json``, the reference image its
examples were checked on and the pin set it was built from, and ``run.sh``
runs any image of that pin set under the lock (:doc:`/install/00_release`).

Licensing
---------

The ADK-Tools repository's own content, the ``Dockerfile``, the scripts and its
documentation, is GPL-3.0-or-later, with one rule on top: a file's own
``SPDX-License-Identifier`` line decides its license. The record format schemas
in ``formats/`` and the files whose SPDX line says Apache-2.0, most of ``ci/``
and ``nix/`` among them, are Apache-2.0.

The image it builds is a **mere aggregation** of independently developed and
independently licensed tools and data. Each bundled component retains its own
license. Packaging them together in one image does not relicense any of them,
and the repository's own ``LICENSE`` does not extend to the bundled components.
The set spans GPL, Apache-2.0, CC-BY-SA-4.0 and permissive (MIT and BSD)
licenses.

The image does contain GPL-licensed programs: the KiCad fork, Chiplet Studio,
the KiCad plugin, gds2kicad, the staged assembly-lvs, chiplet-cosim,
chiplet-flow, interposer-pnr and packaging-flow, KLayout in its in-tree build,
the PyPI wheel in the worker venv and the Nix build, the SG13G2
``pycell4klayout-api``, PyQt6 in the worker venv, the programs from the Nix
closures (Icarus Verilog, GTKWave, GAW, Xschem, gnucap and modelgen-verilog, and
the OpenSTA inside OpenROAD), and the ``featherpad`` and ``vim`` editors
installed from Ubuntu. If you redistribute the image, or any binary built from
it, you must make the **corresponding source** of those components available to
recipients under the terms of their respective GPL licenses. The submodules and
the external components are pinned to public upstreams, so pointing recipients
at the exact pinned commit or version satisfies the obligation for them. The Nix
programs are built from the revisions ``flake.lock`` and ``flake.nix`` pin. The
image carries each staged tree's source as a git checkout under
``/opt/adk-tools/staging/<tree>``, and whoever redistributes the image passes
that source on with it. The permissive and CC-licensed components carry their
own lighter attribution requirements.

``LICENSE`` and ``NOTICE.md`` travel inside the image at ``/opt/adk-tools/``,
and ``NOTICE.md`` carries the per-component table of SPDX identifiers and source
URLs. The KiCad library exception applies to the bundled symbol and footprint
libraries: your design output does not inherit CC-BY-SA-4.0, while the
libraries themselves remain under it.

.. tip::
    For the authoritative, version-exact license texts, read each component's
    own ``LICENSE`` or ``COPYING`` at the pinned commit. Chiplet Studio
    additionally ships a ``THIRD-PARTY-LICENSES.md`` covering the libraries
    linked into its binary.
