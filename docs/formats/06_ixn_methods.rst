Interconnect methods manifest
=============================

.. include:: /common.inc

The interconnect methods manifest is the sidecar that tells the assembly DRC
**which attachment method each die uses, and what numbers apply to it**. It
turns the interconnect axis from one set of pitch and spacing values applied to
the whole assembly into per-method values applied to the pads under each die.

It exists because a real heterogeneous assembly mixes attachment methods. One
die may be attached with a 75 um pitch Cu pillar, another with a 50 um pitch
microbump. A single assembly-global pitch number is either too loose for the
first or impossible for the second. The manifest lets each method be checked
against its own numbers, and lets the boundary between two methods be checked
against the stricter of the two.

The normative JSON Schema is ``config/schema/ixn_methods.schema.json`` in
|adk-repo|.

File location
-------------

Written next to the assembly GDS, named after its stem, a sibling of the other
two sidecars::

    board_complete.gds
    board_complete.boundaries.json
    board_complete.ixn_methods.json

Unlike the boundary manifest, this file is **not** auto-discovered. It is passed
explicitly:

.. code-block:: bash

    python klayout/drc/run_drc.py --path board_complete.gds \
        --interposer-adapter intm4tm2 \
        --interconnect-adapter ihp_cupillar \
        --interconnect-methods board_complete.ixn_methods.json

Omitting it is a supported configuration: the interconnect axis then runs
assembly-global with the adapter's numbers, exactly as it did before per-method
scoping existed. The KiCad export pipeline passes the file automatically when it
was able to derive one.

Schema
------

Top level
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 10 14 54
   :class: adk-wide-table

   * - Field
     - Required
     - Type
     - Meaning
   * - ``schema``
     - yes
     - string
     - Literal ``"adk-ixn-methods"``.
   * - ``version``
     - yes
     - string
     - Exact ``"1.0.0"``. The schema only types it as a string; the exact
       value is pinned by ``run_drc.py``.
   * - ``methods``
     - yes
     - object
     - Maps a method id to its per-method numbers and the dies using it.
   * - ``assembly_gds``
     - no
     - string
     - Basename of the assembly GDS this sidecar describes.

.. note::
   The exporter also writes ``generator`` and ``source_chiplet`` for
   provenance. The schema does not declare them and no consumer reads them;
   they are valid because the schema does not forbid extra properties.

Method entries
~~~~~~~~~~~~~~

Every entry under ``methods`` must carry all four keys. This is enforced twice:
by the schema, and again by ``adk_assembly.drc``, which raises by name on the
first missing key rather than letting a ``nil`` reach a rule.

.. list-table::
   :header-rows: 1
   :widths: 22 12 66
   :class: adk-wide-table

   * - Key
     - Type
     - Meaning
   * - ``IXN_spacing``
     - number greater than zero
     - Minimum edge-to-edge spacing between attachment points of this method,
       in micrometres.
   * - ``IXN_pitch``
     - number greater than zero
     - Minimum centre-to-centre pitch between attachment points of this method,
       in micrometres.
   * - ``IXN_pad_size``
     - number greater than zero
     - Representative attachment-pad size in micrometres, used for the
       pitch-to-spacing conversion.
   * - ``dies``
     - array of at least one string
     - Die instance names using this method. Resolved against
       ``boundaries[].instance`` in the boundary manifest.

``IXN_pad_size`` is not a rule of its own: it feeds the pitch-to-spacing
conversion ``min_space = pitch - pad_size``, and the deck refuses to run a method
whose ``IXN_pitch`` does not exceed it, because that would produce a zero or
negative spacing that silently checks nothing.

The schema file
~~~~~~~~~~~~~~~

``config/schema/ixn_methods.schema.json``, validated against the shipped
sidecars in CI so the committed schema cannot drift from the data.

.. literalinclude:: /../src/IHP-Open-ADK/config/schema/ixn_methods.schema.json
    :language: json

Example
-------

Taken from the two-die reference assembly, where ``U1`` is attached with a Cu
pillar and ``U2`` with a finer-pitch microbump:

.. code-block:: json

    {
      "schema": "adk-ixn-methods",
      "version": "1.0.0",
      "generator": "chiplet_kicad_plugin/orchestrator",
      "assembly_gds": "two_die_interposer_complete.gds",
      "source_chiplet": "two_die_interposer.chiplet",
      "methods": {
        "cupillar_opt1": {
          "dies": ["U1"],
          "IXN_spacing": 40.0,
          "IXN_pitch": 75.0,
          "IXN_pad_size": 35.0
        },
        "vendorx_microbump": {
          "dies": ["U2"],
          "IXN_spacing": 15.0,
          "IXN_pitch": 50.0,
          "IXN_pad_size": 35.0
        }
      }
    }

How the exporter derives the file
---------------------------------

Nothing in this file is typed by hand. The exporter joins two sources:

#. The ``.chiplet`` assembly, which records a ``connection:`` id per die. For
   manifest-era assemblies that id **is** the interconnect method id.
#. The interconnect PDK manifest,
   ``manifest/interconnect_methods.json`` in |interconnect-repo|, which is the
   single source of truth for each method's numbers.

``derive_interconnect_methods`` in the plugin's ``pipeline/orchestrator.py``
walks the per-die connections, looks each one up in the interconnect PDK
manifest, and builds one entry per method it recognises:

.. list-table::
   :header-rows: 1
   :widths: 30 70
   :class: adk-wide-table

   * - Manifest key
     - Sidecar key
   * - ``pitch_rules.IXN_spacing``
     - ``IXN_spacing``
   * - ``pitch_rules.IXN_pitch``
     - ``IXN_pitch``
   * - ``fab_params.passiv_opening_um``
     - ``IXN_pad_size``
   * - the ``.chiplet`` die ids carrying that ``connection``
     - ``dies``

Note that ``IXN_pad_size`` comes from the passivation opening, not from the
bump body diameter. The opening is what the interposer fabricates; the body
diameter is a property of the attachment element sitting on it.

The derivation degrades rather than guesses, at every step:

* A connection id the interconnect PDK manifest does not know is skipped. It is
  a custom or legacy stack, and the assembly-global adapter still covers it.
* A manifest entry with a missing or malformed number is skipped, again leaving
  it to the adapter.
* A non-positive number is skipped, because the schema requires values greater
  than zero and one bad entry would make ``run_drc.py`` reject the whole
  sidecar.
* When nothing is derivable, no file is written at all and the DRC runs exactly
  as it did before this refinement existed.

There is one more filter. ``_intersect_methods_with_manifest`` drops derived
dies that do not appear in the GDS's ``<stem>.boundaries.json``, and drops a
method whose dies all disappear. This is not cosmetic: the deck hard-raises when
a methods entry names a die instance the boundary manifest does not declare, so
without the filter a legitimately partial export would abort the DRC.

One interconnect PDK, many methods
----------------------------------

The rule the format encodes is worth stating plainly: **an assembly has one
interconnect PDK, and a method per die.**

The interconnect PDK is the vendor process that performs the bumping. It
supplies the method registry, the 3D layer numbers, the fabrication anchors and
the bump macro generator. Mixing two of them in one assembly would mean two
bumping vendors in one pass, which is not a thing an assembly flow can express.
Accordingly there is one ``--interconnect-adapter`` per run, and the sidecar is
derived from one ``manifest/interconnect_methods.json``.

Within that one PDK, the method varies per die. ``cupillar_opt1``,
``cupillar_opt2``, ``cupillar_opt3``, ``sbump_sac305`` and the non-IHP demo
entry ``vendorx_microbump`` all live in the same registry, and any die may
select any of them through its ``.chiplet`` ``connection:`` field. That is what
the ``dies`` array expresses, and it is why the numbers are per method rather
than per assembly.

What the deck does with it
--------------------------

With the sidecar loaded, ``8_2_interconnect.drc`` switches from assembly-global
mode to per-method mode: per-method spacing and pitch inside each method's
region, a cross-method separation between every pair of regions, and the
adapter's assembly-global numbers on anything no method claims, reported as
``IXN.b.unclaimed`` and ``IXN.e.unclaimed``. If no interconnect adapter was
loaded, those unclaimed pads are not checked on this axis at all, and the deck
says so in its log. :doc:`/adk/04_ixn_rules` gives the rule names and the region
construction.

Two constraints follow from that. The sidecar requires the boundary manifest,
because the method regions are built from it, and it therefore cannot be
combined with ``--legacy-exchange0``: legacy mode carries no per-die instance
names. ``run_drc.py`` rejects that combination before spawning KLayout.

Version policy
--------------

``run_drc.py`` pins ``schema`` and ``version`` with exact string matches, the
same fail-loud policy as the boundary manifest, and for the same reason: the
deck JSON-parses the file blind, so a stale or foreign sidecar has to be
rejected by the runner or not at all. Per-method key presence is validated by
the deck, and the numeric values are validated by the schema.

.. tip::
   If the DRC report suddenly shows ``IXN.b`` instead of ``IXN.b.<method>``, the
   methods file was not passed or derived nothing. Check that the ``.chiplet``
   dies carry a ``connection:`` id the interconnect PDK manifest knows.

See :doc:`/adk/04_ixn_rules` for the rules themselves and their defaults, and
:doc:`/tools/06_interconnect_pdk` for the method registry this sidecar is
derived from.
