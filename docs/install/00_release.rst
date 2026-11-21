The preview release
===================

.. include:: /common.inc
.. include:: /install/_release_tag.inc
.. include:: /_blocks/typical_01_two_die_minimal/values.inc

.. warning::
    packaging-flow, interposer-pnr, assembly-lvs, chiplet-die-flow,
    chiplet-cosim and the worked examples (adk-examples) are not public
    yet. The image build stages the first five and reads die records from
    the examples, so a public reader cannot build the full image until
    they are.

The preview release is three things that move together: an ADK-Tools release
tag, the image you build from it, and an adk-examples checkout.
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
    The release is a preview. :doc:`/examples` says what is not verified.

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
  ADK-Tools' ``staging.pin`` lists, holding the commit it pins and any extra
  commit it names for that tree, beside the clone.
- **The adk-examples checkout.** Its ``die-views/`` folder holds the die
  records the build stages into the image. Its ``release-lock.json`` is the
  lock the examples run under.
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
to start when ``ADK_WORK`` holds its clone or lies inside it. The ADK-Tools
clone is at the release tag |release-tag|. The die records in the adk-examples
checkout's ``die-views/`` folder have to match ADK-Tools' ``die-views.sha256``
at that tag. The sibling checkouts sit beside the
clone, or in the directory ``STAGE_SIBLINGS`` names.

.. literalinclude:: /install/_recipe/clone.sh
    :language: bash

The two ``--check`` calls write nothing. ``stage-sources.sh --check`` finds
each sibling checkout and the commit ``staging.pin`` pins in it;
``stage-die-views.sh --check`` holds the records under ``STAGE_DIE_VIEWS_DIR``
to the listing ADK-Tools pins; when they do not match, update the adk-examples
checkout until they do. Either one names what is missing in seconds, before an
hour of build.

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
this one: its die checks and views refuse it. Rebuild the die under this
release.

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

What this release changes
-------------------------

A run composes its layout from the routed geometry. interposer-pnr's new
``routed-geometry`` command writes every net's wires and vias, the placed dies
and the carrier's metal stack into one document, and the ``gds`` row composes
the interposer and assembly GDS from it when the signoff check reads the board
as drawn. A board a person edited after the run sent it is composed from the
board. The run no longer writes or checks a HyperLynx ``.hyp`` file
(:doc:`/tools/10_packaging_flow`).

These change what a run that passed before may do now:

- The run stops at the ``gds`` row when the metal fill cannot meet a metal's
  density rule. It names each metal and its coverage, says what usually causes
  it, and no signature waives it. Before, a fill that did not close did not
  stop the run.
- ``interposer-pnr route`` fails (exit 3) on any gap between two nets below
  the layer's spacing rule, on both routing backends. Before, such a gap failed
  only under a non-default width rule on the multi-layer backend, and never on
  one routing layer (:doc:`/tools/11_interposer_pnr`).
- At signing, a signature record that does not read is refused first,
  whatever gate you name. When a die gate the run recorded as signed has no
  record filed under its key, every gate of the run is refused, not only that
  die's.
- A technology package with no KiCad view passes its set B check with the note
  ``PACKAGE_NO_KICAD_VIEW``. Every run writes a KiCad board, so a run on such
  a technology stops where the board is written
  (:doc:`/formats/01_chiplet`). Before, such a package failed set B.

New commands: ``packaging-flow edit <file.chiplet> --move ID=X,Y[,ROT]`` sets a
placed die's position and turn, checked as ``place`` checks a file;
``packaging-flow gds-xor`` says whether two layouts draw the same geometry.
A run now draws the connection sheet of the assembly as a picture, in a row
of its own after the schematic. Open it in a web browser, or in any program
that shows SVG pictures; ``verify-open <run> connection_sheet
assembly.connection_sheet`` prints its path. Where a review is not part of a
run because a row was skipped, the reason names the ``connection-sheet`` row
when it is the one skipped.

Chiplet Studio draws a component whose file names no layout where its anchor
puts it, in both axes; before, such a box sat half its own height off
(:doc:`/tools/04_chiplet_studio`).

Signatures given under this release are of version 1. The next release signs
at version 2 and asks for each gate's signature again, once. The connection
sheet is drawn and shown in this release, not signed; the assembly signature
binds the review schematic.

The run map in VS Code shows the connection sheet from the release whose
review offers it; in this release no review item offers it.

Some code in the engines is present but not in use in this release, and
nothing here describes it as usable: the version 2 signature tables, and the
review of a routed layout in place of the board (the ``interposer.routed``
result and the acknowledgment that would sign it).

.. _release_known_issues:

Known issues
------------

These are known in |release-tag| and are being fixed.

A die with ``sbump_sac305`` exports without its interposer landings
    A die whose ``CONNECTION`` field
    (:doc:`/flow/03_interposer_design`) names ``sbump_sac305`` exports
    without its interposer landings. The export still succeeds, and the only
    sign is a warning from the export worker, so read the export log before
    you take such a design further. Stand-alone solder bumps do not run end
    to end in this release; the Cu pillar methods ``cupillar_opt1`` to
    ``cupillar_opt3`` do. The next release is planned to either refuse such
    a die or draw its landings.

A LibreLane Classic flow run in the image fails at ``Magic.StreamOut``
    The image's Magic is 8.3.610, from LibreLane's Nix closure, and the PDK's
    Magic techfiles require 8.3.617 (ihp-sg13g2) and 8.3.657
    (ihp-sg13cmos5l). Build dies with chiplet-die-flow's Chiplet flow
    (``meta.flow: Chiplet``, :doc:`/tools/12_chiplet_flow`), which runs no
    Magic step.

A partner die regenerates byte-equal under KLayout 0.30.5 and 0.30.6 only
    The pads-only layout ``emit-partner-die`` writes is byte-identical across
    runs under those two KLayout releases. Under another release the layout
    can differ in bytes while every cell, layer and shape is the same. Compare
    structure, not bytes, when the KLayout release differs.

A partner die's build record names the reader release it was written with
    A newer die flow or ``.chiplet`` reader release does not re-admit an older
    folder silently. Re-run ``emit-partner-die`` on the same package and
    replace the four files, and their recorded digests, when the reader
    release moves.

A partner die's signoff is recorded, never checked
    The flow carries the owner's signoff statement verbatim into the build
    record and the run's evidence. It does not verify the checks it names, and
    the layout digest in it is never compared with the derived layout. A run
    that places such a die is never read as verified ("not every die was built
    in this run"), and its die gate needs a person's acceptance.

A stopped ``escape-capacity`` stage can leave a defunct OpenROAD process
    ``run.sh`` starts the container without an init process, so the command
    you give it becomes the container's first process. When that command is
    ``interposer-pnr escape-capacity`` itself, each stage stopped at its
    ``--timeout`` or by an interrupt takes about 5 s longer to stop, and the
    stopped OpenROAD can stay listed as defunct until the container exits.
    Results are not affected: the stage is recorded as stopped either way. Run
    the command from a shell in the container (``run.sh`` with no command, or
    ``run.sh bash < script.sh``), where neither happens.

Only a ``no_connect`` pad listed under ``open`` gets through assembly LVS
    A pad of role ``no_connect`` listed under the system file's ``open`` block
    is carried through assembly LVS. A port of any other role listed under
    ``open`` stops the run at assembly LVS (``AssemblyLvsInvalid``), after the
    die and interposer gates. That covers a spare signal pad, and a pin that
    ``gds2kicad --classic`` writes as ``open`` from a no-connect flag when
    its pad has another role.

    A signal pin has a way round it: after the last sheet read, move it by
    hand in the system file from ``open`` to ``alone``. The file then
    validates and the run carries the pin as a net with one connection. The
    next ``packaging-flow edit --sheet`` writes it back under ``open``, so
    redo the move after each sheet read. A power or ground pin has no such
    way round in this release.

    A pad of role ``no_connect`` that the system file wires to another pad or
    to a carrier pad is refused, but only when the run builds its assembly
    LVS inputs, after the die and interposer gates. List such a pad under
    ``open`` and nowhere else.
