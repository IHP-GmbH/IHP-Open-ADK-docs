ADK domains
===========

.. include:: /common.inc

The ADK repository reserves three domain directories alongside the shipped
assembly rules, each carrying a README stating that no rules are shipped yet, so
that when rules land they attach at an already-agreed place rather than forcing a
reorganisation.

The shipped assembly rules are geometric: they check placement and attachment
density. The three reserved domains below are further axes along which an
assembly can fail for reasons geometry alone cannot express. They are not the
only ones: the inter-die connectivity axis is in the kit's scope rather than in a
reserved domain, and it is not part of this preview release. See
:doc:`/roadmap`.

Thermal
-------

*Reserved. Directory* ``thermal/`` *in the ADK repository.*

Intended scope: interposer hot-spot and power-density checks against chiplet
thermal maps. An assembly that is geometrically legal can still be thermally
unviable, because dissipation from one die raises the junction temperature of
its neighbour through the shared substrate. Checking that requires a per-chiplet
thermal description that the current data model does not carry.

Power delivery
--------------

*Reserved. Directory* ``power/`` *in the ADK repository.*

Intended scope: interposer power delivery network coverage checks against
chiplet supply maps. The question is whether the substrate delivers adequate
current to every die's supply pads within an acceptable voltage drop, which
again needs a per-chiplet description the assembly file does not model today.

Timing
------

*Reserved. Directory* ``timing/`` *in the ADK repository.*

Intended scope: inter-chiplet trace-length budgets on the interposer. Static
timing analysis across die boundaries is a broader open problem and is not in
scope for a rule deck.

What would have to change first
-------------------------------

All three domains share one prerequisite, which is why they are reserved rather
than in progress: each needs per-chiplet characterisation data that the assembly
does not carry, a thermal map, a supply map, a timing model. The ``.chiplet`` format deliberately
scopes itself to physical assembly and points at part-description standards for
this kind of data. See :doc:`/formats/01_chiplet` for how that boundary is
drawn.

Until that data has an agreed home, an ADK rule in these domains would have
nothing to check against.
