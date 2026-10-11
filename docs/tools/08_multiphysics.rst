Multiphysics (EM and thermal)
=============================

.. include:: /common.inc

This page describes how an assembly built with the ADK is turned into one
multi-material model for electromagnetic (EM) and thermal simulation, when its
dies come from different technologies. It documents the method behind the
results of :footcite:`montanares2026multiphysics`.

.. warning::
   This page is a placeholder. The workflow it describes is research alongside
   the ADK, not part of the |current-status| and not part of the ADK-Tools
   image. The model files and data behind the reference results will be
   published from this page; until a link appears in `Data and model files`_,
   nothing described here is downloadable. The EM results are numerically
   verified; the reference also compares the thermal model with infrared
   thermography of a fabricated interposer test chip. The model, mesh and
   material caveats are stated in the reference.

The process
-----------

The workflow has three inputs and two solvers.

* **The assembly description.** The ADK's ``.chiplet`` file
  (:doc:`/formats/01_chiplet`) already carries what a 3D model needs from the
  assembly: each component's technology, lateral position and footprint,
  thickness, orientation (face up or flip chip), the height of the interposer
  surface it attaches to, and the connection stack (for example Cu pillar plus
  SnAg cap) between the two.
* **One stackup per technology.** The ordered list of material layers of each
  process with their heights, holding electrical properties (permittivity,
  conductivity, loss tangent) and thermal properties (conductivity, density,
  heat capacity) side by side. For SG13G2 and the interposer the thermal
  stackup is the gds2palace EM stackup with the thermal fields added, so both
  solvers see identical layer data. SKY130 and GF180MCU publish no thermal data:
  their EM stackup is an XML file and the composer reads a table, both with layer
  heights and metal conductivities from the open PDK technology file and every
  other value from labelled literature data.
* **Layout.** GDS geometry for the structures that need lateral detail, such as
  a die-to-die link or a heater.

From these, the technologies are composed into one stack in a single assembly
coordinate frame (next section). The composed stack drives a steady-state
thermal model in Elmer FEM, meshed with Gmsh. EM structures are solved in Palace
through gds2palace from per-technology EM stackups with the same layer data. Coupling is one way:
the dissipation from an EM or electrical solve enters the thermal model as a
heat source, and temperature does not yet feed back into the EM material data.

Per-technology stackups
~~~~~~~~~~~~~~~~~~~~~~~

Every layer in a composed model keeps a tag saying where its numbers came from,
because a composed model is only as credible as its weakest layer.

.. list-table::
    :header-rows: 1
    :widths: 22 39 39

    * - Technology
      - Heights and metal data
      - Dielectric and thermal data
    * - IntM4TM2 interposer
      - Metal4 to TopMetal2 cut of the SG13G2 foundry stackup; the interposer
        PDK ships its own Palace and openEMS stackups, see
        :doc:`/tools/05_openintm4tm2`
      - Foundry stackup values; thermal conductivities from the IHP thermal
        data, density and heat capacity from literature
    * - IHP SG13G2
      - The SG13G2 stackup distributed with gds2palace
      - As for the interposer
    * - SKY130
      - Layer heights and metal conductivities from the open PDK technology
        file
      - Literature values, tagged as such
    * - GF180MCU
      - Layer heights from the open PDK technology file; top-metal
        conductivity is an effective value, tagged as such
      - Literature values, tagged as such
    * - Connection stacks
      - Heights from the ``.chiplet`` connection stack
      - Literature values for Cu, SnAg and underfill

Composing technologies by hand
------------------------------

The EM decks of the multi-die structures in the reference were composed by
hand. The steps below are that procedure. They need nothing beyond a text
editor, the per-technology XML stackups and gds2palace, and they are the part
that automation is meant to replace (see `Future: automated composition`_).

The constraint that shapes the procedure is that a stackup file in the format
used here (gds2palace ``schemaVersion="2.0"``) has one global offset, ``<Substrate Offset>``, which shifts every layer by the same
amount. It cannot place two dies at two heights, so each die's layers are
rewritten into the assembly frame explicitly.

1. **Choose one datum.** Use the top surface of the interposer silicon as
   z = 0. Interposer layers keep their heights from the interposer stackup.
2. **Add the connection stack.** Above each landing pad, add the pillar and
   solder layers with the heights from the ``.chiplet`` connection stack. Their
   top is the attach height ``z_attach`` of that die.
3. **Flip each die into the frame.** For a flip-chip die, the top of its back
   end faces down and sits on ``z_attach``. With ``z_ref`` the die's top
   reference plane in its own stackup and ``z_local`` a layer height in that
   stackup, the layer lands at

   .. code-block:: text

       z_asm = z_attach + (z_ref - z_local)

   so the die's top metal sits lowest and its substrate highest. A face-up die
   is a plain translation, ``z_asm = z_attach + z_local``.
4. **Keep names and numbers unique.** Give every die its own range of layer
   numbers and its own name prefix (the reference decks add 1000 for the first
   die and 2000 for the second), so that two dies from the same or different
   technologies never share a layer.
5. **Merge the dielectrics.** Order all dielectric layers by height into one
   stack and check that each component's envelope is filled with no gap and no
   overlap. The bulk silicon of a die can be left out of an EM model of a
   structure far from it; it must stay in a thermal model, where it is the main
   heat path.
6. **Tag every layer** with its component, technology and data source.

.. note::
   The reference decks offset the two dies' pillars by 0.5 um so that no two
   layers of different dies share a height. Current gds2palace scopes these
   checks per chiplet for stackups written with reference-relative positioning
   (schema 3.0); the reference decks use absolute heights, and whether the
   offset is still needed after a conversion has not been tested.

Thermal and EM runs
-------------------

**Thermal.** The composed stack is meshed with Gmsh and solved in steady state
with Elmer FEM. A die's power is applied uniformly in its silicon, a thin-film
heater as a thin volume at its footprint, and the dissipation from an EM solve as
a surface source on the conductor surfaces. The backside sees the chuck or
package boundary condition. In the reference assemblies the
die-to-interposer standoff is modelled as homogeneous
underfill without individual pillars, and each die's back end as one oxide
plate. Lateral geometry is at footprint level except where GDS is imported.

**EM.** Each structure is solved in Palace through gds2palace from its
(hand-composed) stackup, with fixtures de-embedded where stated. A die-to-die
link therefore crosses three stackups: the guest die, the interposer, and the
host die.

What the reference results used
-------------------------------

* **Composer, thermal drivers and coupling.** In-house scripts, not yet public.
  They build the composed thermal model and solve it with Elmer FEM; they do not
  use the Elmer path of gds2palace or any of the tools under
  `Future: automated composition`_.
* **Stackup format.** gds2palace ``schemaVersion="2.0"`` files, with
  ``ThermalConductivity``, ``Density`` and ``HeatCapacity`` added per material
  for SG13G2 and the interposer, and tables for SKY130 and GF180MCU.
* **gds2palace.** A development copy based on the upstream state of
  27 March 2026 (commit ``bb95742``), with local fixes to material lookup,
  boundary-surface handling and mesh clean-up that are not in the upstream
  repository.
* **Multi-die EM decks.** Composed by hand as described above, one global offset
  per file.

Data and model files
--------------------

To be published here: the assembly descriptions, the per-technology and
composed stackups with their data-source tags, the solver input files, the
software versions and the result data behind the reference. This section will
link to their location.

Future: automated composition
-----------------------------

This section describes a direction. None of it was used for the reference
results, and none of it is part of the current release.

Public tools by Volker Muehlhaus
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The stackup format and its tools have since grown in the same direction. As of
gds2palace ``main`` at ``a2ac184`` (10 October 2026), setupEM ``main`` at
``45d0b7d`` (7 October 2026) and chiplet_xml_composer ``master`` at ``ac0f6e1``
(18 September 2026):

* **Stackup schema 3.0 and 3.1** (gds2palace, August 2026). Reference-relative
  positioning (a layer placed relative to an edge of another named layer),
  derived layers, thermal property tables, and variables and expressions.
* **Multi-chiplet stackups** (gds2palace, September 2026). Detection of chiplet
  groups that branch from one shared interposer in a stackup written with
  reference-relative positioning, with height checks scoped per chiplet and
  checks for missing boundaries.
* **Thermal model generation** (gds2palace, August to October 2026). An Elmer
  thermal model generated from the same stackup and layout, with
  temperature-dependent conductivity, a fill-factor correction and
  perfect-conductor handling.
* **setupEM.** setupThermal as the GUI for the thermal path, a stackup editor,
  and a topology overview that shows chiplet stacks branching from the
  interposer (September 2026).
* **chiplet_xml_composer** (GPL-3.0). A command-line tool that combines the
  per-technology gds2palace stackups of an assembly into one stackup file,
  driven by an ADK ``.chiplet`` file, its interconnect methods and a file of
  connection-material properties. Its documentation scopes the first version to
  the vertical stack for EM simulation, lists lateral position, rotation,
  die-on-die stacking and the substrate as not yet handled, and shows examples
  with IHP stacks.

What has been tested with our files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Only parsing: the gds2palace stackup reader of 13 September 2026 (``30f15d4``)
reads the schema 2.0 files above, including their thermal conductivity and
density. We have not run chiplet_xml_composer, the gds2palace Elmer path, the
schema 3.x features, the chiplet groups or the setupEM topology view with these
technologies, and none of the reference results has been reproduced through
them.

Direction
~~~~~~~~~

chiplet_xml_composer automates, for the EM stack, the hand steps above. The next
step is to evaluate it on the three-technology assembly of the reference,
including the SKY130 and GF180MCU stacks it has not yet been shown with, and to
compare its combined stackup and the resulting solves with the composed model
and the published results. The same comparison applies to the gds2palace Elmer
path for thermal. Whether these tools are adopted, extended or complemented
depends on that comparison. Two-way coupling, temperature feeding back into EM
material data, is a further step after that.

Reference
---------

.. footbibliography::

* gds2palace: `VolkerMuehlhaus/gds2palace_ihp_sg13g2
  <https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2>`__ (GPL-3.0)
* setupEM: `VolkerMuehlhaus/setupEM <https://github.com/VolkerMuehlhaus/setupEM>`__
* chiplet_xml_composer: `volkermuehlhaus-claude/chiplet_xml_composer
  <https://github.com/volkermuehlhaus-claude/chiplet_xml_composer>`__ (GPL-3.0)
