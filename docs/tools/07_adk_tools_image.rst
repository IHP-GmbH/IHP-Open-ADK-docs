The ADK-Tools image
===================

.. include:: /common.inc

ADK-Tools is the distribution channel of the ecosystem: one Docker image that
carries every tool of the heterogeneous integration flow, compiled and
pre-wired, callable by name. It is not a codebase. It is a version lockfile
plus a build recipe, and the image built from one of its commits *is* that
locked combination.

The repository is |tools-repo|. If you are looking for the getting-started
instructions rather than the design of the image, read
:doc:`/install/01_container`.

.. note::
    ADK-Tools is a |current-status|. The tool pages in this section describe
    the individual repositories; this page describes how they are pinned,
    built and shipped together.

The submodules are the lockfile
-------------------------------

Every tool lives in its own repository and is registered here as a git
submodule under ``tools/``:

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
ADK-Tools therefore names one exact revision of each of the seven tools, and a
fresh ``git clone --recurse-submodules`` at that commit reproduces the exact
tool set.

Not every pin is a submodule. The remaining reproducibility-relevant pins live
as build arguments in the ``Dockerfile`` and are bumped deliberately, in their
own commits:

.. list-table:: Non-submodule pins in the Dockerfile
    :header-rows: 1
    :widths: 26 74

    * - Build argument
      - What it pins
    * - ``KICAD_LIBS_TAG``
      - Release tag of the official KiCad symbol and footprint libraries
        (currently ``9.0.9.1``). The fork reports itself as 9.99, the v10
        development line, but predates the ``.kicad_symdir`` format, so the v9
        libraries are the compatible set. 3D model packages are deliberately
        not shipped.
    * - ``SG13G2_REF``
      - IHP-Open-PDK commit the SG13G2 KLayout slice is cut from.
    * - ``PYCELL_API_REF``, ``PYPREPROCESSOR_REF``
      - The two IHP-Open-PDK submodules that the PCell library needs, cloned at
        their gitlink pins.
    * - ``KLAYOUT_PIP``, ``PYYAML_PIP``, ``PYQT6_PIP``, ``JINJA2_PIP``,
        ``JSONSCHEMA_PIP``, ``PSUTIL_PIP``, ``PYTEST_PIP``
      - Exact versions of the worker venv's direct dependencies.

The direct Python dependencies are exact-pinned on purpose. With only
``klayout`` pinned, the behaviour-defining packages were free to drift against
live PyPI on a cache-cold rebuild, which can silently flip a verify-stage
suite. Their transitive dependencies are still resolved by pip and are not
locked.

.. note::
    The base image (``ubuntu:24.04``) and the apt packages are not pinned, and
    the build needs live network access to github.com and gitlab.com. The image
    is reproducible at the level of the tool set, not byte for byte.

Build stages
------------

The ``Dockerfile`` is a multi-stage build. ``build.sh`` drives it; a plain
``docker build .`` also works and lands on the ``verify`` target, which is the
default stage precisely so that a bare build never produces an untested image.

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
        reused everywhere. The two library-fetching stages start from a bare
        base image instead, because they need no toolchain.
    * - ``kicad-builder``
      - Compiles the KiCad fork with ``KICAD_SCRIPTING_WXPYTHON=ON``, which is
        what makes the headless ``pcbnew`` module available to the export
        pipeline, plus OCC and SPICE support. QA tests are off.
    * - ``studio-builder``
      - Builds the in-tree KLayout first, then Chiplet Studio against it, at
        the final runtime path ``/opt/adk-tools/chiplet-studio``. Building at
        the final path matters: CMake bakes an absolute ``CONFIGS_DIR`` into
        the binary, and the ctest metadata under ``build/`` stays usable in the
        verify stage.
    * - ``kicad-libs``
      - Shallow-clones the official symbol and footprint libraries at
        ``KICAD_LIBS_TAG``.
    * - ``sg13g2-pdk``
      - Checks out a few megabytes of IHP-Open-PDK: the SG13_dev PCell library
        and the SG13G2 KLayout technology files, not the multi-gigabyte PDK.
        This is what lets ``hyp-to-gds`` build vias from real ``via_stack``
        PCells instead of the rectangle fallback.
    * - ``runtime``
      - The lean image. KiCad lands in ``/usr``, the Python tools and the PDK
        data land as siblings under ``/opt/adk-tools`` mirroring the
        development layout, the worker venv is created, the command wrappers
        from ``bin/`` are installed into ``/usr/local/bin``, and the ecosystem
        discovery variables are exported.
    * - ``verify``
      - Derives from ``runtime`` and adds the full Chiplet Studio tree over the
        lean copy, then runs every suite. Not shipped; it exists to decide
        whether the runtime image may be tagged.

``build.sh`` sequences ``kicad-builder`` ahead of the rest so the two heavy
compile stages never run concurrently and the total stays at or below ``JOBS``
compile jobs; BuildKit would otherwise double the effective job count and
exhaust RAM on large machines.

The verify stage is the release gate
------------------------------------

``build.sh`` builds ``verify`` before it tags anything, which is the single
invariant that makes a pin trustworthy:

    One commit of ADK-Tools equals one combination that passed the verify gate.

The stage does not just run unit tests. It regenerates the reference design
headless through the whole pipeline and re-checks it:

#. ADK suite: boundary manifest validation, DRC regressions through the KLayout
   CLI wrapper, and the DRU generator. Cheap and fail-fast, so it runs first.
#. gds2kicad suite: footprint and symbol writers, blackbox chiplets, and the
   GUI pieces under the offscreen Qt platform.
#. The reference design's gds2kicad prior steps: its footprints and symbols are
   reproduced from the shipped die GDS and pin list and diffed against the
   committed library, so an upstream change that silently alters the demo
   artefacts fails before they reach the board.
#. Interposer PDK suite (bump mirror PCell regressions) and interconnect PDK
   suite (manifest contract, schema, 3D body generator). ``jsonschema`` is in
   the verify venv, so the schema check actually executes.
#. The tracked demo outputs are snapshotted and the output tree is then
   cleared, so the regeneration writes into an empty directory. Without the
   clear, a regeneration would overwrite in place and any tracked file the
   current pipeline no longer emits would survive unnoticed.
#. The two-die interposer design is regenerated headless: ``pcbnew`` to the
   writers to ``hyp_to_gds`` to the assembly DRC, with ``--require-drc`` so a
   combination that breaks assembly DRC fails the image build.
#. Reproducibility gate: the shipped deliverables must equal the fresh
   regeneration, compared on die geometry, pillar manifests, boundary geometry
   and a timestamp-normalised geometry digest of the interposer GDS. The
   runtime image bakes the tracked tree rather than the regeneration, so
   without this check a stale demo could ship on a green build. It also guards
   determinism between the GUI and headless paths.
#. Chiplet Studio full suite through ``ctest``, with the regenerated
   ``.chiplet`` handed to the gated tests.
#. Plugin suite, with ``pcbnew`` present so the env-gated byte-exact writer
   tests run instead of self-skipping.
#. ``adk-smoke``, exactly as a user would run it.

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

.. code-block:: bash

    cd ADK-Tools
    git pull
    git submodule update --init --recursive
    ./build.sh          # cached stages rebuild only what changed

Depending on how old the clone is, one of these one-time cleanups may apply:

- Clones predating the move of the reference design into ``examples/`` still
  carry the removed ``kicad_designs`` submodule as leftovers. Remove both the
  worktree and the gitdir: ``rm -rf tools/kicad_designs
  .git/modules/tools/kicad_designs``.
- If the default job count changed since your last build, the heavy stages
  rebuild once, because ``JOBS`` keys those layers. After that the cache
  behaves normally again.
- A ``/work/example`` seeded by an older image is refreshed automatically when
  the image ships a changed demo, and the previous copy is kept once at
  ``/work/example.prev``.

Testing one tool at a different revision
----------------------------------------

This is the main reason the image exists: it lets you change exactly one
variable and hold the other six fixed.

.. code-block:: bash

    # follow the branch tracked in .gitmodules (usually main)
    git submodule update --remote tools/adk
    ./build.sh && git commit -am "Bump adk to <ref>"

    # or try an arbitrary branch of one tool against the rest of the pinned stack
    cd tools/chiplet-studio && git fetch && git checkout feature/x && cd ../..
    ./build.sh

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
        -v ~/git/Chiplets-KiCad-Plugin:/opt/adk-tools/chiplet_kicad_plugin \
        -v ~/adk-work:/work -w /work \
        --user "$(id -u):$(id -g)" -e HOME=/tmp \
        adk-tools:dev

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
``dev``, and it carries the release tags. ``release.sh`` publishes the image
under an immutable version tag, moves ``latest`` onto the same digest, and
refuses to publish at all unless the provenance is clean:
the working tree must be clean, no submodule may be dirty or off its pin, ``HEAD``
must be exactly at the tag, and the ``meta`` string baked into the image being
published must equal the tag. That last check is the definitive one, because it
compares the artefact against the tag rather than the source tree.

.. note::
    There is currently no pre-built image to download. Build locally with
    ``build.sh``, as described in :doc:`/install/01_container`.

Licensing
---------

The ADK-Tools repository's own content, the ``Dockerfile``, the scripts and its
documentation, is GPL-3.0-or-later.

The image it builds is a **mere aggregation** of independently developed and
independently licensed tools and data. Each bundled component retains its own
license. Packaging them together in one image does not relicense any of them,
and the repository's own ``LICENSE`` does not extend to the bundled components.
The set spans GPL, Apache-2.0, CC-BY-SA-4.0 and permissive (MIT and BSD)
licenses.

The image does contain GPL-licensed programs: the KiCad fork, Chiplet Studio,
the KiCad plugin, gds2kicad, KLayout in both its in-tree build and the PyPI
wheel in the worker venv, the SG13G2 ``pycell4klayout-api``, PyQt6 in the worker
venv, and the ``featherpad`` and ``vim`` editors installed from Ubuntu. If you
redistribute the image, or any binary built from it, you must make the
**corresponding source** of those components available to recipients under the
terms of their respective GPL licenses. Every component is pinned to a public
upstream, so pointing recipients at the exact pinned commit or version, or
shipping the source alongside the image, satisfies the obligation. The
permissive and CC-licensed components carry their own lighter attribution
requirements.

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
