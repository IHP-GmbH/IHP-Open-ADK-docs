.. _partner_die_package:

Black-box pad map and partner die package
=========================================

.. include:: /common.inc

A die whose layout stays with its owner enters an assembly as a black box. Its
owner hands over one file, the partner die package, and the flow derives the
ready-die files from it. The package is the black-box pad map at version 1.1:
1.1 adds keys to the 1.0 pad map and moves none, so every 1.0 pad map stays
valid and every reader of 1.0 keeps reading it. The schema is
``schemas/blackbox_padmap.schema.json`` in |spec-repo|, under Apache-2.0.

The format is specified by ``docs/partner_die_package.md`` in the same
repository, which carries the key table with the type, rule and a placeholder
for every key. This page says what the package is for and what each part of it
states; read the specification for the exact rule of a key.

What a die owner states
-----------------------

The die seen pad side up in its own frame, in micrometres: the outline
(``die.bbox_um``, at any origin; nothing is shifted) and the thickness
(``die.thickness_um``). A flip at assembly is the assembly's convention, as for
every ready die.

Three ids of the owner's own: a PDK id, the PDK release the die was designed
with, and the die's technology id. Never a layer number, a layer name or a
design-rule value of that process. The package needs none, and the files the
flow derives from it carry only the shared pad vocabulary.

Per pad: its name, unique across the package, its centre and size, its net,
its direction and its role. For a power or ground pad the net is its supply
domain; there is no separate domain key. A function that spans several pads, a
rail, is one ``port`` with an ``ordinal`` per pad; a signal port holds one pad.

The supply volts of every power and ground net, ground at 0 and power above 0,
and no net in both roles.

A signoff statement: what the owner checked on its own layout, with which tool
and with what result, and the digest of the layout it checked. ``issued_by``
is a role or an organisation, never a person, because the record that carries
the statement travels with the run's evidence.

Optionally, a reference to a CDXML description and one to a 3Dblox
description of the same die, each with a digest.

The words are the die contract's closed sets: ``direction`` is one of
``input``, ``output``, ``bidir``, ``analog``, ``none``; ``role`` is one of
``signal``, ``power``, ``ground``, ``no_connect``; a signoff check is ``drc``,
``lvs`` or ``other``, with a result of ``pass``, ``fail`` or ``unresolved``.
Any other spelling is refused by name; nothing is guessed.

Required and optional keys
--------------------------

The schema requires only what 1.0 required, ``die`` and ``pads``. The partner
die writer requires every key of the specification's table except
``pads[].port``, ``pads[].ordinal``, ``cdxml_ref``, ``3dblox_ref`` and
``_provenance``. A 1.1 key absent from a file is therefore a refusal of the
writer, not of the schema.

A ``uri`` in either reference that names a file beside the package is a path
relative to the package's folder, with forward slashes and no way out of that
folder; the writer checks that file's digest. A URL is carried as data and not
checked.

The specification's complete placeholder package, a fictional ``owner-pdk``
die of 1500 by 1500 micrometres with five pads, two of them one ``VDD`` port,
goes through the writer unchanged. Start from it:

.. literalinclude:: /../src/chiplet-spec/docs/partner_die_package.md
    :language: json
    :start-after: ```json
    :end-before: ```

What the flow derives from it
-----------------------------

This section is informative: it describes the tool that reads the package.

The die flow's ``emit-partner-die`` (:ref:`chiplet_flow_emit_partner_die`)
turns the package into a ready die, the four-file folder every die enters an
assembly as: a pads-only layout drawn on the shared pad vocabulary, the pin
list, the die contract (with the supply voltages) and a build record that
carries the process, outline, thickness, package digest, supply volts, signoff
and references verbatim.

The flow never says more about the die than its package says. The die's
internals stay unverified. The signoff is recorded and never judged: the
layout digest in it is never compared with the derived layout. The die is
placed in an assembly only under an admission statement, as every die built
elsewhere is (:ref:`packaging_flow_black_box`).

The specification also carries a key-by-key table of which field of CDXML,
3Dblox and LEF means the same thing in the same unit, for anyone writing a
converter. No converter ships, and the package is not claimed to be aligned
with any of the three.
