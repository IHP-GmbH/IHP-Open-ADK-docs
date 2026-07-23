Analysis and automation
=======================

.. include:: /common.inc

.. warning::
   Nothing on this page is shipped. Each section is a reserved slot describing
   an intended axis of work. No interface is committed, and nothing here should
   be planned against.

The reserved domains on :doc:`/roadmap/01_adk_domains` are rule slots inside the
kit. The three directions below sit next to it instead: they are analysis and
automation capabilities that would consume the assembly the ADK describes rather
than add rules to the deck.

2.5D place and route
--------------------

Today the flow is interactive at the placement and routing step: a designer
positions chiplet footprints and routes the interposer in the layout tool, and
the ADK checks the result. See :doc:`/flow/03_interposer_design`.

The direction of work is to make that step assistable rather than purely manual.
Two pieces are relevant.

**Placement assistance.** The assembly placement rules already express what a
legal placement is. The same rules can drive a legaliser that detects
violations and proposes a corrected placement, rather than only reporting them
after the fact.

**Interposer routing.** Routing between dies on an interposer is a
redistribution-layer problem, which established open engines can address given
a description of the routing technology.

The design question that dominates both is where the coupling to a specific
process lives. The ADK solved the equivalent problem for rules with the adapter
contract: rules speak in abstract inputs, and one small file per PDK maps them
onto concrete layers. A place and route capability needs the same property, or
it becomes locked to one interposer and stops being reusable.

Extraction and signal integrity
-------------------------------

The shipped checks are geometric. They confirm that dies are placed legally and
that attachment structures respect the density their method allows. They say
nothing about what a signal experiences crossing the interposer.

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

The interconnect PDK already carries a three-dimensional stackup fragment per
attachment method, which exists precisely so that a pillar or bump has a body a
solver can mesh rather than only a two-dimensional footprint. See
:doc:`/tools/06_interconnect_pdk`.

There is no committed path from the ADK into a solver in this release, and no
interface for one is defined.

.. note::
   Any electromagnetic or thermal result from these two lines of work is
   numerically verified. This documentation does not describe simulation output
   as measured, and the distinction is not pedantic: a numerically verified
   result depends on the model, the mesh and the material data, and it is
   reported with those caveats.
