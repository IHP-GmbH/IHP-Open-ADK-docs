Quickstart
==========

.. include:: /common.inc

The shortest path from nothing to a checked assembly. Four commands, one of
which takes about an hour.

You need Docker with a running daemon, git, and network access to github.com
and gitlab.com. An X server is needed only for the graphical tools.
:doc:`/install/01_container` states the prerequisites in full.

1. Build the image
------------------

.. code-block:: bash

    git clone --recurse-submodules https://github.com/IHP-GmbH/ADK-Tools.git
    cd ADK-Tools
    ./build.sh

The submodules are the version lockfile, so a clone without them cannot build.
``build.sh`` compiles KiCad and KLayout from source, which is where the hour
goes, and refuses to tag the image unless the reference design regenerates end
to end and its assembly DRC passes.

2. Check the image
------------------

.. code-block:: bash

    ./run.sh adk-smoke

``adk-smoke`` exports the two-die reference design headless through the whole
pipeline and fails unless the assembly DRC passes. A green run prints
``adk-smoke: PASS (export + assembly DRC green)`` and leaves nothing behind.
That single line is the evidence that the toolchain works on your machine.

3. Look at the assembly
-----------------------

.. code-block:: bash

    ./run.sh chiplet-studio example/outputs/two_die_interposer.chiplet

``run.sh`` mounts ``~/adk-work`` on the host as ``/work`` inside the container
and seeds a disposable copy of the reference design at ``/work/example``. Open,
break and delete it freely: the next container start reseeds it.

The same design opens in the board tool with
``./run.sh kicad example/kicad/two_die_interposer.kicad_pro``.

4. Start your own design
------------------------

.. code-block:: bash

    ./run.sh adk-new-project my_design

This scaffolds ``/work/heterogenic-designs/my_design`` with the reference
design's directory layout, which is what the rest of the flow expects, and
prints the next three steps with absolute paths.

Where to go next
----------------

- :doc:`/flow/01_overview` for what the pipeline you just ran actually does.
- :doc:`/flow/08_reference_design` for a walk through the two-die design, file
  by file.
- :doc:`/intro/01_what_is_the_adk` if you want the problem before the tooling.
- :doc:`/install/01_container` for build options, graphics, the shared folder
  and the bundled commands.
- :doc:`/install/02_host` if you cannot use Docker. It is a best-effort route.
