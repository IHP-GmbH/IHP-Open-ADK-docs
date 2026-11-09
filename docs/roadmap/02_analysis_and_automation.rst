Analysis and automation
=======================

.. include:: /common.inc

.. warning::
   Apart from the place and route proof of concept that the first section
   names, nothing on this page is shipped. Each section describes an intended
   axis of work. No interface is committed for it, and nothing here should be
   planned against.

The reserved domains on :doc:`/roadmap/01_adk_domains` are rule slots inside the
kit. The three directions below sit next to it instead: they are analysis and
automation capabilities that would consume the assembly the ADK describes rather
than add rules to the deck.

2.5D place and route
--------------------

In this release the placement and routing step can be run by tools, as a proof
of concept. ``interposer-pnr`` (:doc:`/tools/11_interposer_pnr`) places the
dies a source leaves open and legalises them against the assembly rules, puts
a bump on every die pad, routes the interposer with OpenROAD, and writes the
copper as a draft on a KiCad board. ``packaging-flow``
(:doc:`/tools/10_packaging_flow`) runs those steps in order and halts for a
person to review and sign the board. What they write is a geometric draft, not
a sign-off. The interactive path stays: you can still position the footprints
and route the interposer in KiCad yourself, as
:doc:`/flow/03_interposer_design` describes, and the ADK checks either result
the same way.

The design question that dominated both pieces was where the coupling to a
specific process lives. The ADK solved the equivalent problem for rules with the
adapter contract: rules speak in abstract inputs, and one small file per PDK
maps them onto concrete layers. interposer-pnr follows the same pattern. It
reads no PDK kit files; one routing-technology descriptor per interposer maps
the engine onto concrete layers, and a synthetic descriptor with no fab behind
it ships beside the IHP ones to show the schema is not shaped around one PDK.

The direction of work from here:

- **Routing that closes.** On one routing layer a dense design can stay partly
  open. On one assembly a second layer closed every net the first left open,
  and the engine reports what stays open rather than hiding it.
- **Impedance-aware routing.** Routing today is geometric. Routing to a target
  impedance needs the constraint contract described in the next section.
- **Congestion by layer.** The route report states routed length; it does not
  yet report overflow per routing layer.
- **Placement.** Legalisation runs only inside the placer, with no command of
  its own, and the placer seeds every die on one grid, so dies of very different
  sizes sit further apart than they need to.

Extraction and signal integrity
-------------------------------

The shipped checks are geometric and connective. The assembly rules confirm
that dies are placed legally and that attachment structures respect the density
their method allows, and ``assembly-lvs`` checks the extracted connectivity of
the placed assembly against its declared nets (:doc:`/tools/09_assembly_lvs`).
None of them says what a signal experiences crossing the interposer.

Two levels are in scope, and they are worth separating because the first is
largely a reuse problem and the second is not.

**Interposer parasitic extraction.** Extracting resistance and capacitance for
interposer nets is close to a solved problem in open tooling: it needs a process
description and an extraction engine, both of which exist. The work is in
binding the interposer technology to an extractor rather than in inventing a
method.

**Multi-die signal integrity.** This is the harder half. A die-to-die link
crosses two attachment transitions and a length of interposer routing, and the
interesting effects, including coupling between adjacent links and discontinuity
at the attachment, are properties of the assembly rather than of any single
die's netlist. The direction of work is a constraint contract that lets a design
declare what a link needs, a fast impedance estimation tier that can answer
during routing, and a slower field-solver tier for verification.

Multiphysics analysis
---------------------

Electromagnetic and thermal behaviour of an assembly is a research direction
alongside the ADK rather than a part of it. The relationship to the shipped kit
is one of inputs: a simulation needs a meshed geometry with materials, and the
assembly artefacts this flow already produces are a reasonable starting point
for building one.

:doc:`/tools/08_multiphysics` describes the method behind the published
reference results.

The interconnect PDK already carries a three-dimensional stackup fragment per
attachment method, which Chiplet Studio (:doc:`/tools/04_chiplet_studio`) uses
to render each pillar or bump at its elevation. The same z data is a starting point for a solver geometry. See
:doc:`/tools/06_interconnect_pdk`.

There is no committed path from the ADK into a solver in this release, and no
interface for one is defined.

.. note::
   Any electromagnetic or thermal result from these two lines of work is
   numerically verified. This documentation does not describe simulation output
   as measured, and the distinction is not pedantic: a numerically verified
   result depends on the model, the mesh and the material data, and it is
   reported with those caveats.
