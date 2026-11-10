.. Shared note for pages that run gds2kicad scripts by path.

In the tools image these scripts sit under ``$GDS_TO_KICAD_ROOT``; run them with
``/opt/adk-tools/venv/bin/python3``, which carries the modules they import
(KLayout, PyYAML); the image's own ``python3`` does not
(:doc:`/install/01_container`).
