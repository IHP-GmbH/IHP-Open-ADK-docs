IHP Open ADK documentation
==========================

The documentation site of the IHP Open Assembly Design Kit (ADK) and the flow
for 2.5D heterogeneous chiplet integration built around it. It documents code
it does not own: the repositories it describes are pinned as submodules under
``src/``.

Use
---

.. build-steps-start

.. code-block:: bash

    git clone https://github.com/IHP-GmbH/IHP-Open-ADK-docs.git
    cd IHP-Open-ADK-docs
    git submodule update --init
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r docs/requirements.txt
    make -C docs preprocess
    sphinx-build -b html -W --keep-going docs docs/_build/html

Initialise the direct submodules only, as CI and Read the Docs do.
``--recurse-submodules`` would also pull the submodules of ADK-Tools and
chiplet-studio, which this site never reads. The generators need Python 3.11 or
later. The result is in ``docs/_build/html/index.html``.

``make -C docs docs`` runs the whole chain, generators included, and opens the
result. It installs the requirements with ``python3 -m pip`` and calls
``sphinx-build`` from ``PATH``, so run it with the venv activated.

.. build-steps-end

Documentation
-------------

The full documentation is at https://ihp-open-adk-docs.readthedocs.io/en/latest/.
How the site is generated and the authoring contract are on its page
"Contributing to this documentation" (``docs/contrib/02_documentation.rst``).

Release
-------

Released as part of the IHP Open ADK. The release page lists the commit of
every repository in each release:
https://ihp-open-adk-docs.readthedocs.io/en/latest/install/00_release.html

License
-------

Apache-2.0. See ``LICENSE``.
