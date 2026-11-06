The alpha release
=================

.. include:: /common.inc

The alpha release is three things that move together: an ADK-Tools release
tag, the image you build from it, and an adk-examples checkout at the same tag.
No image is published: you build the one you run, and it gets an ID of its
own. The checkout's ``release-lock.json`` names the reference image the
examples were checked on and the pin set that image was built from.
``run.sh --examples`` holds your image to that pin set: an image built from
the same pins runs, with one note naming both IDs, and any other image is
refused before a container starts.

This page gets you that image and the host pieces the examples need. Each
example's README then starts from its first block, which calls ``run.sh``.
:doc:`/examples` lists the examples.

.. note::
    The release is alpha. :doc:`/examples` says what is not verified.

What you need
-------------

- **Docker**, with the daemon running and your user able to talk to it.
  The image carries every tool a run uses (OpenROAD, LibreLane and its Python,
  the SG13G2 PDK, the co-simulation engines and the waveform viewers), so
  running it needs only the pieces in this list.
- **Nix**, for the build. ``build.sh`` copies OpenROAD, LibreLane, the SG13G2
  PDK and the simulation engines and viewers from the host's Nix store into the
  image's own, so they have to be in that store before the build. Running the
  image you built needs no Nix.
- **git**, for the checkouts, and **python3**, which the build scripts use.
- **The sources the build stages.** Besides the ADK-Tools clone and its
  submodules, the build needs a checkout of each sibling repository that
  ADK-Tools' ``staging.pin`` lists, at the commit it pins, beside the clone.
- **The adk-examples checkout** at the release tag. Its ``die-views/`` folder
  holds the die records the build stages into the image, and its
  ``release-lock.json`` is the lock the examples run under.
- **A display** for the reviews the examples ask for. ``run.sh`` takes
  ``DISPLAY`` or a ThinLinc session; ``ADK_DISPLAY=:N`` names another.
- **Memory and cores.** Each example states what it needs before it starts a
  container and checks it in its first block.
- **Disk and time.** The first build takes about an hour, and later builds
  reuse its cache. :doc:`/install/01_container` says what the build does.

1. The checkouts
----------------

Keep both checkouts outside your work directory (``ADK_WORK``,
``~/adk-work`` by default), which the container can write: ``run.sh`` refuses
to start when ``ADK_WORK`` holds its clone or lies inside it. The adk-examples
checkout is the release you run, at the release tag ``v2026.11``; the
ADK-Tools clone is at the same tag. The sibling checkouts sit beside the
clone, or in the directory ``STAGE_SIBLINGS`` names.


.. code-block:: bash

    # the clone lives at ADK_TOOLS_ROOT, outside ADK_WORK; the
    # adk-examples checkout at ADK_EXAMPLES_ROOT is at the same v2026.11 tag
    export ADK_TOOLS_ROOT=~/adk-tools ADK_EXAMPLES_ROOT=~/adk-examples
    export STAGE_DIE_VIEWS_DIR="$ADK_EXAMPLES_ROOT/die-views"
    git clone --branch v2026.11 --recurse-submodules https://github.com/IHP-GmbH/ADK-Tools.git \
        "$ADK_TOOLS_ROOT"
    cd "$ADK_TOOLS_ROOT"
    ./stage-sources.sh --check && ./stage-die-views.sh --check

The two ``--check`` calls write nothing. ``stage-sources.sh --check`` finds
each sibling checkout and the commit ``staging.pin`` pins in it;
``stage-die-views.sh --check`` holds the records under ``STAGE_DIE_VIEWS_DIR``
to the listing ADK-Tools pins. Either one names what is missing in seconds,
before an hour of build.

2. The image
------------

Build it as :doc:`/install/01_container` describes, from ``nix build`` to
``./build.sh``, in the clone and with the same ``STAGE_DIE_VIEWS_DIR``. Then
read the ID of the image you built:


.. code-block:: bash

    export ADK_TOOLS_IMAGE="$(docker image inspect --format '{{.Id}}' adk-tools:dev)"

``run.sh`` takes the image only by that ID, ``sha256:<64 hex>``, and has no
default. A tag is refused, because a tag on a shared daemon can be moved to
another image between two runs.

3. Run an example
-----------------

Copy nothing by hand. Open the example's README in your adk-examples checkout
and paste its blocks in order, from the host block that starts the container.
That block calls ``run.sh --examples`` with your checkout, which ``run.sh``
mounts read-only at ``/examples``. ``run.sh`` prints one line for each choice
it made (the work directory, the image, the display, the caps and the release
lock it held the image to). Your build is not the reference image, so one of
those lines names both IDs:


.. code-block:: text

    run.sh: the image sha256:<your ID> is not the reference image sha256:<reference ID> the release lock <checkout>/release-lock.json names; it runs held to the lock's pin set

An image whose ``org.ihp.adk-tools.pin-set`` label, which ``build.sh`` writes,
is not the lock's pin set is refused with a line that names both values, and
no container starts.

A die run recorded under another release's SG13G2 PDK does not resolve under
this one: its die checks and views refuse with a missing path. Rebuild the die
under this release.

The release lock
----------------

``release-lock.json`` is one canonical JSON object, sorted keys, a two-space
indent and a final newline, with exactly these keys:

``adk_tools``
    The ADK-Tools commit the examples go with, the one to build.
``image``
    The reference image's ID, as ``docker image inspect --format '{{.Id}}'``
    prints it.
``image_manifest``
    Schema ``/2`` only: the ID Docker's containerd image store gives the
    reference image. An image you build is found by its own ID on either
    image store, so this key changes nothing for it.
``pin_set``
    The sha256 of ``ci/pin-set.json`` at that commit, the value ``build.sh``
    writes into the image's ``org.ihp.adk-tools.pin-set`` label.
``schema``
    ``adk-examples.release-lock/1``, or ``adk-examples.release-lock/2`` when
    ``image_manifest`` is there.

``run.sh`` refuses any other form, a schema that does not match the keys, and
a lock that names one ID as both ``image`` and ``image_manifest``. It does not
read ``adk_tools``: an image of the same pin set may come from another
ADK-Tools commit.

To hold the examples to a lock of your own, write it in this form and set
``ADK_EXAMPLES_LOCK`` to its path; each example's first block passes it to
``run.sh`` as ``--lock``. The adk-examples checkout's ``docs/RELEASE_LOCK.md``
says the same from the examples' side.
