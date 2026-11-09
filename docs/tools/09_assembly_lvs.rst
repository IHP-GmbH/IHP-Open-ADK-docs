Assembly LVS (assembly-lvs)
===========================

.. include:: /common.inc

``assembly-lvs`` checks the connectivity axis of assembly-level verification,
the one :doc:`/intro/01_what_is_the_adk` calls assembly LVS. It reads the layout
of every component of a placed 2.5D assembly, the interposer and each die, puts
each one where the assembly places it, and follows the metal through the layers,
vias and contacts its input declares. It then compares the nets it extracted
with the logical nets the input declares, and reports every open and every
short it finds.

Version 0.8.0 ships in the ADK-Tools image as the ``assembly-lvs`` command.
packaging-flow runs it as one stage of a flow run, and you can also run it on
its own. It is licensed GPL-3.0-or-later.

.. warning::
   assembly-lvs is a |current-status| at alpha maturity: its input and report
   formats and its exit codes may still change between versions. A match says
   that the extracted artwork connectivity agrees with the declared nets under
   the model described on this page, nothing more. It does not check the dies,
   their devices or the electrical behaviour of the assembly, and it is not
   sign-off. Read `What it does not check`_ before relying on a verdict.

What it checks
--------------

The input is one **resolved** document, YAML or JSON, not a GDS plus a netlist.
It names every component layout and where it sits, maps each component's GDS
layers onto technology layers, lists the vias and the layer pairs allowed to
make contact across a component boundary, gives every die pad a terminal
window, and declares the intended nets as an independent list of
``(component, pin)`` endpoints. An assembly flow writes this document, or a
person does. Coordinates are in micrometres on the technology grid, and every
file it names is a portable relative path.

From that document the engine builds a physical graph and compares it with the
declared nets:

- **Nodes** are the placed, merged polygons of each component on each declared
  layer.
- **Edges** come from three sources only: geometry on the same layer, an
  explicit via rule between two conductors, and an explicit interface-contact
  rule between a die layer and an interposer layer. No connection between
  adjacent layers is ever inferred.
- **Terminals** are audit windows. Each must lie fully inside one merged pad
  polygon, and every die pad polygon on a declared interface layer must be
  covered by at least one window. A window selects metal; it never adds any.
- **The reference** is the declared net list. Text labels and the ``net`` value
  of an interposer I/O pad are carried as metadata and never join geometry.

Each component can be given a placement uncertainty, a bound on how far it may
translate in the plane. With a bound of zero the check is at the nominal
placement. With a nonzero bound, a fast pairwise bracket first compares two
graphs, one with the contacts that must happen anywhere within the bound and
one with the contacts that may happen, and settles every result on which both
agree. If the result still depends on the placement, an exact global stage asks
the Z3 solver whether a correct placement and an incorrect placement each exist
within the bound.

Running it
----------

.. code-block:: text

    assembly-lvs verify INPUT [-o REPORT] [--quiet] [--debug] [--pairwise-only]

``verify`` is the only subcommand. ``assembly-lvs --version`` prints the
version.

.. list-table::
    :header-rows: 1
    :widths: 28 72

    * - Argument
      - Meaning
    * - ``INPUT``
      - The resolved document, YAML or JSON. Schemas
        ``assembly-lvs.resolved/v2``, ``/v3``, ``/v4`` and ``/v5`` are
        accepted.
    * - ``-o``, ``--report REPORT``
      - Where to write the report. The default is beside the input, named after
        its stem: ``resolved.yaml`` gives ``resolved.lvs.json``. ``-`` writes
        the report to standard output, and then the summary line goes to
        standard error. A path ending in ``.lvsdb`` is refused with exit code 2,
        because the LVS database would overwrite it.
    * - ``--quiet``
      - Suppresses the one-line summary.
    * - ``--debug``
      - On an unexpected internal error, writes the ``invalid`` report and then
        re-raises the exception with its traceback. The exit status is then
        Python's, not the table below, so use it for debugging only.
    * - ``--pairwise-only``
      - Skips the exact global stage. A result the pairwise bracket cannot
        settle stays ``ambiguous``.

The engine is technology-neutral: no PDK name appears in it, and everything it
knows about layers and contacts comes from the input.

A first run
~~~~~~~~~~~

The engine carries a minimal input, one die on a carrier with one net. Inside
the image, copy the input to a folder of your own, generate its two layouts
there, and verify it:

.. code-block:: bash

    mkdir -p /tmp/alvs-minimal
    cp /opt/adk-tools/staging/assembly-lvs/examples/minimal/resolved.yaml \
        /tmp/alvs-minimal/
    /opt/adk-tools/venv/bin/python3 \
        /opt/adk-tools/staging/assembly-lvs/examples/minimal/make_layouts.py \
        --out /tmp/alvs-minimal
    assembly-lvs verify /tmp/alvs-minimal/resolved.yaml
    echo $?

.. code-block:: text

    assembly-lvs: robust_match; report=/tmp/alvs-minimal/resolved.lvs.json
    0

The folder now holds ``resolved.lvs.json`` and ``resolved.lvs.lvsdb`` beside
the input. Move the die off its landing and run it again:

.. code-block:: bash

    sed -i 's/position_um: \[50, 50\]/position_um: [150, 50]/' \
        /tmp/alvs-minimal/resolved.yaml
    assembly-lvs verify /tmp/alvs-minimal/resolved.yaml
    echo $?

.. code-block:: text

    assembly-lvs: definite_open; report=/tmp/alvs-minimal/resolved.lvs.json
    1

The report's finding says that logical net ``N0`` now spans two physical
components: the die pad no longer lands on the carrier metal.

Input and report versions
-------------------------

Each input version is answered by its own report version, one to one:

.. list-table::
    :header-rows: 1
    :widths: 24 22 54

    * - Input
      - Report
      - Adds
    * - ``resolved/v2``
      - ``report/v3``
      - The base contract.
    * - ``resolved/v3``
      - ``report/v4``
      - An optional per-die footprint policy: a seal-ring frame on the pad
        layer is accepted when it is proved isolated from the carrier.
    * - ``resolved/v4``
      - ``report/v5``
      - Metal fill on a layer mapping, removed from the carrier where it
        provably cannot join a net.
    * - ``resolved/v5``
      - ``report/v6``
      - A die pin on several pads, grouped by the die's own declaration. The
        group is not verified and joins nothing: each pad is still checked as
        its own terminal.

Final states and exit codes
---------------------------

Every run ends in one of nine final states. The state is the report's top-level
``state``, and the exit code follows from it:

.. list-table::
    :header-rows: 1
    :widths: 26 8 66

    * - State
      - Exit
      - Meaning
    * - ``robust_match``
      - 0
      - The extracted connectivity matches the declared nets, settled by the
        pairwise bracket.
    * - ``robust_match_global``
      - 0
      - The bracket could not settle it; the global stage found that every
        placement within the bound matches.
    * - ``definite_open``
      - 1
      - A declared net is split in the extracted connectivity, wherever the
        components sit within the bound.
    * - ``definite_short``
      - 1
      - Two declared nets are joined in the extracted connectivity, wherever the
        components sit within the bound.
    * - ``unavoidable_mismatch``
      - 1
      - The global stage found that no placement within the bound gives the
        declared connectivity.
    * - ``invalid``
      - 2
      - No verdict: malformed input, a layout extraction failure or a tool
        failure. The report's ``invalid_phase`` says which: ``input``,
        ``geometry`` or ``internal``.
    * - ``ambiguous``
      - 3
      - Only with ``--pairwise-only``: the bracket could not settle the result.
    * - ``placement_dependent``
      - 3
      - Some placements within the bound match and some do not.
    * - ``inconclusive``
      - 3
      - No verdict could be reached: uncertainty geometry the method does not
        support (a polygon with holes, for example), a resource or solver limit,
        or a solver answer of unknown. Never a pass and never a fail.

Exit code 2 is also returned for a usage error, a report path ending in
``.lvsdb`` and a report that cannot be written; in those cases no report is
left at the report path.
The report lists every finding, so an assembly with both an open and a short
reports both, whichever state it ends in.

The report
----------

The report is deterministic JSON, sorted and indented. Its top level carries
``schema_version``, ``state`` and ``exit_code``; ``engine``, with the versions
of assembly-lvs, KLayout, Z3 and Python that produced it; ``input``, with the
input's file name and SHA-256; ``summary``, with the counts of nets and findings
and the state of each stage; ``findings``, one entry per open, short or
diagnostic, naming the nets and terminals involved; ``nets``, the state of each
declared net and its terminals; ``physical``, the extracted polygons, terminals,
edges and the full ledger of contact candidates; and ``limitations``, the
engine's own statement of what the verdict does not cover.

``run_id`` is the SHA-256 of every other field. Inputs use only relative paths
and the report keeps only the input's file name, so moving an input tree gives
a byte-identical report. These hashes are content identities, not signatures:
to trust a report received from elsewhere, run the engine again on the inputs it
names.

The LVS database
----------------

Beside a file report, a run that reaches a verdict also writes a KLayout LVS
database: the report's suffix replaced by ``.lvsdb``, so
``--report out/assembly_lvs.json`` also writes ``out/assembly_lvs.lvsdb``. It is
a view of the report for KLayout's netlist browser, not a second verdict, and
it never changes the report.

- An ``invalid`` or ``inconclusive`` run writes none, and removes any database
  an earlier run left at that path. A report on standard output writes none.
- It is written from the engine's own graphs; KLayout's extractor and netlist
  comparer never run.
- The top circuit is named after the interposer's top cell in the input, the
  unit is the technology grid, and there is one layer per component and
  technology layer, named ``<component>:<technology layer>``.
- The layout netlist has one net per extracted component, named after the
  logical nets whose terminals it carries; the reference netlist is the
  declared nets. Each pair is marked match, mismatch or warning from the
  report's states, and carries its findings as its description.
- A database that cannot be built or written costs only the database: the run
  says so on standard error and keeps its report and exit code.

Open it over an assembly layout whose top cell has the interposer's top-cell
name, with ``klayout <assembly layout> -mn <report stem>.lvsdb``. The ``-mn``
option loads a netlist database; ``-m`` is for marker databases.

In a flow run
-------------

Most users meet assembly-lvs through packaging-flow rather than directly. A flow
run that composes an assembly derives the resolved document from its own
records, runs the ``assembly-lvs`` command on the image's ``PATH`` by default,
and accepts only the report version that pairs with the input it wrote. It
reads the nine states as four words:

.. list-table::
    :header-rows: 1
    :widths: 22 78

    * - Flow word
      - assembly-lvs states
    * - PASS
      - ``robust_match``, ``robust_match_global``
    * - FAIL
      - ``definite_open``, ``definite_short``, ``unavoidable_mismatch``
    * - INCONCLUSIVE
      - ``ambiguous``, ``placement_dependent``, ``inconclusive``, and an
        assembly the flow could not express as a resolved input
    * - ERROR
      - ``invalid``, a report the flow refuses, or a tool failure

Only a FAIL can be waived; a run whose every FAIL is covered exits 16
(:doc:`/tools/10_packaging_flow`). The flow passes a placement bound of zero for every
component, so its verdict is at the nominal placement, and it does not claim die
LVS. The flow also maps only dies at rotation 0: a die at another right angle,
which the engine itself accepts, is an assembly the flow cannot express, and
the check reads INCONCLUSIVE with the cause ``unsupported_orientation``.
``packaging-flow lvs-bundle`` writes the assembly-LVS input of one
completed run into a directory, and ``packaging-flow lvs-verify`` derives it
again from those copies and runs assembly-lvs on it.

The ADK view of a resolved document
-----------------------------------

The ADK can build its own files for the assembly a ``resolved/v2`` document
describes: an assembly GDS, the boundary and pillar manifests, the per-method
IXN sidecar and a ``.chiplet``, ready for the ADK DRC and the pad to pillar
check. :doc:`/adk/11_resolved_v2_entry` describes that entry and the subset of
v2 it accepts. On the ``.chiplet`` side, whether each placed die is the one its
die contract describes is a separate gate, :doc:`/adk/10_assembly_admission`.
Run it on the accepted ``.chiplet`` that carries the ``die_contract``
references, not on the ``.chiplet`` the entry writes: the entry writes none, so
strict admission refuses every die in it.

What it does not check
----------------------

Most of these limits are stated by the engine itself, in every report's
``limitations`` list:

- The dies themselves. It extracts no devices and checks no die-internal
  connectivity. Per-die LVS stays with each die's PDK, and interposer LVS with
  the interposer PDK.
- Electrical behaviour: resistance, capacitance, current, signal or power
  integrity.
- Reliability, thermal or mechanical properties.
- Geometric legality. Overlap, spacing and pitch belong to assembly DRC; see
  :doc:`/flow/06_verification_stages`.
- Anything outside one planar 2.5D interface with one interposer. 3D stacks are
  out of scope.
- Rotations other than multiples of 90 degrees.
- Placement error other than a rigid, independent translation per component, up
  to the stated bound. In a flow run that bound is zero.
- Layer and contact rules the input does not declare. The vias and interface
  contacts come from the input and are not checked against any PDK.
- A die pin on several pads, unless a verified component contract ties them. A
  tie the die only declares (``resolved/v5``) joins no pads, so a die that ties
  its pads internally and is connected on one pad only does not pass.
- Raw GDS polygons exactly. Exactness is relative to KLayout's merged, integer
  geometry, so KLayout's merge is trusted.
- Proof of the solver's answers. Z3's unsatisfiable results are not
  independently proof-checked.
- Who issued a component contract. A contract is bound to its layout by hash,
  so a stale or rebound one is detected, but its issuer is not authenticated.

No independent oracle and no validation campaign on real designs ship with it.
A match is a connectivity statement under this model, not sign-off.
