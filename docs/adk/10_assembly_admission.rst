Assembly admission
==================

.. include:: /common.inc

A ``.chiplet`` places dies, but it does not say whether a placed die is the die
its producer described. A die built by the die flow carries a die contract
(:doc:`/tools/12_chiplet_flow`): which pad inventory is authoritative, what each
terminal is for, and which layout bytes and top cell the description is about.
``checks/assembly_admission.py`` is the assembly-stage gate that asks, for every
die component of a finalized ``.chiplet``, whether its contract admits it.

The check does not judge the contract itself. It hands each die component to
``die_contract.admit_component`` in the reference reader ``chiplet_format_io``
from |spec-repo|, and turns the answers into one outcome and one exit code. The
contract, its schema and every rule in it belong to the specification; the ADK
restates none of them.

Profiles
--------

``--profile`` selects one of two behaviours, and the default is ``legacy``.

``legacy``
    Asks nothing. The ``.chiplet`` is read with the ADK's vendored reader, the
    same one ``chiplet2dbx`` and ``pads_vs_pillars`` use, and the outcome is
    ``NOT_REQUESTED`` with exit code ``0``. No ``die_contract`` module is
    imported, so a legacy ``.chiplet`` loads exactly as it did before the check
    existed. The ADK suite asserts that the module is absent after a legacy run.

``strict``
    Admits every die, and never degrades a question it cannot answer to a
    warning. The ``.chiplet`` is read with the installed reader, and a check
    that cannot be answered is a red gate, not a pass with a note.

.. important::

    A legacy run exits ``0`` without checking anything. It says the assembly
    loads, nothing more. A CI gate that means to admit dies must pass
    ``--profile strict``.

What strict admission checks
----------------------------

A die component must carry a ``die_contract`` reference, an object with a
``path`` to the contract and the contract's ``sha256``. The key is additive: a
reader that never asks for admission ignores it. For each die component the
reader then refuses the die when any of these fails:

- The component declares a ``die_contract`` reference, the referenced file
  exists, and its digest equals the recorded ``sha256``.
- The contract passes the schema that ships inside the ``chiplet-format-io``
  package, and the files it binds (build record, pad inventory, layout) still
  hash to the digests it records.
- The component's own ``layout`` hashes to the layout digest the contract binds,
  and its ``top_cell`` equals the contract's top cell. Without this, a valid
  contract for a different die, placed beside this component, would pass every
  other check.
- Every terminal is in the bound pad inventory, which records its size, and
  carries an opening; every pad in the inventory is declared by a terminal; no two
  terminals share a name.

The last rule exists because the consumer that places bumps hands out
same-named pads by occurrence order. A repeated physical name cannot be
resolved without choosing a pad silently, so strict admission refuses it and
asks the producer for distinct names.

The component's ``die_contract.path`` and ``layout`` resolve against the base
directory: the ``.chiplet`` file's own directory, or ``--base-dir``. Both must
be relative and resolve inside that directory; an absolute path or one that
climbs out of it is refused, and ``${VAR}`` references are not expanded. Paths
written inside the contract resolve against the contract's own directory, so a
contract bundle can move as a unit.

Component types
~~~~~~~~~~~~~~~

``type`` is deliberately free-form in the ``.chiplet`` schema, so an
unexpected spelling would otherwise match nothing and pass silently. Strict
admission therefore classifies every component, not only the ones it checks:

.. list-table::
    :header-rows: 1
    :widths: 26 74
    :class: adk-wide-table

    * - ``type``
      - Treatment
    * - ``die``
      - Checked against its die contract.
    * - ``interposer``, ``substrate``
      - Recognized and excluded. A die contract does not describe them.
    * - ``die_array``
      - Refused by name. A die contract binds one layout and one top cell, so
        it cannot speak for the several instances an array places.
    * - anything else
      - Unclassified. The assembly cannot be decided, even when every die in
        it was admitted.

An assembly in which nothing matched, for example one with only an interposer,
cannot be decided either: a pass on an empty subject would look exactly like
a real one.

Running the check
-----------------

.. code-block:: bash

    python3 checks/assembly_admission.py \
        --chiplet build/demo.chiplet \
        --profile strict \
        --json build/assembly_admission.json

.. include:: /_image_adk_scripts.inc

.. literalinclude:: /adk/_usage/assembly_admission.txt
   :language: text

Strict admission needs the installed ``chiplet-format-io`` distribution with
its ``strict`` extra, which adds ``jsonschema``. Outside the image, install it
from ``reference/python`` in |spec-repo|. The tools image installs it in
``/opt/adk-tools/venv``, and the image build stops if strict admission cannot
load there.

Each refused die is printed to stdout as ``REFUSED [<id>]: <reason>``. Reader
warnings go to stderr prefixed with ``WARNING:``, and the reasons for an
undecidable outcome go to stderr prefixed with ``UNDECIDABLE:``. The run ends
with a one-line summary:

.. code-block:: text

    assembly_admission: profile=strict outcome=ADMITTED; 3 component(s) seen, 2 matched, 2 admitted, 0 refused, 1 excluded, 0 unclassified

An undecidable run names its cause in the same line, for example
``outcome=UNDECIDABLE (coverage_incomplete)``.

Exit codes
~~~~~~~~~~

.. list-table::
    :header-rows: 1
    :widths: 12 88

    * - Code
      - Meaning
    * - ``0``
      - ``ADMITTED``: every die was admitted. Also ``NOT_REQUESTED``, the
        legacy profile, which asked nothing.
    * - ``1``
      - ``REFUSED``: the reader refused at least one die, or the assembly
        holds a ``die_array``. Each refusal carries the reason the reader gave.
    * - ``2``
      - ``UNDECIDABLE``: strict admission was requested and the answer is not
        known. Also a command line that ``argparse`` refuses, an unreadable or
        invalid ``.chiplet``, and any unexpected failure.

An undecidable outcome has one of two causes, and the report keeps them apart:

``tooling_unavailable``
    The reader cannot answer. ``chiplet_format_io`` is not installed; it is
    installed without ``die_contract``; it resolves to the ADK's vendored copy,
    or partly into the ADK's ``vendor`` directory; its ``die_contract`` comes
    from another installation; it ships no schema; ``jsonschema`` is missing;
    or its strict admission revision is not one this check accepts. The check
    accepts revision 4 only, the revision that reads die contract 1.2 and its
    ``supply_domains``.

``coverage_incomplete``
    The assembly holds a component this profile cannot classify, or no
    component matched at all.

There is no path from ``2`` to ``0``, and a refusal never becomes a ``2``, even
beside an unclassified component. A refusal is a finding about the document;
``2`` says the answer is not known. Exit ``1`` is reachable only through the
deliberate return at the end of a completed run: the whole run is guarded, so
an unexpected exception exits ``2`` rather than through Python's default ``1``.
This is the vocabulary :doc:`/adk/08_pads_vs_pillars` uses.

.. note::

    When the tooling is missing, the command line stops before it reads the
    ``.chiplet``. It prints ``assembly_admission: error:`` with the reason and
    exits ``2``, and writes neither a summary line nor a JSON report. The
    ``tooling_unavailable`` cause appears in the report of an
    ``admit_assembly`` call made from Python.

A contract above the minor version the reader accepts, 1.3 and up, is read
element by element. An unknown key there admits the die, and the reader's
warning is collected in the report's ``warnings``: that is the reader's answer
for the newer minor, not a strict failure turned into a warning. An element the
reader cannot read, such as a terminal role it does not know, raises
``DieContractIncomplete``. That is a ``DieContractError``, so today it is
reported as ``REFUSED`` with exit ``1``, not as undecidable. The check fails
closed until that mapping changes.

The JSON report
~~~~~~~~~~~~~~~

``--json PATH`` writes the machine-readable report:

.. code-block:: json

    {
      "check": "assembly_admission",
      "profile": "strict",
      "census": {
        "components_seen": 3,
        "matched": 2,
        "admitted": 2,
        "refused": 0,
        "excluded": 1,
        "unclassified": 0,
        "types_seen": {"die": 2, "interposer": 1}
      },
      "components": [
        {"id": "U1", "type": "die", "outcome": "admitted"}
      ],
      "reasons": [],
      "warnings": [],
      "cause": null,
      "outcome": "ADMITTED",
      "exit_code": 0,
      "chiplet": "build/demo.chiplet",
      "base_dir": "/work/build"
    }

``components`` holds one entry per component with its ``outcome``
(``admitted``, ``refused``, ``excluded`` or ``unclassified``) and, for every
outcome but ``admitted``, a ``reason``. ``cause`` is ``null`` unless the outcome
is ``UNDECIDABLE``.

Importable entry points
-----------------------

.. code-block:: python

    AdmissionUnavailable                        # the third outcome, as an error
    load_admission() -> module                  # the installed die_contract
    admit_assembly(assembly, base_dir, *, profile="legacy") -> report dict
    exit_code(report) -> int
    main(argv=None) -> int

``admit_assembly`` takes an already loaded ``.chiplet`` dictionary and the
directory its references resolve against. It raises ``ValueError`` for an
unknown profile; a tooling gap is returned as an ``UNDECIDABLE`` report, never
raised. ``AdmissionUnavailable`` is deliberately not a reader error type, so
"the check said no" and "nobody could ask" cannot be confused. As everywhere in
the ADK, new options are appended as trailing keyword arguments with defaults.
