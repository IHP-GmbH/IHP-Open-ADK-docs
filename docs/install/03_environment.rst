Environment and path discovery
==============================

.. include:: /common.inc

The ecosystem is seven repositories that have to find each other at run time.
The KiCad plugin needs the ADK's DRC runner. The HyperLynx to GDS converter
needs the interposer PDK's Cu-pillar generator and the interconnect PDK's
method manifest. The interposer PDK's bump mirror needs gds2kicad's pin list
reader. Chiplet Studio needs to resolve the paths written inside a ``.chiplet``
file, which was produced on someone else's machine.

No tool contains fixed-depth path arithmetic, a ``parents[3]`` or a ``../../..``
reaching into a sibling repository, because that hard-codes a directory layout
that only holds on the machine where it was written. Every consumer resolves
every dependency with the same chain, implemented identically in the Python tools
and in Chiplet Studio's C++ reader.

The discovery chain
-------------------

First hit wins:

#. **Environment variable** naming the dependency root.
#. **KiCad project text variable** of the same name, where a board is in scope.
   This leg exists only in plugin contexts, since it needs a loaded board to
   read the variable from. Set these under ``Board Setup > Text Variables``.
#. **Upward walk** from the consumer looking for a conventional sibling
   directory. Each root accepts a small closed set of candidate names. For
   three of the five roots that set includes the name a default clone of the
   upstream GitHub repository produces; for ``ADK_ROOT`` and
   ``GDS_TO_KICAD_ROOT`` it does not. The table below lists them.
#. **Loud failure**, naming every location that was probed and the variable to
   set.

A candidate is not accepted merely because the directory exists. Each root has
a **marker subpath** that must exist under it, and a set-but-invalid
environment value falls through to the walk rather than winning and then
failing later. This is what makes a stale ``INTERPOSER_PDK_ROOT`` pointing at a
deleted checkout harmless instead of confusing.

The variables
-------------

.. list-table::
    :header-rows: 1
    :widths: 22 22 34 22

    * - Variable
      - Dependency root
      - Consumers
      - Value in the container
    * - ``ADK_ROOT``
      - The ADK checkout
      - Plugin DRC step, gds2kicad canonical layer lookup
      - ``/opt/adk-tools/adk``
    * - ``INTERPOSER_PDK_ROOT``
      - Interposer PDK
      - ``hyp_to_gds`` Cu-pillar generation, default layer properties
      - ``/opt/adk-tools/OpenIntM4TM2``
    * - ``INTERCONNECT_PDK_ROOT``
      - Interconnect PDK
      - Method manifest readers, Chiplet Studio fragments, the 3D bump body
        and bump LEF generators
      - ``/opt/adk-tools/IHP-Interconnect-IntM4TM2``
    * - ``GDS_TO_KICAD_ROOT``
      - gds2kicad checkout
      - ``bump_mirror`` pin list import
      - ``/opt/adk-tools/gds_to_kicad``
    * - ``PDK_ROOT``
      - Base IHP SG13G2 PDK
      - ``hyp_to_gds`` ``via_stack`` PCells, Chiplet Studio
      - ``/opt/adk-tools/IHP-Open-PDK``
    * - ``KICAD_CHIPLET_PYTHON``
      - Worker interpreter, not a root
      - Plugin orchestrator
      - ``/opt/adk-tools/venv/bin/python3``

The container sets all of them, which is why nothing inside it needs
configuring. It additionally sets ``ADK_TOOLS=/opt/adk-tools`` as the parent of
all of them, and a ``KLAYOUT_PATH`` that registers the interposer KLayout
technology.

Marker subpaths and accepted directory names
--------------------------------------------

The walk and the environment check share one table, reproduced identically in
``hyp_to_gds.py``, the ADK's ``pads_vs_pillars.py`` and Chiplet Studio's
``ChipletFormat.cpp``:

.. list-table::
    :header-rows: 1
    :widths: 30 34 36

    * - Variable
      - Directory names accepted by the walk
      - Marker that must exist under the root
    * - ``ADK_ROOT``
      - ``adk``, ``ADK``
      - ``klayout/drc``
    * - ``INTERPOSER_PDK_ROOT``
      - ``interposer``, ``OpenIntM4TM2``
      - ``libs.tech/klayout``
    * - ``INTERCONNECT_PDK_ROOT``
      - ``interconnect_pdk``, ``IHP-Interconnect-IntM4TM2``
      - ``manifest``
    * - ``GDS_TO_KICAD_ROOT``
      - ``gds_to_kicad``, ``gds-to-kicad``
      - ``pdks``
    * - ``PDK_ROOT``
      - ``IHP-Open-PDK``
      - ``ihp-sg13g2/libs.tech/klayout``

Two consequences are worth stating plainly. First, a development layout where
all checkouts are siblings in one directory needs almost no environment: the
walk resolves ``INTERPOSER_PDK_ROOT``, ``INTERCONNECT_PDK_ROOT`` and
``PDK_ROOT`` from a default clone, because for those three the upstream
repository name is itself an accepted name. ``ADK_ROOT`` and
``GDS_TO_KICAD_ROOT`` are not: they accept ``adk``/``ADK`` and
``gds_to_kicad``/``gds-to-kicad``, which differ from the upstream names
``IHP-Open-ADK`` and ``gds2kicad``, so those two need a rename, a symlink or
the variable. Second, the accepted names are a closed set. An unknown variable name is
treated as a typo rather than as permission to expand an arbitrary environment
variable, which keeps a ``.chiplet`` file from reaching into unrelated
environment values.

.. tip::
    The simplest correct host layout is one parent directory holding
    ``IHP-Open-ADK`` renamed or symlinked to ``adk``, ``OpenIntM4TM2``,
    ``IHP-Interconnect-IntM4TM2``, ``gds2kicad`` renamed or symlinked to
    ``gds_to_kicad``, and ``Chiplets-KiCad-Plugin``. Those two renames are the
    only ones needed: ``IHP-Open-ADK`` and ``gds2kicad`` are the repository
    names but are not accepted walk names, so each needs a rename, a symlink,
    or its variable (``ADK_ROOT``, ``GDS_TO_KICAD_ROOT``) set explicitly.

Where the walk starts
---------------------

The walk climbs parent directories, but from different starting points
depending on who is asking, and the difference matters when your checkouts are
not siblings:

- The Python tools walk up from the consuming source file. ``hyp_to_gds.py``
  walks from its own location inside the plugin checkout; the ADK's checks walk
  from the ADK root.
- Chiplet Studio walks up from the directory of the ``.chiplet`` file being
  read, because that is the only anchor a viewer has for a file authored
  elsewhere.

Two lookups have their own shape
--------------------------------

Most consumers use the table above verbatim. Two do not, and both differences
are deliberate.

The worker interpreter
~~~~~~~~~~~~~~~~~~~~~~

``KICAD_CHIPLET_PYTHON`` names an interpreter rather than a root, and its chain
is:

#. The ``KICAD_CHIPLET_PYTHON`` environment variable.
#. ``<plugin_dir>/.venv/bin/python3``, the recommended local setup.
#. The ``KICAD_CHIPLET_PYTHON`` KiCad project text variable, when a board is in
   scope.
#. ``python3`` from ``PATH``, accepted only if a subprocess probe can
   ``import klayout.db`` and ``import yaml`` with it.

Note the order: **a plugin-local ``.venv`` outranks the project text
variable**. If a checkout has a stale or broken ``.venv``, it wins over the
text variable you just set, so the fix is to remove or repair the ``.venv``
rather than to add an override. The environment variable and the text variable
are treated as explicit overrides and are used as-is when executable, without
the import probe; only the ``PATH`` candidate is probed, because it is the only
one nobody chose deliberately.

Paths are returned absolute but never symlink-resolved. Resolving would hydrate
``.venv/bin/python3`` to the underlying ``/usr/bin/python3.12``, which bypasses
the ``pyvenv.cfg`` lookup and makes the venv's packages disappear from
``sys.path``. The exact path is the point.

The ADK runner, seen from the plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The plugin's lookup for ``run_drc.py`` adds a leg in front and shortens the
walk behind:

#. An explicit ADK root chosen in the export dialog, the GUI face of the
   environment variable leg.
#. The ``ADK_ROOT`` environment variable.
#. The ``ADK_ROOT`` KiCad project text variable.
#. ``<plugin_dir>/../adk``, a single conventional sibling rather than a full
   upward walk.

Each candidate is tested by whether ``klayout/drc/run_drc.py`` exists beneath
it, and the failure message lists every path that was tried.

Fail loud, do not degrade
-------------------------

When a dependency is required for correctness, the tool aborts. It names the
locations it probed and the variable to set. A silent degraded mode is only
acceptable when the output stays correct without the dependency.

The precedent is Cu pillars. An assembly GDS written without them would open
fine, pass the assembly DRC and look fabricable, because **no geometric check can
flag geometry that is absent**. So the converter refuses:

.. code-block:: text

    ERROR: Cu-pillar generation requested (connection=cupillar) but
    bump_mirror is unavailable. Set INTERPOSER_PDK_ROOT to the interposer PDK
    checkout (libs.tech/klayout/python/bump_mirror.py) and retry. Refusing to
    emit a complete GDS without its pillars.

The same reasoning gives the whole ecosystem its rule. The ADK's assembly DRC
aborts when the boundary manifest is missing rather than checking an assembly
with no chiplets in it. The 3Dblox export aborts when the interconnect PDK's
bump LEF generator cannot be found. An unresolvable ``${VAR}`` aborts instead of
leaving a literal ``${VAR}`` in a path that would merely "not exist" later and
mask the real problem.

Two lookups deliberately degrade instead, and both print a warning:

- **The SG13G2 base PDK.** Without ``PDK_ROOT``, ``hyp_to_gds`` falls back from
  ``via_stack`` PCells to plain rectangle vias. The fallback is correct
  geometry, just less detailed, so this is the designed degradation. A
  found-but-broken PDK, for example one missing ``tkinter`` or ``psutil``,
  reports the cause on stderr and takes the same fallback rather than killing
  the export.
- **The ADK canonical layer table**, as used by gds2kicad's blackbox chiplet
  generator. Without the ADK it uses its built-in copy of the layer numbers and
  says so.

.. note::
    If you see a tool report a missing dependency, read which variable it names
    before setting anything. The message is generated from the same table
    documented above, so it always names the variable that would have resolved
    the lookup and the exact paths it examined.

``${VAR}`` references in path inputs
------------------------------------

Path inputs may reference the discovery variables with ``${VAR}`` syntax. This
is what makes a ``.chiplet`` file portable between machines whose checkouts sit
in different places.

It is accepted in:

- KiCad board text variables, for example ``INTERPOSER_LYP``.
- KiCad footprint fields, ``GDS_FILE`` and ``LYP_FILE``.
- ``hyp_to_gds`` command-line arguments.
- The ``.chiplet`` entries those flow into:
  ``technologies.*.layer_properties`` and ``components[].layout``.

.. code-block:: yaml

    technologies:
      intm4tm2:
        layer_properties: ${INTERPOSER_PDK_ROOT}/libs.tech/klayout/tech/intm4tm2.lyp
    components:
      - id: U1
        layout: ${GDS_TO_KICAD_ROOT}/gds_files/dies/my_die.gds

Writers copy these values **verbatim**. The KiCad C++ exporter and the Python
plugin writer stay byte-identical with zero emission logic, which is what lets
the byte-exact parity gate between them keep working. Readers, meaning
``hyp_to_gds``, the ADK's checks and Chiplet Studio, expand each reference on
read using the discovery chain: environment, then the sibling walk, then loud
failure naming the variable. There is no project text variable leg here, since
a reader may have no board in scope.

Everything else about path handling is unchanged: a path without ``${`` passes
through untouched, absolute paths stay absolute, and a relative path resolves
against the directory of the ``.chiplet`` file. Absolute paths remain the
default emission, because a ``.chiplet`` file is machine-local unless the board
data opts into the ``${VAR}`` form. If you receive a foreign ``.chiplet`` that
uses absolute paths, adjusting them is your job; if it uses ``${VAR}`` forms and
you have the checkouts, it resolves on your machine unchanged.

Two failure modes are both hard errors rather than warnings: an unknown or
unresolvable variable name, and a malformed reference such as an unterminated
``${``. Neither is allowed to survive into a path.

Setting the environment
-----------------------

In the container, nothing to do. Everything in the table is already set.

On a host, export the roots from your shell profile:

.. code-block:: bash

    export ADK_ROOT=$HOME/git/IHP-Open-ADK
    export INTERPOSER_PDK_ROOT=$HOME/git/OpenIntM4TM2
    export INTERCONNECT_PDK_ROOT=$HOME/git/IHP-Interconnect-IntM4TM2
    export GDS_TO_KICAD_ROOT=$HOME/git/gds2kicad
    export PDK_ROOT=$HOME/git/IHP-Open-PDK
    export KICAD_CHIPLET_PYTHON=$HOME/adk-venv/bin/python3

Launch KiCad from a shell that has these exported, so the plugin inherits them.
A desktop launcher started by the session manager does not see variables set in
an interactive shell profile.

Per project, use KiCad text variables instead. ``Board Setup > Text Variables``
accepts the same names, applies only to that board, and travels with the
project file, which is the right granularity when one design needs a different
ADK revision from the rest of your work.

.. tip::
    To find out which interpreter the plugin will actually use before running
    anything, open the export dialog: it displays the resolved worker path and
    the leg of the chain it came from.

See also
--------

- :doc:`/install/01_container` for the environment as the image sets it.
- :doc:`/install/02_host` for obtaining the checkouts these variables point at.
- :doc:`/formats/01_chiplet` for the file the ``${VAR}`` forms appear in.
