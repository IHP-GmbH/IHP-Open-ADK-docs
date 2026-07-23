Roadmap
=======

.. include:: /common.inc

.. warning::
   Everything in this section describes a direction of work, not a shipped
   feature. No interface, file format or rule described here is committed, and
   nothing here is part of the preview release. Availability dates are not
   given.

The ADK reserves domain slots that mirror the empty ``thermal/``, ``power/`` and
``timing/`` directories in the ADK repository. Those directories exist so the
structure of the kit is visible before the rules land; each ships a README
noting that no rules are shipped yet.

.. toctree::
    :name: roadmap-toc
    :caption: Roadmap
    :maxdepth: 2

    ADK domains <roadmap/01_adk_domains>
    Analysis and automation <roadmap/02_analysis_and_automation>

The connectivity axis of assembly verification
----------------------------------------------

:doc:`/intro/01_what_is_the_adk` sets out the two axes of assembly verification
and why a device-graph comparator cannot reach the connectivity one. In short:
the geometric axis ships in this release, the connectivity axis asks whether the
placed assembly is wired the way the system netlist says, and neither subsumes
the other.

That axis is in the scope of the kit and on its roadmap. No implementation,
interface or result is part of this preview release. It will be documented when
it is released.
