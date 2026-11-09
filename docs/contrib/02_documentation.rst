Contributing to this documentation
==================================

.. include:: /common.inc

This site lives in its own repository and documents code it does not own. The
sources are pinned as git submodules under ``src/``, and the parts of the site
that state facts about that code are generated from it rather than typed.

Getting a local build
---------------------

.. include:: ../../README.rst
    :start-after: .. build-steps-start
    :end-before: .. build-steps-end

.. important::
   The build must be warning free. ``-W`` is set in the Makefile and
   ``fail_on_warning: true`` is set for Read the Docs, so a warning is a broken
   build, not a cosmetic issue.

What is generated
-----------------

``docs/scripts/`` reads the submodules and writes the rule tables, the adapter
tables, the version matrices, the command line transcripts, the image build
recipe, the coordinate values the format and flow pages quote and the
constants the admission and entry pages quote. Never edit
the generated files: they are overwritten on every build.

.. list-table::
    :header-rows: 1
    :widths: 32 68

    * - Generator
      - Produces
    * - ``gen_rule_tables.py``
      - The ASM and IXN rule and parameter tables, and the rule counts.
    * - ``gen_adapter_table.py``
      - The shipped interposer and interconnect adapter tables.
    * - ``gen_version_matrix.py``
      - The pinned component matrix and the format and schema version matrix.
    * - ``gen_cli_usage.py``
      - The ``--help`` transcript of each ADK command line tool.
    * - ``gen_build_recipe.py``
      - The image build recipe, copied from the ADK-Tools README with the
        pinned release tag, and the ``|release-tag|`` substitution.
    * - ``gen_frame_values.py``
      - ``_frame_values.inc``: the interposer PDK's mount plane, each die's
        method, stack, pitch and spacing, the dimensions and die z of the
        specification's worked example and of the reference design, the
        reference die's origin offset (read from its GDS with KLayout), the
        positions Chiplet Studio's round-trip test asserts and the z
        tolerance of ``chiplet2dbx``. Also the specification excerpts under
        ``formats/_excerpts/`` and the usage-class table. It fails when a
        file's plane or a die z disagrees with the PDK key.
    * - ``gen_admission_values.py``
      - ``_admission_values.inc``: the strict admission revision and contract
        minor, the component type table, and the profile, schema versions and
        limits of the resolved v2 entry, all read from the ADK's constants. It
        fails when an exit code mapping or the handling of
        ``DieContractIncomplete`` no longer matches what the pages say.
    * - ``check_validation_rules.py``
      - Nothing. It fails when the validation rules on
        :doc:`/formats/01_chiplet` drift from the specification's numbering.

The generators fail the build when the source drifts from what is documented.
Adding a rule to a deck without describing it, renaming a command line tool, or
removing a required key from an adapter all stop the build with a diagnostic
rather than silently producing a table that no longer matches the code.

Continuous integration re-runs every generator and fails if the working tree is
then dirty, which is what proves the published tables match the pinned revisions.

Updating to newer sources
-------------------------

.. code-block:: bash

    git submodule update --remote src/IHP-Open-ADK
    git add src/IHP-Open-ADK
    git diff --cached --submodule=log src/IHP-Open-ADK
    make -C docs preprocess
    git diff

The generators refuse a submodule whose checkout differs from the commit the
index pins, so stage the new pin before regenerating. The ``--cached`` diff
lists the commits the move pulls in. Review the diff in the generated tables.
It tells you exactly what changed in the code that this site makes claims
about, and therefore which prose needs rereading.

Pages a repository keeps for this site
--------------------------------------

A repository can keep pages for this site in its own ``docs/`` folder, in
Markdown or reStructuredText. They are built as they stand, with no copy and no
include page in between. Three things wire one in, all in the same change:

- the repository is a submodule under ``src/``, and is listed under
  ``submodules: include`` in ``.readthedocs.yaml``, so the hosted build checks
  it out;
- ``docs/_repos/<name>`` is a relative symlink to ``../../src/<name>``, the
  submodule itself and never a checkout beside this repository, so it resolves
  in any clone with its submodules;
- a toctree on one of this site's pages names the repository's index, as
  ``/_repos/<name>/docs/index``.

``REPO_PAGES`` in ``conf.py`` builds every ``docs/`` folder under ``_repos/``
and nothing else from the repository. A repository whose pages live elsewhere
adds its own patterns there. Building the pages from the repository's tree is
what keeps their relative includes and links working: a page included from
this site would resolve them against the including page instead.

Writing conventions
-------------------

Pages are reStructuredText and follow the conventions of the sibling PDK
documentation at https://ihp-open-pdk-docs.readthedocs.io.

- Page titles use ``=``, sections ``-``, subsections ``~``.
- Double backticks for paths, environment variables, commands and identifiers.
- Reference other pages with ``:doc:`` and an absolute path.
- ``.. warning::`` is reserved for status and risk. Prefer ``.. note::`` and
  ``.. tip::`` elsewhere.
- Rule and parameter tables are ``.. csv-table::`` reading a generated file. The
  CSV has no header row; the headers live in the directive.
- Include ``/common.inc`` on any page that uses a substitution.

Editorial rules
---------------

This section is the authoring contract. The constraints below are factual or
legal rather than stylistic, and a pull request that breaches one will be sent
back even if the prose is good.

- Never describe electromagnetic or thermal results as measured. They are
  numerically verified.
- Never write "signoff-grade" or "production-grade". This is a preview release.
- Hedge novelty claims as "to our knowledge, the first open ...". Never claim
  primacy over other open work in the field.
- Never describe a complete assembly as fabricated. The interposer process has
  been fabricated several times at IHP, which is a statement about process
  maturity.
- Never present 3Dblox as closed or proprietary. It has an open implementation.
- Automated 2.5D place and route is a proof of concept. Do not present it as
  more than that.
- Do not name a bumping or packaging vendor in the site's own prose. Write "the
  bumping vendor" or "the vendor's Cu-pillar table". A vendor name that appears
  inside a file quoted verbatim from a source repository stays as it is, because
  changing it would make the documentation misdescribe the file.
- Assembly LVS ships as ``assembly-lvs``. Describe what it checks together with
  what it does not, as :doc:`/tools/09_assembly_lvs` does. Never present a
  match as sign-off, as per-die LVS or as an electrical check, and make no
  benchmark or primacy claim for it.
- No em-dashes and no emojis anywhere.
- British spelling throughout, except in verbatim quotations of file names,
  command output and tool user-interface strings.
- Do not present the shipped rule values as foundry rules. Read
  :doc:`/adk/09_registries` for what provenance each one actually has.
- Do not number figure captions. Write the caption text only, with no
  "Figure N." prefix. ``numfig`` is deliberately off: Sphinx numbers per
  document, so a figure reused on two pages would carry two different numbers,
  and no prose on this site cites a figure by number. Every figure sits next to
  the paragraph it illustrates. If a paginated build is ever added, that is the
  moment to reconsider ``numfig`` deliberately.
- A figure enters as a rendered SVG with a same-name PDF, text outlined, and a
  page references it as ``/_figures/<name>.*``: the HTML build takes the SVG
  and the PDF build the PDF. Drawing sources and render tooling stay out of the
  repository, and a new or changed figure comes in the documentation's house
  style. Screenshots and other images a tool produced stay PNG.
