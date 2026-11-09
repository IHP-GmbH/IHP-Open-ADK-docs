Viewing and inspecting
======================

.. include:: /common.inc

Three viewers cover the assembly at three levels. Chiplet Studio shows the
assembly as a stack of physical bodies and lets you drill into any component's
real layout. KLayout shows the assembly GDS itself, with named and coloured
layers when the interposer technology is registered. The KLayout Marker Browser
walks a result database, either the violations from an assembly DRC run or the
chiplet boundaries rendered from the boundary manifest.

Opening the assembly in Chiplet Studio
---------------------------------------

The entry point is the ``.chiplet`` file, not a GDS:

.. code-block:: bash

    chiplet-studio outputs/two_die_interposer.chiplet

Launched with no argument the application opens an empty session and you load
the file from *File > Open*.

.. figure:: /_figures/screenshots/chiplet-inteposer-assembly-top-view-3d-and-2d.png
    :align: center
    :width: 100%
    :alt: Chiplet Studio showing the 3D assembly on the left and the 2D view in assembly mode on the right.

    Chiplet Studio: the 3D assembly view on the left, the 2D view in assembly
    mode on the right with its layer panel and cell hierarchy. The capture is of
    a simplified single-die demo, not of the two-die reference design.

How the file resolves its layouts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A ``.chiplet`` references layouts by path, and those paths are resolved against
the ``.chiplet`` file's own directory. In the reference design the interposer is
``layout/two_die_interposer_interposer.gds`` and each die is
``../chiplets/Metal_Test.gds``, so the whole project moves as one directory
tree with no absolute paths to fix up. Studio also picks up the assembly GDS
from that same ``layout/`` directory when it is present. Paths written as
``${INTERPOSER_PDK_ROOT}/...`` or ``${GDS_TO_KICAD_ROOT}/...`` are expanded on
read through the discovery chain; see :doc:`/install/03_environment`.

Inspecting the assembly
~~~~~~~~~~~~~~~~~~~~~~~

:doc:`/tools/04_chiplet_studio` is the reference for the docks, render modes and
toolbars. For a first look at an exported assembly:

1. Select a component in the **Hierarchy** dock or in the 3D view. The two stay
   in sync, and the **Properties** tab shows the component's geometry. Under
   each die, the hierarchy also shows the interconnect method that die uses.
2. Right-click a die and set its *Render Mode* to ``Detailed (with Si bulk)``
   or ``Detailed (no Si bulk)`` to see its routing and pads as bodies rather
   than as a box. Raise **Filter** to drop fill and small shapes from a
   detailed die.
3. Double-click a component to open its real layout in the **2D Layout** dock,
   and use **Back** to return to the assembly layout.
4. Open *View > Net Graph* to check the declared connectivity.

.. figure:: /_figures/screenshots/chiplet-inteposer-assembly-lateral-view.png
    :align: center
    :width: 100%
    :alt: Lateral view of a die mounted on Cu pillars above the interposer, with wire-bond pads and the traces fanning out to them.

    A lateral view: the die sits on its Cu pillars above the interposer body,
    with the wire-bond I/O pads and the traces fanning out to them at the
    interposer edge.

Opening the GDS in KLayout with named layers
---------------------------------------------

An assembly GDS opened in a plain KLayout session is a stack of numbered
layers. Registering the interposer technology gives every layer its name and
colour from the PDK layer table:

.. code-block:: bash

    klayout -n intm4tm2 outputs/layout/two_die_interposer_complete.gds

In the ADK-Tools image this works out of the box: ``KLAYOUT_PATH`` already
includes the interposer tree, so ``intm4tm2`` appears in KLayout's technology
selector and ``-n intm4tm2`` resolves. The registration is nothing more than
putting the directory that holds ``libs.tech/klayout/tech/intm4tm2.lyt`` and
``intm4tm2.lyp`` on the search path.

Outside the image, do the same by hand:

.. code-block:: bash

    export KLAYOUT_PATH=$HOME/.klayout:/path/to/OpenIntM4TM2/libs.tech/klayout
    klayout -n intm4tm2 two_die_interposer_complete.gds

.. note::
    Keep a writable directory as the *first* entry of ``KLAYOUT_PATH``. KLayout
    treats it as its configuration home and will not start cleanly if the first
    entry is read only. The image uses ``/tmp/.klayout`` for exactly this
    reason.

.. tip::
    Do not put the base SG13G2 PDK on ``KLAYOUT_PATH``; its PCell autorun macro
    pops error dialogs in a GUI session. The interposer tree ships its own autorun
    pymacro, which bootstraps the ``intm4tm2`` PCell library and is why the
    ADK-Tools image puts that tree on the path deliberately. ``hyp_to_gds``
    reaches the SG13G2 PCells through ``PDK_ROOT``, a different mechanism. See
    :doc:`/install/02_host`.

Walking DRC violations in the Marker Browser
---------------------------------------------

An assembly DRC run writes a KLayout result database. With ``--run_dir`` it
lands there as ``<layout-stem>_<topcell>_assembly.lyrdb``; the export pipeline
names it after the board, as in
``outputs/reports/two_die_interposer_assembly_drc.lyrdb``.

To inspect it:

1. Open the GDS the run checked, with the interposer technology.
2. *Tools > Marker Browser*.
3. Load the ``.lyrdb`` from the browser.

The browser lists one category per rule, using the rule identifier and its
message as they were rendered at run time, for example ``ASM.b : Min.
chiplet-to-chiplet spacing is 200.0 um`` or ``IXN.x.cupillar_opt1.vendorx_microbump
: Min. cross-method spacing ... is 40.0 um``. Selecting an item zooms the layout
to the offending geometry.

A category with no items is a rule that ran and found nothing, unless its
description reads ``<rule> : not applicable: <reason>``: that rule did not run,
as ``ASM.g`` on an interposer that declares no wire-bond pads. So the category
list is a record of *what was checked*; read it before concluding that a rule you
expected was actually evaluated. The reference design's committed report carries
fourteen rule categories and no items.

Viewing chiplet boundaries
--------------------------

Chiplet boundaries are not in the GDS; they travel in the
``<gds-stem>.boundaries.json`` manifest, so opening the assembly GDS shows the
dies' artwork but not the mechanical outlines the assembly rules actually check.
The ``boundaries_to_rdb`` macro closes that gap: it reads the same sidecar the
DRC runner injects and renders it as markers, so what you see is exactly what the
checker sees. Nothing is written into the GDS.

From the command line:

.. code-block:: bash

    python3 klayout/macros/boundaries_to_rdb.py \
        outputs/layout/two_die_interposer_complete.gds

.. include:: /_image_adk_scripts.inc

Pass the assembly GDS and the sidecar is auto-discovered next to it by the same
rule the runner uses; pass the manifest ``.json`` directly if it lives
elsewhere. The output is a ``.lyrdb`` next to the manifest, or wherever ``-o``
says. Load it in the Marker Browser exactly like a DRC report.

From the GUI, make the macro discoverable and use the menu entry:

.. code-block:: bash

    export ADK_ROOT=/path/to/IHP-Open-ADK
    export KLAYOUT_PATH=$HOME/.klayout:$ADK_ROOT/klayout:/path/to/OpenIntM4TM2/libs.tech/klayout

Then open an assembly GDS and run *Tools > Show chiplet boundaries (ADK boundary
manifest)*. One click builds the same database in memory and loads it into the
Marker Browser. Symlinking
``klayout/macros/show_boundaries.lym`` into ``~/.klayout/macros/`` works too.

The database has one ``chiplet_boundary`` category with a sub-category per
placed chiplet, named by its instance and described by its source die. Markers
are drawn from ``polygon_dbu``, the field the DRC treats as authoritative,
converted to microns using the manifest's own database unit, so they land on the
layout regardless of the layout's own resolution.

.. note::
    The viewer pins the manifest version it understands and refuses a sidecar
    that does not match, rather than rendering an older schema approximately.
    If it complains, regenerate the sidecar with a current ``hyp_to_gds``.

There is also a producer-side option, ``hyp_to_gds --annotate-boundaries``,
which paints the boundaries onto a viewer-only GDS layer. Prefer the marker
database: it needs no regeneration, adds no synthetic geometry to a layout you
may hand off, and cannot be mistaken for something a rule reads. See
:doc:`/flow/05_hyp_to_gds`.

Related pages
-------------

- :doc:`/tools/04_chiplet_studio` for the viewer itself.
- :doc:`/adk/05_run_drc` for producing the result database.
- :doc:`/formats/04_boundary_manifest` for what the manifest contains.
- :doc:`/flow/08_reference_design` for a worked example with real paths.
