Roadmap
=======

.. include:: /common.inc

.. warning::
   Everything in this section describes a direction of work. No interface, file
   format or rule described here is committed, and availability dates are not
   given. Where a page names a tool that ships in the preview release, it links
   to that tool's reference page, which carries the tool's own status.

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

The axis itself is not a direction of work any more: it ships in this release
as ``assembly-lvs``, and :doc:`/tools/09_assembly_lvs` documents what it checks
and, as plainly, what it does not. What stays here is one direction of work on
it, placement tolerance. The engine accepts a bound on how far each component
may move in the plane, and packaging-flow (:doc:`/tools/10_packaging_flow`)
passes a bound of zero, so a flow run checks the nominal placement only. Giving each bump method a placement accuracy
for the flow to pass on is listed in :doc:`/contrib/01_contributing`.
