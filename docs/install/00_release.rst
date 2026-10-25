The alpha release
=================

.. include:: /common.inc

The alpha release is three things that move together: an ADK-Tools commit, the
image built from it, and an adk-examples checkout whose ``release-lock.json``
names that image by its ID. ``run.sh --examples`` starts only the image the lock
names and checks the image's labels against it, so every example runs in the
image it was written for.

This page gets you that image and the host pieces the examples need. Each
example's README then starts from its first block, which calls ``run.sh``.
:doc:`/examples` lists the examples.

.. note::
    The release is alpha. :doc:`/examples` says what is not verified.

What you need
-------------

- **Docker**, with the daemon running and your user able to talk to it.
  The image carries every tool a run uses (OpenROAD, LibreLane and its Python,
  the SG13G2 PDK, the co-simulation engines and the waveform viewers), so the
  host needs only the pieces in this list.
- **git**, for the ADK-Tools clone, and **python3**, which reads the lock.
- **zstd**, which unpacks the image archive.
- **The release itself**: the adk-examples checkout, the image archive
  (``adk-tools-runtime-<12 hex>.tar.zst``) and the editor extension, with a
  ``SHA256SUMS`` beside them that covers the archive and the extension. None of
  them is in a public registry; they are handed out with the release, to
  workshop participants for instance.
- **A display** for the reviews the examples ask for. ``run.sh`` takes
  ``DISPLAY`` or a ThinLinc session; ``ADK_DISPLAY=:N`` names another.
- **Memory and cores.** Each example states what it needs before it starts a
  container and checks it in its first block.

1. The two checkouts
--------------------

Keep both outside your work directory (``ADK_WORK``, ``~/adk-work`` by default),
which the container can write. The adk-examples checkout is the release you
run; the ADK-Tools clone goes to the commit its lock names.

.. code-block:: bash

    export ADK_TOOLS_ROOT=~/adk-tools ADK_EXAMPLES_ROOT=~/adk-examples
    # the adk-examples checkout of the release is at $ADK_EXAMPLES_ROOT
    git clone https://github.com/IHP-GmbH/ADK-Tools.git "$ADK_TOOLS_ROOT"
    lock() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
               "$ADK_EXAMPLES_ROOT/release-lock.json" "$1"; }
    git -C "$ADK_TOOLS_ROOT" checkout "$(lock adk_tools)"

2. The image
------------

There are two routes to the image. The first runs the reference image, and is
the one to take unless you need to build.

**Load the release image.** Check the files that come with the release, then
load the archive. On Docker's classic image store ``docker load`` keeps the
image ID, so the loaded image is the one the lock names:

.. code-block:: bash

    # in the directory that holds the archive, the extension and SHA256SUMS
    sha256sum -c SHA256SUMS && zstd -dc adk-tools-runtime-<12 hex>.tar.zst | docker load
    export ADK_TOOLS_IMAGE="$(lock image)"
    docker image inspect --format '{{.Id}}' "$ADK_TOOLS_IMAGE"   # prints the same ID

On a Docker daemon that uses the containerd image store, a loaded archive is
not found by that ID; ``run.sh`` refuses and names the setting, and the
README of the two-ready-dies example (``two_die_echo_shifted_gf180``), section
Before you start, gives the steps.

**Or build it.** Building needs sources that are not public yet: the sibling
repositories at the commits the image pins, and the die records it names.
ADK-Tools' README, section Build, says what a build needs and how to hold the
image to a lock of your own; :doc:`/install/01_container` describes
``build.sh``.

3. Run an example
-----------------

Copy nothing by hand. Open the example's README in your adk-examples checkout
and paste its blocks in order, from the host block that starts the container.
``run.sh`` prints one line for each choice it made (the caps, the OpenROAD, the
display, the network and the release lock it held the image to), and stops
before a container starts when the lock names another image.

A die run recorded under another release's SG13G2 PDK does not resolve under
this one: its die checks and views refuse with a missing path. Rebuild the die
under this release.
