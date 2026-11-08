.. Shared note for pages that run run_drc.py by path.

In the tools image the assembly DRC runner is the ``adk-drc`` command. It takes
the same arguments as ``run_drc.py`` and runs it with
``/opt/adk-tools/venv/bin/python3``, which carries the modules it imports
(KLayout, PyYAML); the image's own ``python3`` does not
(:doc:`/install/01_container`).
