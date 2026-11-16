A die from a partner's package
==============================

.. include:: /common.inc

This page takes a die whose layout stays with its owner from the owner's
package to a placed die in an assembly. You need the die flow
(:doc:`/tools/12_chiplet_flow`), packaging-flow
(:doc:`/tools/10_packaging_flow`) and KLayout from the ADK-Tools image
(:doc:`/install/01_container`), and the owner's package. Run every command
below in the container, in your design folder under ``/work``.

.. note::
   The commands of steps 1 to 5 were run in the ADK-Tools image, with the die
   flow, packaging-flow and chiplet-spec at the commits this release stages,
   and the outputs quoted are the ones produced. The run was fully routed,
   its assembly DRC found nothing and its assembly LVS read
   ``robust_match``. Its three gates were passed by the automated check that
   ran it, not by the review and acceptance a person gives, so that run is a
   record of what the flow does, not a signed run. The first signed run of
   this page will be a user's.

1. Receive the package
----------------------

The owner hands over one JSON file, the partner die package: the black-box pad
map at version 1.1 (:doc:`/formats/09_partner_die_package`). Put it in your
design folder.

To try the flow without a partner, save the placeholder package on that page
as ``example_partner_die.blackbox.json``. It describes a fictional
``owner-pdk`` die named ``example_partner_die``, 1500 by 1500 micrometres,
with five pads (``PAD_IN``, ``PAD_OUT``, two ``VDD`` pads as one port, and
``PAD_VSS``) and the supplies ``VDD`` at 1.8 V and ``VSS`` at 0 V.

.. important::
   Before anything runs, check that the package names no layer number, layer
   name or rule value of the owner's process. The flow carries every key of
   the package into its records, and nothing scrubs it.

2. Write the ready die
----------------------

.. code-block:: bash

    mkdir dies
    chiplet-die-flow emit-partner-die \
        --package example_partner_die.blackbox.json \
        --output dies/example_partner_die \
        --report report.json

The output folder must not exist yet and its parent must: with no ``dies/``
folder the command refuses with ``PartnerDieRefused: dies is not a directory``
and writes nothing. On success it writes four files into
``dies/example_partner_die/`` and prints their digests:

- ``layout.gds``, a pads-only layout, top cell ``example_partner_die``, drawn
  on the shared pad vocabulary (not on any layer of the owner's process), with
  no write date.
- ``pins.json``, the five pads with centre, size, net, direction and role.
- ``die-contract.json``, the die contract at version 1.2, with the supply
  domains and volts.
- ``build-record.json``, with status ``partner-declared``,
  ``qualified: false``, the owner's process ids, the package digest, the
  signoff and references carried verbatim, and the reader release the writer
  ran under.

``report.json`` holds the command, the package digest, the four output
digests, which pad vocabulary the generator read (``adk`` when the ADK tree is
reachable, else ``fallback``) and the refusal if there was one. Keep it with
the design: it is the record of what was derived from which package.

Run the same command twice on the same package and the four files are
byte-identical under the image's KLayout. Under another KLayout release, see
:ref:`release_known_issues`.

3. Give the die's technology an attachment method
-------------------------------------------------

The shipped interconnect registry lists which die processes each attachment
method attaches (:doc:`/tools/06_interconnect_pdk`), and the owner's
technology is not among them. Copy the registry into your design folder as
``registry/`` and add one method row that lists the technology id the package
states under ``process.technology``, here ``owner-tech``: for example a copy
of ``cupillar_opt1`` under the new id ``owner_tech_pillar``, with
``"die_processes": ["owner-tech"]``. The system file points at that copy with
the ``registry:`` key.

Copy the whole tree, not only ``manifest/``; in the container it is
``/opt/adk-tools/IHP-Interconnect-IntM4TM2``. The export imports code from the
registry root (``bump3d_generator.py``) and refuses to fall back to another
tree, so a manifest-only copy fails the ``gds`` stage as
``DrcReportUnreadable``. packaging-flow also ships a recorded form of this
step, ``examples/mixed_gf180/copy_registry.py <checkout> <commit>
<die-contract> <out> --die-words "..."``: it writes a subset copy with the row
added, under the method id ``<technology>_flow_demo_pillar``, at
``<out>/interconnect_pdk``.

The flow refuses, before anything is built, a die whose technology the method
does not list (``DieProcessRefused``). Which pillar or bump the owner's die
can really take is the owner's and the assembly house's statement, not the
flow's; the row you add records your choice.

4. Write the admission and the system file
------------------------------------------

The die was built elsewhere, so it is placed under an admission statement.
Save it as ``admission.json``, with three keys:

.. code-block:: json

    {
      "reason": "a die of a process this flow has no tables for, handed over as a partner package",
      "scope": "placement, routing and composition of this assembly; no fabrication, electrical or functional statement about the die",
      "not_verified": ["die DRC", "die LVS", "die timing", "pad finish and solderability"]
    }

The system file names the die folder, the method and the admission on the
die's row. The ``admission`` key needs format 1.4. Save it as
``system.chiplet``:

.. code-block:: yaml

    format_version: "1.4"
    _metadata:
      finalize_required: true
      finalizer: "packaging-flow run"
    assembly:
      name: partner_die_alone
      description: "a partner die from its package on a plain IntM4TM2 carrier"
      units: um
    interposer:
      adapter: intm4tm2
    system:
      carrier: {technology: intm4tm2, top_cell: CF_CARRIER, size: [3000, 3000]}
      registry: registry
      dies:
        - {id: U1, die: dies/example_partner_die, at: [1500, 1500], rotation: 0,
           method: owner_tech_pillar, thickness: 250, admission: admission.json}
      rails:
        - {name: VDD, class: power, volts: 1.8, ports: [U1.VDD]}
        - {name: VSS, class: ground, ports: [U1.PAD_VSS]}
      alone:
        - U1.PAD_IN
        - U1.PAD_OUT
    flow:
      packaging_flow:
        route: {tech: ihp_sg13g2_intm4tm2_rdl2, interconnect_adapter: ihp_cupillar}
        checks: {template: signoff}

Ports are named as the package names them: the two ``VDD`` pads are one port
``VDD``, and the others keep their pad name. Check the file before running:

.. code-block:: bash

    packaging-flow validate system.chiplet

It prints the line below and writes the pre-run map beside the file:

.. code-block:: text

    [INFO PFL-0211] system.chiplet read: 0 refusing, 0 note(s), 0 port(s) unaccounted; pre-run map: .packaging-flow/map.json.

5. Run and read the result
--------------------------

.. code-block:: bash

    packaging-flow run system.chiplet --admitted-by reviewer

``--admitted-by`` names the role that admits the die, never a person, and is
required when a die row carries an admission. The run makes ``runs/<stamp>/``
beside the file. It runs ``spec``, ``elaborate``, ``admit:U1`` and
``cosim-select``, then halts at the die gate with exit 2; nothing is routed
before the die is accepted:

.. code-block:: text

    GatePending: halt:die: gate die:U1 is unsigned ...
    [INFO PFL-0213] U1 needs an acceptance and is signable with it: packaging-flow verify-accept <run> --gate die:U1
    [INFO PFL-0217] Interposer: not run yet; the run stopped at U1.

The admit stage takes the die from its four files at their digests. The die's
own layout is never composed into the assembly: the run writes an abstract,
the outline and the pad openings in a layer window of its own, and routes,
exports and checks against that (:ref:`packaging_flow_black_box`).

A person accepts the die, after looking at it. ``verify-open`` opens the
derived layout in KLayout with the pad sheet:

.. code-block:: bash

    packaging-flow verify-open runs/<stamp> layout die.layout:U1
    packaging-flow verify-accept runs/<stamp> --gate die:U1
    packaging-flow resume runs/<stamp>

The acceptance is given at the terminal or on the review form. An answers
file on the script channel is refused ("an acceptance is a person's decision,
filed with a review only, form or terminal; nothing was signed"), and
``verify-sign`` never signs the die gate instead.

``resume`` runs ``place-check``, ``bumps``, ``route``, ``export``, ``report``,
``schematic``, ``signoff-check``, ``gds`` and ``interposer-drc``, then halts at
the interposer gate, exit 2. Review the board (placement, routing, margins),
sign it with ``verify-sign runs/<stamp> --gate interposer`` and resume again.
The run then runs ``drc`` and ``assembly-lvs`` and halts at the assembly gate;
sign it with ``verify-sign runs/<stamp> --gate assembly`` and resume once
more. The last resume prints ``resumed <run id> to verdict`` and exits 0, and
``packaging-flow status runs/<stamp>`` shows every stage ok, the gates acked
and the state completed. A run that composes the assembly runs its assembly
LVS, so the ``assembly-lvs`` engine must be on ``PATH``, as it is in the image,
or named by ``--assembly-lvs-executable``; without it the run refuses at start
with ``ToolRootUnresolved``.

The run completes, but it never reads as verified: a placed die this run did
not build keeps it from that, whatever its checks say. ``verify`` takes the
run's manifest:

.. code-block:: bash

    packaging-flow verify runs/<stamp>/run/manifest.json

It ends with ``verify: not every die was built in this run (tier full; built
none; admitted U1)`` and one reason, ``(g) 1 of 1 placed dies were admitted
from contracts, not built by this run: U1; ...``, and exits 1. Run while the
run is still halted, it prints ``verify: FAILED (tier full; built none;
admitted U1)``, with ``die U1 internals: unverified; admitted`` among the
reasons.

What the run says about the die is exactly what the package said, recorded;
the owner's signoff is carried and never judged. A second run of the same
package reads the die gate as ``reused: Signed in run <first stamp>`` and does
not ask for the acceptance again: the acceptance is keyed on the die's
digests.
