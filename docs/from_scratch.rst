Design a system from scratch
============================

.. include:: /common.inc
.. include:: /_counts.inc
.. include:: /install/_release_tag.inc
.. include:: /_blocks/typical_01_two_die_minimal/values.inc
.. include:: /_blocks/typical_02_die_with_power/values.inc

.. warning::
    packaging-flow, interposer-pnr, assembly-lvs, chiplet-die-flow and the
    worked examples (adk-examples) are not public yet. This page follows
    those tools and that checkout, so a public reader can read it, but not
    yet run it.

.. Still typed by hand, to read again at each move of the adk-examples pin,
   because no block and no captured output states them: place exit 3 and
   run exit 1 and 10 (refusals the reference run does not take); verify's
   reason (g) (past the captured tail); the 20 and 15 um widths that do not
   route (the second application's sheet); and the four lanes, four outer
   pads and two rails of step 7. Also read again at each move: that the pin
   is the adk-examples commit of |release-tag|, and the paragraph at the end
   of step 2 on typical_03_from_schematic, against that example's page.

The quickstart leaves you with an image and a smoke test. This page takes you
from an empty folder to a checked assembly: two dies that do not exist yet,
placed on an interposer, routed, checked, and signed at four checkpoints. It
follows the typical application ``typical_01_two_die_minimal`` of adk-examples,
the smallest system this release runs from a pad plan to a verdict. The guide
follows adk-examples at commit |typical-01-examples-commit|, the one this site
pins: every shell block on this page is a block of that example's page, copied
from that commit, so what you read here is what the examples' checks run
against the release image; the page in the checkout is the one to paste from,
since it carries the STOP checks around each block and the result lines in
full.

Seven steps. Each says what you write, the command, what it produces, what to
look at, and the usual refusal with its fix. An eighth adds power.

.. figure:: /_figures/guide_overview.*
    :width: 100%

    From a die folder or a pad plan to the verdict: the files you write, the
    command at each step, and the four checkpoints where the run waits for you.

Before you start
----------------

You need the image of the preview release, |release-tag| (ADK-Tools
|typical-01-adk-tools|), built as :doc:`/install/00_release` sets up, and an
adk-examples checkout at commit |typical-01-examples-commit|, its
|release-tag| release, whose ``release-lock.json`` locks the same ADK-Tools
commit. The container does everything below. Its first block is run
from the host and starts the container with the example's caps,
|typical-01-cpus| CPUs and |typical-01-mem-gib| GiB, which this application
peaks under:

.. include:: /_blocks/typical_01_two_die_minimal/readme-1.inc

Inside, ``/work`` is your work directory on the host and ``/examples`` the
read-only checkout. One container at a time.

1. The dies
-----------

**You write** nothing for a die that exists. It enters the flow as a folder of
four files, as delivered: ``layout.gds``, the layout; ``pins.json``, the pin
list, which names each pad, its port and its net; ``die-contract.json``, which
binds the layout by its digest and names the process; and
``build-record.json``, which says who built it, against which PDK, and what
was checked. The die flow's ``emit-ready-die`` writes the four from a finished
build; a die from a partner arrives as the same four files, or is given them.

**Look at** the pin list, which is what the system file will name, and the
build record's status. A record that declares no DRC count or LVS verdict is
placed only under an admission (below); a record that declares them is read
at the dies' checkpoint.

**The usual refusal** comes at the run's ``admit:`` row: a layout whose digest
is not the contract's, or a port the system file names that the pin list does
not have. Both name the file and the name.

For a die you do not have yet, **you write** a frame spec: a short JSON with
the technology, the die size, how far in from the edge the pad centres sit,
and one row per pad with its name, side, position along that side, direction
and role. A pad's name is its port and its net. The two specs of the example
are in its ``inputs/frames/``.

**The command** is the die flow's ``pad-frame``, once per spec:

.. include:: /_blocks/typical_01_two_die_minimal/readme-2.inc

**It produces** a pad frame: the same four files as a die you have, with the
bond pads and the die area and nothing else, and a build record whose status
is ``pad-frame-not-a-circuit``. The frame stands in for the die until it is
designed, so the carrier can be designed first; when the die arrives, its pads
have to be where the frame's were.

**Look at** the pin line the block prints for each frame: the pads in the
order the pin list gives them. The two things the command is given by path,
the PDK tree and the pad master, come from the image, as the block names them.

**The usual refusal** is a ``PadFrameRefused:`` line that names what the spec
got wrong: two plates that overlap, a length off the technology's grid, a
supply pad that is not ``INOUT``, a repeated name, or a PDK tree whose version
cannot be stated. Fix the spec and paste the block again; a frame that was
written is kept.

Because a frame's record declares no check, the run places it only under an
admission: a small file, ``admission.json``, with the reason, the scope and
what is not verified, named on the die's row. The run records the role that
admitted it.

2. The system file
------------------

**You write** ``system.chiplet``; the block of step 3 copies the example's
instead, so the guide and the example run the same file. Here it is, as
shipped, with one comment per block:

.. include:: /_blocks/typical_01_two_die_minimal/system.inc

Top to bottom: the format version; the assembly's name and units; the carrier
technology's adapter; the carrier, with its technology and top cell; the dies,
each with its folder, its attachment method, its thickness and, for a frame,
its admission; the links, one carrier net per lane; the rails, the pads the
carrier ties into one net, with a voltage for the record; the external
interface, a profile that gives each pin that leaves the carrier a wire-bond
pad; and the flow block, with the routing technology, the attachment adapter
and the checks template that names the four checkpoints.

Leave open what you do not know yet. The file above states no carrier size,
no die position and no edge; ``unplaced`` lists the pins that leave the
carrier, and step 4 fills the rest. A bus of many lanes is one ``buses`` row
with a port pattern instead of one ``links`` row per lane; the format pages
under :doc:`/formats` have the full key list.

If you would rather draw the connections than type them, the third typical
application of adk-examples, ``typical_03_from_schematic``, starts the same
system on a KiCad sheet. ``chiplet_to_kicad_sch.py --handout`` writes a symbol
per die from its folder (:doc:`/tools/03_gds2kicad`). On the sheet you fill
each die symbol's attachment method and thickness, join the dies' pins with
global labels, draw the rails with the handout's power symbols and wire each
pin that leaves the carrier to an external pad symbol. ``packaging-flow edit
--sheet`` then reads the sheet into the system file: it writes the die rows'
method and thickness, the links, the rails with their volts and the pins on
no edge yet, and keeps the carrier technology, each die's admission, the
external profile, the routing technology and the checks template as the file
states them. From there the steps below are the same.

3. Read it before any run
-------------------------

**The command** is ``validate``:

.. include:: /_blocks/typical_01_two_die_minimal/readme-3a.inc

**It produces** the pre-run map and one line per finding: a note
(|typical-01-note-code|) is something the run would accept and tell you about;
a refusal (|typical-01-refusal-code|) is something the run would stop at. On
the file above it ends |typical-01-validate-summary| and
|typical-01-validate-expected|: the open values are the refusals, by design,
and the next step fills them. For the whole example |typical-01-placed-notes|
notes stay: the voltage on each rail is not checked, because a frame declares
no supply domain.

**Look at** every line that is not about an open value. A refusal that names a
port, a die path or a rail is a typo or a wrong file, and the line says which.

**The usual refusals** are a port the die's pin list does not have, a die
folder that is not where the row says, and a rail whose port is not a supply
pad on that die.

4. Let the engine place
-----------------------

**The command** is ``place``, then ``validate`` again:

.. include:: /_blocks/typical_01_two_die_minimal/readme-3b.inc

**It produces** the carrier size, each die's position and rotation, and the
edge of each external pin, written into the file with one printed reason per
number: the seed order, the cell each die takes, the margins (edge clearance,
pad, die keep-out), the size on the technology's grid, and for each pin the
side of the dies it sits nearest. The placement's own files are in
``edits/<UTC time>/`` beside the system file. The second ``validate`` reads
|typical-01-placed-summary|. Automated 2.5D place and route in the ADK is a
proof of concept, at alpha maturity: the placement written here and the route
the run draws in step 6 are a geometric draft that the run's checks and your
review at each checkpoint judge, not a layout ready for fabrication.

**Look at** the reasons, then the file. Every number has one.

**The usual refusal** is ``place exit=3``: no legal placement, with the rule it
could not meet, such as dies that do not fit a carrier size you stated. Widen
the carrier, or leave its size open. To place by hand instead, write ``size``,
``at``, ``rotation`` and the edges yourself and skip this step.

5. Run to the first checkpoint
------------------------------

**The command** is ``run``, with the tier and the role that admits the frames:

.. include:: /_blocks/typical_01_two_die_minimal/readme-4a.inc

**It produces** a run folder, ``runs/<UTC time>/``, and the first halt:
|typical-01-run-expected| with a ``GatePending`` line naming the first die's
checkpoint, where the run waits for you (:doc:`/tools/10_packaging_flow`).
Before it halts, the run admits each frame from its contract and its admission
and runs the PDK's DRC deck on each layout; the sheet under the halt line
reads the result per die.

**Look at** the sheet: for a frame, the deck ``PASS`` on pads and a die area,
and ``NOT_DECLARED`` for the record's own DRC and LVS, which is what the
admission covers.

**The usual refusals** are ``run exit=1`` right after the system file, the
flow refusing the composition, and ``run exit=10`` at an ``admit:`` row, the
flow refusing that die; each names what it read. A run is never edited: fix
the input and run again, and the run makes a new folder.

6. Look, accept or sign, resume
-------------------------------

Each checkpoint is the same three moves: open what the run made, answer the
checkpoint's questions at the terminal, resume. The dies first. Open each
frame's layout and pin list:

.. include:: /_blocks/typical_01_two_die_minimal/readme-4b.inc

A frame's checkpoint is accepted rather than signed, because nothing checked a
circuit: ``verify-accept`` prints the sheet, asks the two questions (the design
and revision you meant to place; each supply pin the domain you expect, at a
voltage you know), shows what the checkpoint leaves out, asks for a yes on its
key, your role and your name, then the reason and scope of your acceptance. It
reads your answers from the shell, so it ends its block; one per frame:

.. include:: /_blocks/typical_01_two_die_minimal/readme-4c.inc

.. include:: /_blocks/typical_01_two_die_minimal/readme-4d.inc

Then resume. The run places the frames, routes the carrier, exports the board
and the GDS, runs the interposer DRC, and halts at the interposer checkpoint:

.. include:: /_blocks/typical_01_two_die_minimal/readme-4e.inc

Open the board in KiCad and read the DRC margins, then sign. Look, and close
without saving: the signature binds the board's bytes, and the run reads the
board under its own folder, never the review copy.

.. include:: /_blocks/typical_01_two_die_minimal/readme-5a.inc

.. include:: /_blocks/typical_01_two_die_minimal/readme-5b.inc

The assembly, then the external interface, each one resume and one signature:

.. include:: /_blocks/typical_01_two_die_minimal/readme-6a.inc

.. include:: /_blocks/typical_01_two_die_minimal/readme-6b.inc

A signature is a review, not a qualification: it says you looked at what the
checkpoint names, and it signs off neither DRC nor LVS. Away from a terminal a
checkpoint is signed from an answers file instead, recorded as signed by a
script, as :doc:`/tools/10_packaging_flow` describes.
:doc:`/flow/06_verification_stages` says what each checkpoint reads.

7. Read the result, change, run again
-------------------------------------

**The command** is the last ``resume``, which writes the verdict, then the
readers:

.. include:: /_blocks/typical_01_two_die_minimal/readme-7.inc

**It produces** the map, one line per checkpoint and who signed it; the status,
one row per stage; ``verify``, the verdict in words with its reasons; the
review folder, ``runs/<UTC time>/review/``, with the run's files by checkpoint
and a list naming each file and its digest; and the counts: nets, endpoints,
findings, violations, copper.

**Look at** ``verify`` first. On this example it ends
|typical-01-verify-expected| by design: both dies
were admitted from contracts, and the all-dies-built-in-run verdict is a claim
about dies a run built from RTL; its one reason, (g), says so. Every check
that ran held. Then the counts, which follow from the system file: four
lanes, four outer pads, two rails; |typical-01-nets| nets, |typical-01-endpoints|
endpoints.

**To change** the system, edit ``system.chiplet`` in your copy, or paste step
3's block to start again from the shipped file, place it again with step 4,
and run step 5 again. A run is never edited and no stage runs alone: a change
is a new run in a new folder, and a checkpoint an earlier run of the same
bytes signed is reused. At this release the external interface checkpoint is
the exception: its check is keyed to files that name the run folder, so a
second run signs it again.

8. Power, when you need it
--------------------------

A rail may state more than a voltage. With ``amps`` and
``current_density_ma_per_um`` on its row, or ``width_um`` outright, the rail
carries a routing requirement: the width its copper must reach, the current
divided by the density. The run reads it before any die is built, in its rail
requirement check, which refuses a width the routing technology cannot draw,
and the route then draws the rail at that width and records, per rail,
whether the width was met.

**You write** two keys more on each rail that carries a known current:
``amps``, the current the rail carries, and ``current_density_ma_per_um``,
the current per micrometre of width the system allows the rail's copper,
its own figure and not one the technology declares. The
two go together on a power or ground rail; one without the other is refused
when the file is read. Neither die has to declare a current: the figure is
the system's statement, and the sheet of a system should say where it comes
from. The second typical application, a designed die and a pad frame with
two rails, states them this way under ``system:``, |typical-02-rail-width-um| um
each from |typical-02-rail-ma| mA at |typical-02-rail-density| mA/um:

.. include:: /_blocks/typical_02_die_with_power/rails.inc

**It produces** ``pnr/net_requirements.json`` in the run, one row per such
rail with the width it must reach, and the route's ``route.json`` says per
rail whether that width was met.

**Look at** the ``requirements`` row of ``status`` and the rail rows of the
route. The readout of the second typical application prints them last, one
line per rail: the route's word on its width, the width from the current and
the density, and the narrowest copper on each layer:

.. include:: /_blocks/typical_02_die_with_power/readme-7.inc

**The usual refusal** is a width above what the routing technology draws
without slits (|interposer-slit-free-width| um on the metals of IntM4TM2, rule
``Slt.c``): lower the current or raise the density. A second one comes from the route: a rail widened by its
requirement is drawn under a non-default rule, and the engine's own copper
spacing check refuses a route that leaves it closer to other copper than the
technology allows, naming the widened net and each gap; and a width below
that can still leave spacing violations inside the router, which the route
reports as its own. On the carrier of the second typical application 20 um
fails the copper spacing check, 15 um leaves two violations in the route,
and |typical-02-rail-width-um| um routes; its sheet states that limit. More
than |typical-02-rail-ma| mA per rail does not route on that carrier at this
release; a system whose rails need
more needs more room for them, or a supply mesh. Never state less current
than a rail needs.

A supply mesh, stripes on the top metals over the supply pads, is the step
after a wide rail: a second file beside the system file, ``pdn_mesh.json``,
in carrier coordinates, meant for the supply mesh check against the rails
and the requirement and for laying as reserved copper before the rest is
routed. At this release the mesh step is pending: the planner's mesh is not
one the supply stage draws, so the second typical application ships its
rails as wide nets and without a mesh, and says so on its sheet. The drop
along a rail and electromigration are not in this release.

Where to go next
----------------

- :doc:`/examples` for the worked examples, each with its page, its scripts and
  what it does not claim. The typical applications sit beside them in the
  same checkout, ``typical_01_two_die_minimal`` and
  ``typical_02_die_with_power``, each with its README and its sheet.
- :doc:`/tools/10_packaging_flow` for every command used above.
- :doc:`/tools/12_chiplet_flow` for the die flow: ``pad-frame``, and building a
  die from its RTL.
- :doc:`/flow/06_verification_stages` for the four checkpoints and what each
  one reads.

This is a preview release. No assembly here has been fabricated, and no verdict
is a sign-off for fabrication.
