Installing on the host
======================

.. include:: /common.inc

.. note::
    The container described in :doc:`/install/01_container` is the supported
    installation path. Everything on this page is derived from the same
    recipe, the ADK-Tools ``Dockerfile``, which is the only place the real
    dependency set is recorded. It is a best-effort route: no combination of
    host-installed versions is gated by the verify stage, so when something
    behaves differently from the container, the container is right.

Read this page if you already have a KiCad or KLayout installation you need to
keep, if you cannot run Docker, or if you are developing one of the tools and
want it on your own machine. You can also install a subset: the tools are
independent programs that find each other through the environment described in
:doc:`/install/03_environment`, so a host installation of only the ADK and
KLayout is a perfectly reasonable thing to have.

The reference platform
----------------------

The image is built on Ubuntu 24.04, whose system Python is 3.12. That is the
combination every test suite is exercised against. Other distributions and
Python versions are expected to work but are not covered by any gate. The
chiplet format reference reader declares support back to Python 3.8, and
gds2kicad's own CI runs 3.11, so the practical floor is around 3.11 rather
than 3.12.

System packages
---------------

The image installs one shared apt layer holding the union of the build
dependencies of the KiCad fork, the build dependencies of Chiplet Studio and
KLayout, and the runtime utilities. On Ubuntu 24.04 the same set is:

.. code-block:: bash

    sudo apt-get install -y \
        build-essential cmake ninja-build gettext git curl wget file \
        ca-certificates pkg-config \
        libglm-dev zlib1g-dev libzstd-dev libcurl4-openssl-dev libspnav-dev \
        libcairo2-dev libpixman-1-dev libgit2-dev libboost-all-dev \
        libfreetype-dev libharfbuzz-dev libfontconfig1-dev libngspice0-dev \
        libocct-data-exchange-dev libocct-draw-dev libocct-foundation-dev \
        libocct-modeling-algorithms-dev libocct-modeling-data-dev \
        libocct-ocaf-dev libocct-visualization-dev \
        protobuf-compiler libprotobuf-dev swig \
        python3 python3-dev python3-venv python3-pip python3-tk \
        python3-wxgtk4.0 libwxgtk3.2-dev libwxgtk-webview3.2-dev \
        libglew-dev libgl1-mesa-dev libglu1-mesa-dev libnng-dev \
        unixodbc-dev libgtk-3-dev libsecret-1-dev \
        libpoppler-dev libpoppler-glib-dev libpoppler-cpp-dev \
        qt6-base-dev qt6-base-dev-tools libqt6opengl6-dev \
        libqt6core5compat6-dev libyaml-cpp-dev ruby ruby-dev \
        xvfb xauth libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 \
        libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
        libxcb-xinerama0 libxcb-xfixes0

You need far less than this if you are not building KiCad or Chiplet Studio
from source. The first two groups are the KiCad build, the Qt and Ruby group is
KLayout and Chiplet Studio, and the last group is the X and xcb runtime the Qt
tools need. ``python3-tk`` is not optional if you want the SG13G2 PCells: the
PCell API imports ``tkinter``.

KLayout's qmake-based build expects a plain ``qmake``, which Ubuntu does not
provide for Qt 6:

.. code-block:: bash

    sudo ln -sf /usr/bin/qmake6 /usr/bin/qmake

The worker virtual environment
------------------------------

Every Python tool in the flow runs from one interpreter, and it is not KiCad's
bundled Python. Create it once and point the tools at it.

.. code-block:: bash

    python3 -m venv --system-site-packages ~/adk-venv
    ~/adk-venv/bin/pip install \
        klayout==0.30.5 \
        PyYAML==6.0.3 \
        PyQt6==6.11.0 \
        jinja2==3.1.6 \
        jsonschema==4.26.0 \
        psutil==7.2.2 \
        pytest==9.1.0

Two details matter here.

``--system-site-packages`` is deliberate. With it, the venv interpreter also
sees ``pcbnew`` from the KiCad installation and ``wx`` from
``python3-wxgtk4.0``, so a single interpreter can drive the whole pipeline, from
reading a board to writing a GDS. Without it you need a second interpreter for
the pcbnew half and the plugin's worker handoff stops making sense.

The versions above are the ones the image pins. They are exact rather than
minimum because the loose alternative let behaviour-defining packages drift
against live PyPI and silently change test outcomes. The declared minimums in
the individual repositories are looser (``klayout>=0.28`` and ``PyYAML>=6.0``
for the plugin worker, ``PyQt6>=6.6.0`` for gds2kicad), but the pinned set is
the combination that is actually verified together.

Then export the interpreter so the KiCad plugin uses it:

.. code-block:: bash

    export KICAD_CHIPLET_PYTHON=$HOME/adk-venv/bin/python3

KLayout
-------

KLayout appears in three roles.

The ``klayout`` executable on ``PATH``
    The ADK assembly DRC runner shells out to ``klayout -b`` to execute the
    deck, and it checks the version first: it requires **0.29.11 or newer** and
    exits with a clear message if the binary is missing from ``PATH``.

The ``klayout`` Python module
    ``run_drc.py``, ``hyp_to_gds.py``, gds2kicad and the PDK Python tooling all
    import ``klayout.db`` directly. This is the PyPI wheel installed in the
    venv above. A system KLayout whose bindings are on ``PYTHONPATH`` also
    works; if ``import klayout.db`` fails, the converters say so and exit
    rather than guessing.

The KLayout libraries linked into Chiplet Studio
    Chiplet Studio uses KLayout as a library for its 2D drill-down view, and
    builds it in-tree from its own ``extern/klayout`` submodule. That build is
    pinned by Chiplet Studio, independently of the wheel version above.

An ordinary distribution KLayout package satisfies the first two roles as long
as it is recent enough. Only the third requires a source build.

The KiCad fork
--------------

The ecosystem is developed against the IHP KiCad fork, |kicad-repo|. Build it
the way the image does:

.. code-block:: bash

    git clone https://github.com/IHP-GmbH/KiCad-ADK-MOD.git
    cmake -G Ninja -S KiCad-ADK-MOD -B build/kicad \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr \
        -DKICAD_SCRIPTING_WXPYTHON=ON \
        -DKICAD_USE_OCC=ON \
        -DKICAD_SPICE=ON \
        -DKICAD_BUILD_QA_TESTS=OFF
    ninja -C build/kicad -j8
    sudo ninja -C build/kicad install

``KICAD_SCRIPTING_WXPYTHON=ON`` is the flag that matters. It is what puts the
``pcbnew`` Python module on the system path, and the headless export pipeline,
the plugin's test suite and the reference design regeneration all depend on it.

You do not strictly need the fork to use the flow. The chiplet export plugin is
a pcbnew action plugin and the writers are pure Python, so a stock KiCad 9.0
runs the export. What the fork adds is the C++ side: the headless
``ExportBoardToChipletFile`` and ``ExportBoardToHyperlynxFile`` functions
exposed through SWIG, which back the plugin's byte-exact writer parity tests.
The legacy ``File > Export > Chiplet...`` and ``File > Export > Hyperlynx...``
menu actions have been removed from the fork; the plugin is the sole entry
point.

Symbol and footprint libraries
    The fork reports itself as 9.99, the v10 development line, but predates the
    ``.kicad_symdir`` format, so the KiCad **v9** libraries are the compatible
    set. The image clones ``kicad-symbols`` and ``kicad-footprints`` at tag
    ``9.0.9.1`` and points ``KICAD9_SYMBOL_DIR`` and ``KICAD9_FOOTPRINT_DIR``
    at them. On a host, an ordinary distribution install of the v9 libraries
    is fine.

.. tip::
    If pcbnew is slow to start, the cause is usually footprint enumeration: the
    stock library set holds roughly fifteen thousand footprints that get
    re-read whenever no ``fp-info-cache`` survives. The chiplet flow resolves
    its interposer footprints from each project's own ``${KIPRJMOD}`` library,
    so trimming the global footprint table to a small useful set costs you
    nothing in this flow.

The chiplet export plugin
-------------------------

Make the plugin directory visible to pcbnew, then give it a worker interpreter.

.. code-block:: bash

    git clone https://github.com/IHP-GmbH/Chiplets-KiCad-Plugin.git
    ln -s "$PWD/Chiplets-KiCad-Plugin" \
          ~/.config/kicad/9.0/scripting/plugins/chiplet_kicad_plugin

Adjust the version directory to your KiCad installation. Restart pcbnew and the
action appears under ``Tools > External Plugins > Chiplet Export``.

The worker interpreter needs ``klayout`` and ``PyYAML``, which KiCad's bundled
Python does not have. The plugin looks for ``.venv/bin/python3`` next to itself
before falling back to other candidates, so the simplest arrangement is a venv
inside the plugin directory:

.. code-block:: bash

    python3 -m venv Chiplets-KiCad-Plugin/.venv
    Chiplets-KiCad-Plugin/.venv/bin/pip install -r \
        Chiplets-KiCad-Plugin/requirements.txt

If you would rather use the shared venv from above, set
``KICAD_CHIPLET_PYTHON`` to its interpreter before launching KiCad, or define
it as a KiCad project text variable. The full resolution order, including the
fact that a plugin-local ``.venv`` outranks the project text variable, is in
:doc:`/install/03_environment`.

``hyp_to_gds.py`` is also a standalone command. Run it from the plugin checkout
with the worker interpreter directly when you want the conversion without the
GUI.

gds2kicad
---------

Nothing to build and nothing to install. Clone it and run the scripts from the
clone root with the venv interpreter:

.. code-block:: bash

    git clone https://github.com/IHP-GmbH/gds2kicad.git
    export GDS_TO_KICAD_ROOT="$PWD/gds2kicad"
    ~/adk-venv/bin/python3 "$GDS_TO_KICAD_ROOT/unified_gui.py"

It needs PyQt6 for the GUIs and KLayout to read GDS, both already in the venv.
On a slim box PyQt6 also needs the xcb runtime libraries from the package list
above.

The ADK
-------

The ADK is pure Python with no build step and no installable package:

.. code-block:: bash

    git clone https://github.com/IHP-GmbH/IHP-Open-ADK.git
    export ADK_ROOT="$PWD/IHP-Open-ADK"

Its dependencies are modest: ``klayout`` for the module and the executable,
``PyYAML`` for the vendored ``.chiplet`` reader, and ``jinja2`` for the KiCad
DRU generator. ``jsonschema`` is needed only by the test suite, which skips the
schema checks when it is absent.

There is no installed ``adk`` package and no ``__init__.py``, which is
deliberate: importers add the relevant directory to ``sys.path`` and import the
bare module. Run the runner by path:

.. code-block:: bash

    ~/adk-venv/bin/python3 "$ADK_ROOT/klayout/drc/run_drc.py" --help

See :doc:`/adk/05_run_drc` for what the runner does with those arguments.

Chiplet Studio
--------------

Chiplet Studio is a compiled Qt application that links KLayout, so it needs a
source build. Build KLayout in-tree first, then the application against it:

.. code-block:: bash

    git clone --recurse-submodules https://github.com/IHP-GmbH/chiplet-studio.git
    cd chiplet-studio
    (cd extern/klayout && ./build.sh -j8 -without-qtbinding)
    mkdir -p build && cd build
    cmake .. -DKLAYOUT_BUILD_DIR="$PWD/../extern/klayout/bin-release"
    make -j8

The binary lands at ``build/chiplet-studio``. It needs the in-tree KLayout
libraries at run time:

.. code-block:: bash

    export LD_LIBRARY_PATH=/path/to/chiplet-studio/extern/klayout/bin-release
    ./build/chiplet-studio path/to/assembly.chiplet

.. note::
    CMake bakes an absolute configuration directory into the binary. If you
    move the tree after building, rebuild it rather than moving the binary.
    The repository also ships a portable-bundle script for machines without the
    build dependencies.

The PDKs
--------

Both PDKs are data plus Python tooling. Clone them and export their roots:

.. code-block:: bash

    git clone https://github.com/IHP-GmbH/OpenIntM4TM2.git
    git clone https://github.com/IHP-GmbH/IHP-Interconnect-IntM4TM2.git
    export INTERPOSER_PDK_ROOT="$PWD/OpenIntM4TM2"
    export INTERCONNECT_PDK_ROOT="$PWD/IHP-Interconnect-IntM4TM2"

Register the interposer KLayout technology so generated interposer and assembly
GDS files open with named, coloured layers:

.. code-block:: bash

    export KLAYOUT_PATH="$HOME/.klayout:$INTERPOSER_PDK_ROOT/libs.tech/klayout"

The first component of ``KLAYOUT_PATH`` must be a writable configuration home,
because KLayout writes its own configuration into it. The interposer tree is
safe to put on that path: its only macro does not autorun.

The base SG13G2 PDK slice
-------------------------

``hyp_to_gds`` builds vias from the SG13G2 ``via_stack`` PCells when it can
find them, and falls back to plain rectangles when it cannot. Point ``PDK_ROOT``
at an IHP-Open-PDK checkout to get the PCell path:

.. code-block:: bash

    export PDK_ROOT=/path/to/IHP-Open-PDK

What is actually needed is small: the ``sg13g2_pycell_lib`` PCell library and
the ``sg13g2.lyt``, ``.lyp`` and ``.map`` technology files under
``ihp-sg13g2/libs.tech/klayout/``, plus the ``pycell4klayout-api`` and
``pypreprocessor`` submodules of that repository. The image checks out exactly
that slice, a few megabytes rather than the full PDK.

.. note::
    Do not put the SG13G2 tree on ``KLAYOUT_PATH``. Its PCell autorun macro
    expects system-level ``psutil`` and ``tkinter`` and pops error dialogs in
    the GUI. ``hyp_to_gds`` self-registers the library from ``PDK_ROOT``
    instead, which is why the environment variable and the KLayout search path
    are separate concerns.

    A missing or broken SG13G2 install is not fatal. The tool prints a note and
    falls back to rectangle vias. This is the one dependency in the flow whose
    absence degrades rather than aborts, because the fallback output is still
    correct geometry.

OpenROAD
--------

OpenROAD is **not** part of the image and is not needed for the main flow. The
ADK's ``chiplet2dbx`` exporter derives a geometric 3Dblox view from a finalised
``.chiplet`` file, and writing that view has no OpenROAD dependency. You only
need an OpenROAD installation if you want to run its ``check_3dblox`` command
on the result. Install it from its own upstream instructions and keep it
outside this environment. See :doc:`/adk/07_chiplet2dbx`.

Wiring it together
------------------

Once the pieces are on disk, the tools find each other through the discovery
chain, not through hard-coded paths. A host installation that keeps every
checkout as a sibling in one directory is resolved automatically by the upward
walk. Anything else needs the environment variables set. The full precedence
rules, the accepted directory names, and which lookups fail loudly rather than
degrading silently are in :doc:`/install/03_environment`.

A reasonable check that the installation is coherent is to run the test suites
the image runs, from each checkout:

.. code-block:: bash

    cd "$ADK_ROOT" && ~/adk-venv/bin/python3 -m pytest tests -q
    cd "$GDS_TO_KICAD_ROOT" && \
        QT_QPA_PLATFORM=offscreen ~/adk-venv/bin/python3 -m pytest tests -q
    cd "$INTERPOSER_PDK_ROOT/libs.tech/klayout" && \
        ~/adk-venv/bin/python3 -m pytest intm4tm2_tests -q
    cd "$INTERCONNECT_PDK_ROOT/libs.tech/klayout" && \
        ~/adk-venv/bin/python3 -m pytest interconnect_tests -q

The plugin suite additionally needs ``pcbnew`` importable, and its byte-exact
writer tests self-skip when it is not. That difference is exactly why the
container is the supported path: inside it, nothing skips.
