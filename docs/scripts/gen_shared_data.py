#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Write the tables of formats/00_shared_data: where each shared datum lives.

A row names a datum, the repository that owns it and the file, and the files
in other repositories that read or write it. None of that is trusted as typed:
the generator holds every row to the pinned trees and stops the build when a
row no longer matches them.

- The owner's file, and its schema when the row names one, exist at the pin.
- A version shown in the table is read from the file at the pin.
- Each reader or writer file exists at its own commit and still names the
  datum (the row's needle, by default the file name), so a reader that stops
  reading it, or moves, fails here.
- The page each row links to names the datum too.

Public repositories are read at the commit this site pins them at. The staged
engines (interposer-pnr, packaging-flow, assembly-lvs, chiplet-cosim,
chiplet-flow) are read at the commit docs/tools/tables/staged_engines.json
records, in a checkout beside this repository or in STAGE_SIBLINGS. The public
build has no such checkout, so there those rows are written unchecked. The
release regeneration sets STAGE_SIBLINGS, and then every engine must be found
and checked. A run that finds some engines but not all fails, so a table is
never half checked; the tables come out the same either way.

ADK-Tools' ci/contract-registry.json, read at its pin, contributes twice: the
consumers it lists for a published file join that row's readers, and each copy
its contract gate compares with the owner's file is a row of the copies table.
Copies the registry does not hold are listed in COPIES below and checked like
a row. A registry entry this page has no wording for stops the build.

Writes docs/formats/tables/shared_*.csv.
"""

import json
import os
import re

from _common import (
    ADK,
    DOCS_DIR,
    INTERCONNECT,
    INTERPOSER,
    REPO_ROOT,
    SPEC,
    SRC_DIR,
    TOOLS,
    fail,
    git_text,
    pinned_commit,
    read_json,
    read_text,
    require_submodule,
    run_git,
    stage_siblings,
    write_csv,
)

#: key -> (submodule path, the repository's name on the page). The keys are
#: also the repository keys of ADK-Tools' contract registry.
PUBLIC = {
    "adk": (ADK, "IHP-Open-ADK"),
    "spec": (SPEC, "chiplet-system-spec"),
    "interposer": (INTERPOSER, "OpenIntM4TM2"),
    "interconnect": (INTERCONNECT, "IHP-Interconnect-IntM4TM2"),
    "tools": (TOOLS, "ADK-Tools"),
    "gds2kicad": (os.path.join(SRC_DIR, "gds2kicad"), "gds2kicad"),
    "plugin": (os.path.join(SRC_DIR, "Chiplets-KiCad-Plugin"), "Chiplets-KiCad-Plugin"),
    "studio": (os.path.join(SRC_DIR, "chiplet-studio"), "chiplet-studio"),
}
#: staged engines, by their key in staged_engines.json (also their checkout's name)
ENGINES = ("interposer-pnr", "packaging-flow", "assembly-lvs", "chiplet-cosim", "chiplet-flow")
STAGED_RECORD = os.path.join(DOCS_DIR, "tools", "tables", "staged_engines.json")
OUT = os.path.join(DOCS_DIR, "formats", "tables")
REGISTRY = "ci/contract-registry.json"

# A reader or writer is (repository key, file) or (repository key, file,
# needle); the needle defaults to the row's. A tool that reads a file only to
# verify it counts as a reader. Readers the contract registry lists as
# consumers of a row's file are added to the row and checked like the others.

# Published data: what a technology or the ADK publishes for the others to read.
PUBLISHED = [
    dict(name="Assembly rule parameters", owner="adk", path="config/rule_params.json",
         schema=("spec", "schemas/rule_params.schema.json"), version="version",
         readers=[("interposer-pnr", "src/interposer_pnr/sources.py"),
                  ("packaging-flow", "src/packaging_flow/engine.py")],
         page="adk/09_registries"),
    dict(name="Adapter ids and the decks they name", owner="adk", path="adk_registry.builtin.json",
         version="version",
         readers=[("plugin", "plugins/chiplet_export/pipeline/orchestrator.py", "--interposer-adapter"),
                  ("packaging-flow", "src/packaging_flow/stages.py", "--interposer-adapter")],
         note="The plugin passes an adapter id to the ADK's ``klayout/drc/run_drc.py``, packaging-flow "
              "to ``adk-drc``; both resolve it through the ADK's own loader.",
         page="adk/02_adapter_contract"),
    dict(name="Black-box pad layer vocabulary", owner="spec", path="schemas/chiplet_pads.json",
         version="version",
         readers=[("gds2kicad", "blackbox_chiplet.py"),
                  ("adk", "checks/pads_vs_pillars.py")],
         note="gds2kicad reads the ADK's copy, or its own built-in copy when no ADK is found.",
         page="adk/09_registries"),
    dict(name="Interconnect methods: pitch, body, anchors per method", owner="interconnect",
         path="manifest/interconnect_methods.json",
         schema=("spec", "schemas/interconnect_methods.schema.json"), version="schema_version",
         readers=[("adk", "bridges/assembly_lvs/derive_attachment_sidecar.py"),
                  ("adk", "bridges/assembly_lvs/resolved_v2_entry.py", "methods_manifest"),
                  ("plugin", "plugins/chiplet_export/pipeline/orchestrator.py"),
                  ("interposer", "libs.tech/parasitics/routed_load.py"),
                  ("tools", "bin/adk-verify-carrier-drc"),
                  ("tools", "ci/check_attach_plane.py"),
                  ("interposer-pnr", "src/interposer_pnr/sources.py"),
                  ("packaging-flow", "src/packaging_flow/engine.py")],
         needle="interconnect_methods", page="tools/06_interconnect_pdk"),
    dict(name="Interconnect methods reader", owner="interconnect",
         path="libs.tech/klayout/python/interconnect_manifest.py",
         readers=[("plugin", "plugins/chiplet_export/writers/connection_stacks.py", "interconnect_manifest"),
                  ("plugin", "plugins/chiplet_export/hyp_to_gds.py", "interconnect_manifest")],
         page="tools/06_interconnect_pdk"),
    dict(name="Interconnect 3D body per method", owner="interconnect",
         path="libs.tech/chiplet_studio/stackup_fragments",
         readers=[("studio", "src/core/LayerStackup.cpp")],
         page="tools/06_interconnect_pdk"),
    dict(name="Interposer technology package", owner="interposer", path="libs.tech/adk/technology.json",
         schema=("spec", "schemas/technology_package.schema.json"), version="schema_version",
         readers=[("spec", "reference/python/chiplet_format_io/technology_package.py"),
                  ("interposer-pnr", "tests/test_descriptor_package_copies.py")],
         note="A test in interposer-pnr holds its descriptor copies to the package.",
         page="tools/05_openintm4tm2"),
    dict(name="Interposer routing descriptors", owner="interposer", path="libs.tech/adk/routing",
         schema=("interposer-pnr", "src/interposer_pnr/schema/interposer_routing_tech.schema.json"),
         version="schema_version",
         version_file="libs.tech/adk/routing/ihp_sg13g2_intm4tm2.routing_tech.json",
         readers=[("interposer-pnr", "tests/test_descriptor_package_copies.py", "ihp_sg13g2_intm4tm2")],
         note="At this release interposer-pnr routes from its own copy, which that test holds byte-equal to these.",
         page="tools/05_openintm4tm2"),
    dict(name="Interposer stack: substrate, metals, attach plane", owner="interposer",
         path="libs.tech/intm4tm2_stack.json", version="schema_version",
         readers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py"),
                  ("tools", "ci/check_attach_plane.py"),
                  ("tools", "Dockerfile"),
                  ("interposer-pnr", "src/interposer_pnr/sources.py"),
                  ("packaging-flow", "src/packaging_flow/engine.py")],
         page="tools/05_openintm4tm2"),
    dict(name="Interposer DRC rule values", owner="interposer",
         path="libs.tech/klayout/tech/drc/rule_decks/interposer_tech_default.json", version="version",
         readers=[("tools", "bin/adk-verify-carrier-drc"),
                  ("plugin", "plugins/chiplet_export/hyp_to_gds.py", "interposer_tech_default"),
                  ("packaging-flow", "profiles/intm4tm2_wire_bond_v0.json")],
         note="The plugin reads it only when given ``--tech-json``; a normal export uses its built-in values.",
         page="tools/05_openintm4tm2"),
    dict(name="Interposer layer sheet", owner="interposer", path="libs.tech/klayout/tech/intm4tm2.lyp",
         readers=[("plugin", "plugins/chiplet_export/layer_map.py"),
                  ("packaging-flow", "profiles/intm4tm2_wire_bond_v0.json")],
         page="tools/05_openintm4tm2"),
    dict(name="Interposer KLayout technology", owner="interposer", path="libs.tech/klayout/tech/intm4tm2.lyt",
         readers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py")],
         page="tools/05_openintm4tm2"),
    dict(name="Interposer pycell technology values", owner="interposer",
         path="libs.tech/klayout/python/intm4tm2_pycell_lib/intm4tm2_tech.json",
         readers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py")],
         page="tools/05_openintm4tm2"),
    dict(name="Interposer bump mirror", owner="interposer", path="libs.tech/klayout/python/bump_mirror.py",
         readers=[("plugin", "plugins/chiplet_export/layer_map.py", "bump_mirror"),
                  ("plugin", "plugins/chiplet_export/hyp_to_gds.py", "bump_mirror")],
         page="tools/05_openintm4tm2"),
    dict(name="Interposer fill closure", owner="interposer", path="libs.tech/klayout/python/fill_closure.py",
         readers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py", "fill_closure")],
         page="flow/05_hyp_to_gds"),
    dict(name="Interposer KiCad board templates", owner="interposer", path="libs.tech/kicad",
         readers=[("tools", "ci/check_kicad_templates.py"),
                  ("interposer-pnr", "src/interposer_pnr/sources.py")],
         needle="interposer_template", page="flow/03_interposer_design"),
    dict(name="Layer sheets for the GDS to KiCad conversion", owner="gds2kicad", path="pdks",
         readers=[("tools", "bin/adk-verify-chiplet-artifacts"),
                  ("studio", "scripts/run-gate.sh")],
         needle="sg13g2.lyp", page="tools/03_gds2kicad"),
]

# Per-design files: one is written for each die or assembly and read downstream.
# A row without a schema says in schema_text what stands in for one; a row whose
# file has no fixed name says in file_text how it is named. page_needle is what
# the linked page must name when it names the datum some other way.
DESIGN = [
    dict(name="Assembly", file="<name>.chiplet", schema=("spec", "schemas/chiplet.schema.json"),
         writers=[("plugin", "plugins/chiplet_export/writers/chiplet_writer.py"),
                  ("plugin", "plugins/chiplet_export/hyp_to_gds.py"),
                  ("studio", "src/formats/ChipletFormat.cpp"),
                  ("interposer-pnr", "src/interposer_pnr/analyses/escape/coupon.py")],
         readers=[("adk", "checks/assembly_admission.py", "--chiplet"), ("studio", "src/formats/ChipletFormat.cpp"),
                  ("plugin", "plugins/chiplet_export/hyp_to_gds.py"),
                  ("packaging-flow", "src/packaging_flow/cli.py"),
                  ("interposer-pnr", "src/interposer_pnr/ir.py")],
         needle=".chiplet", page="formats/01_chiplet"),
    dict(name="Die contract", file="die-contract.json", schema=("spec", "schemas/die_contract.schema.json"),
         writers=[("chiplet-flow", "src/chiplet_die_flow/emit_ready_die.py")],
         readers=[("adk", "checks/assembly_admission.py", "chiplet_format_io.die_contract"),
                  ("packaging-flow", "src/packaging_flow/ready_die.py")],
         page="tools/12_chiplet_flow"),
    dict(name="Pin list", file_text="``<die>.pins.json``, or ``<name>_pins.json`` by gds2kicad's default", schema=("spec", "schemas/pins.schema.json"),
         writers=[("gds2kicad", "footprint_to_pinlist.py"), ("chiplet-flow", "src/chiplet_die_flow/plans.py"),
                  ("plugin", "plugins/chiplet_export/writers/chiplet_writer.py", "write_die_pin_lists"),
                  ("interposer-pnr", "src/interposer_pnr/analyses/escape/coupon.py")],
         readers=[("adk", "openroad/chiplet2dbx.py"), ("interposer", "libs.tech/klayout/python/bump_mirror.py"),
                  ("gds2kicad", "gds_to_kicad_symbol.py"), ("gds2kicad", "gds_to_kicad.py"),
                  ("gds2kicad", "chiplet_to_kicad_sch.py"),
                  ("plugin", "plugins/chiplet_export/hyp_to_gds.py", "--pad-locations"),
                  ("tools", "bin/adk-verify-chiplet-artifacts"), ("tools", "openroad/check-3dblox.sh"),
                  ("interposer-pnr", "src/interposer_pnr/pads.py")],
         needle="pins.json", page="formats/07_pin_lists"),
    dict(name="Boundary manifest", file="<gds-stem>.boundaries.json",
         schema=("spec", "schemas/boundary_manifest.schema.json"),
         writers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py"), ("gds2kicad", "blackbox_chiplet.py")],
         readers=[("adk", "klayout/drc/run_drc.py"), ("tools", "bin/adk-verify-demo-reproducible"),
                  ("plugin", "plugins/chiplet_export/pipeline/orchestrator.py"),
                  ("packaging-flow", "src/packaging_flow/stages.py")],
         needle=".boundaries.json", page="formats/04_boundary_manifest"),
    dict(name="Pillar manifest", file="<gds-stem>.pillars.json",
         schema=("adk", "config/schema/pillar_manifest.schema.json"),
         writers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py")],
         readers=[("adk", "checks/pads_vs_pillars.py", "pillars.json"), ("tools", "bin/adk-verify-carrier-drc"),
                  ("packaging-flow", "src/packaging_flow/stages.py", "pillars.json")],
         needle=".pillars.json", page="formats/05_pillar_manifest"),
    dict(name="Interconnect methods in use", file="<gds-stem>.ixn_methods.json",
         schema=("adk", "config/schema/ixn_methods.schema.json"),
         writers=[("plugin", "plugins/chiplet_export/pipeline/orchestrator.py")],
         readers=[("adk", "klayout/drc/run_drc.py"), ("tools", "bin/adk-verify-demo-reproducible"),
                  ("packaging-flow", "src/packaging_flow/stages.py")],
         needle="ixn_methods", page="formats/06_ixn_methods"),
    dict(name="Interposer external pads", file="io_pads.json", schema=("spec", "schemas/io_pads.schema.json"),
         writers=[("gds2kicad", "io_pads/kicad_pcb_to_iopads.py"),
                  ("plugin", "plugins/chiplet_export/writers/chiplet_writer.py"),
                  ("interposer-pnr", "src/interposer_pnr/io_pads.py")],
         writer_note="The plugin's file holds only the ``io_pads`` list, without the ``schema``, "
                     "``version`` and ``frame`` keys the schema requires.",
         readers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py")],
         needle="io_pads.json", page="tools/03_gds2kicad"),
    dict(name="Pad domains of a die footprint", file_text="the ``CHIPLET_PAD_DOMAINS`` footprint property",
         schema_text="none; format ``chiplet_kicad.pad_domains``",
         writers=[("interposer-pnr", "src/interposer_pnr/pad_domains.py")],
         readers=[("plugin", "plugins/chiplet_export/pad_domains.py")],
         needle="CHIPLET_PAD_DOMAINS", page="tools/02_chiplet_export_plugin"),
    dict(name="No-fill regions", file_text="the path given to ``--nofill-regions``", schema_text="none",
         writers=[("interposer", "libs.tech/parasitics/routed_load.py"),
                  ("plugin", "plugins/chiplet_export/writers/chiplet_writer.py")],
         readers=[("plugin", "plugins/chiplet_export/hyp_to_gds.py"),
                  ("packaging-flow", "src/packaging_flow/fill_keepout.py")],
         needle="nofill", page="tools/02_chiplet_export_plugin"),
    dict(name="Die layouts", file="die_layouts.json", schema_text="none",
         writers=[("packaging-flow", "src/packaging_flow/stages.py"),
                  ("packaging-flow", "src/packaging_flow/runner.py", "_write_die_layouts")],
         readers=[("plugin", "plugins/chiplet_export/pipeline/orchestrator.py", "die_layouts_json")],
         page="tools/02_chiplet_export_plugin", page_needle="die_layouts_json"),
    dict(name="Connectivity form of a generated sheet", file_text="the path given to ``kicad_sch_to_connectivity.py``",
         schema_text="none; format ``chiplet_system.connectivity``",
         writers=[("gds2kicad", "kicad_sch_to_connectivity.py")],
         readers=[("packaging-flow", "src/packaging_flow/sheet_form.py")],
         needle="chiplet_system.connectivity", page="tools/03_gds2kicad"),
    dict(name="Interposer export report", file_text="the path given to ``interposer-pnr export --report``",
         schema_text="none; format ``interposer_pnr.export``",
         writers=[("interposer-pnr", "src/interposer_pnr/cli.py", "--report")],
         readers=[("gds2kicad", "io_pads/kicad_pcb_to_iopads.py", "--export-report"),
                  ("plugin", "plugins/chiplet_export/draft_net_names.py", "export_report")],
         needle="interposer_pnr.export", page="tools/02_chiplet_export_plugin"),
    dict(name="Assembly LVS report", file_text="``<input-stem>.lvs.json``, or the path given to ``--report``",
         schema_text="none",
         writers=[("assembly-lvs", "src/assembly_lvs/cli.py")],
         readers=[("packaging-flow", "src/packaging_flow/assembly_gate.py", "assembly_lvs.json"),
                  ("packaging-flow", "src/packaging_flow/assembly_bundle.py", "REPORT_REL")],
         needle=".lvs.json", page="tools/09_assembly_lvs"),
]

# Release data: what holds the repositories together in one image.
RELEASE = [
    dict(name="Pin set: every repository and tool the image is built from", owner="tools",
         path="ci/pin-set.json", version="schema",
         readers=[("interposer-pnr", "tests/test_tools_manifest.py"),
                  ("packaging-flow", "tests/conftest.py"),
                  ("assembly-lvs", ".github/workflows/host-tier.yml"),
                  ("chiplet-cosim", ".github/workflows/host-tier.yml")],
         page="tools/07_adk_tools_image"),
    dict(name="Staged sources: the commits the image stages", owner="tools", path="staging.pin",
         readers=[], note="This site's version matrix.",
         page="tools/07_adk_tools_image"),
    dict(name="Die views: records the image stages, by layout digest", owner="tools",
         path="die-views.sha256",
         readers=[], note="The image build, from an adk-examples checkout.",
         page="tools/07_adk_tools_image"),
    dict(name="Contract registry: the copies and pins checked across repositories", owner="tools",
         path=REGISTRY, version="registry_version",
         readers=[], note="ADK-Tools' contract gate.",
         page="formats/00_shared_data"),
]

# Copies the contract registry does not list, each with the file that holds it
# to the owner's. A path may name sibling files as a{b,c}d. "also" names
# further files that must still name the copy, such as the build step that
# runs the check; "more" adds a second check, as (how, (key, file, needle));
# "after" is a closing clause that names no check.
COPIES = [
    dict(owner="interposer", path="libs.tech/adk/routing/ihp_sg13g2_intm4tm2{,_rdl2}.routing_tech.json",
         copy=("interposer-pnr", "src/interposer_pnr/descriptors/ihp_sg13g2_intm4tm2{,_rdl2}.routing_tech.json"),
         check=("interposer-pnr", "tests/test_descriptor_package_copies.py", "SHIPPED_PREFIX"),
         how="byte for byte, against the sha256 ``technology.json`` states"),
    dict(owner="interposer", path="libs.tech/chiplet_studio/intm4tm2.stackup.yaml",
         copy=("studio", "tests/fixtures/intm4tm2.stackup.yaml"),
         check=("tools", "ci/check_attach_plane.py", "tests/fixtures/intm4tm2.stackup.yaml"),
         how="byte for byte"),
    dict(owner="interposer", path="libs.tech/chiplet_studio/intm4tm2.stackup.yaml",
         copy=("studio", "configs/stackups/intm4tm2.yaml"),
         check=("tools", "ci/check_attach_plane.py", "render_only"),
         how="layer by layer, matched on GDS layer and datatype (name with Studio's renames, purpose, "
             "z, height), with any layer only Studio has marked ``render_only`` and "
             "``attachment_surface_z`` equal to the plane in ``libs.tech/intm4tm2_stack.json``"),
    dict(owner="interposer", path="libs.tech/intm4tm2_stack.json",
         copy=("plugin", "plugins/chiplet_export/tests/fixtures/intm4tm2_pdk/libs.tech/intm4tm2_stack.json"),
         check=("tools", "ci/check_attach_plane.py", "fixtures/intm4tm2_pdk/"),
         how="byte for byte"),
    dict(owner="interposer", path="libs.tech/intm4tm2_stack.json",
         copy=("spec", "description/tests/fixtures/interposer_pdk/libs.tech/intm4tm2_stack.json"),
         check=("tools", "ci/check_attach_plane.py", "--pdk-copy"),
         also=[("tools", "Dockerfile", "--pdk-copy chiplet-spec/description=")],
         how="byte for byte, at image build"),
    dict(owner="interposer", path="libs.tech/intm4tm2_stack.json",
         copy=("packaging-flow", "tests/fixtures/interposer_pdk/libs.tech/intm4tm2_stack.json"),
         check=("tools", "ci/check_attach_plane.py", "--pdk-copy"),
         also=[("tools", "Dockerfile", "--pdk-copy packaging-flow=")],
         how="byte for byte, at image build"),
    dict(owner="interposer", path="libs.tech/intm4tm2_stack.json",
         copy=("interposer-pnr", "tests/data/frozen/interposer_pdk/libs.tech/intm4tm2_stack.json"),
         check=("tools", "ci/check_attach_plane.py", "--pdk-copy"),
         also=[("tools", "Dockerfile", "--pdk-copy interposer-pnr=")],
         how="byte for byte, at image build"),
    dict(owner="interposer", path="libs.tech/kicad/interposer_template.{kicad_dru,kicad_pro}",
         copy=("packaging-flow", "tests/fixtures/interposer_pdk/libs.tech/kicad/interposer_template.{kicad_dru,kicad_pro}"),
         check=("tools", "ci/check_kicad_templates.py", "interposer_template"),
         also=[("tools", "Dockerfile", "--copy packaging-flow=")],
         how="byte for byte, at image build"),
    dict(owner="interposer", path="libs.tech/kicad/interposer_template.{kicad_dru,kicad_pro}",
         copy=("interposer-pnr", "tests/data/frozen/interposer_pdk/libs.tech/kicad/interposer_template.{kicad_dru,kicad_pro}"),
         check=("tools", "ci/check_kicad_templates.py", "interposer_template"),
         also=[("tools", "Dockerfile", "--copy interposer-pnr=")],
         how="byte for byte, at image build"),
    dict(owner="interposer", path="libs.tech/adk/technology.json",
         copy=("spec", "conformance/fixtures/technology_package/intm4tm2/libs.tech/adk/technology.json"),
         check=("spec", "conformance/test_technology_package_intm4tm2.py", "provenance.json"),
         how="a snapshot held to the release its ``provenance.json`` records",
         after="not kept equal to this pin"),
    dict(owner="spec", path="reference/cpp/",
         copy=("studio", "src/formats/chiplet_format_io/"),
         check=("studio", "ci/check_vendored.py", "VENDORED.md"),
         how="held to the content digest its ``VENDORED.md`` records",
         after="that check does not compare it with the owner's files"),
    dict(owner="spec", path="reference/python/chiplet_format_io/",
         copy=("gds2kicad", "_vendor/chiplet_format_io/"),
         check=("gds2kicad", "tests/test_vendored_reader.py", "chiplet_format_io.SOURCE"),
         how="byte for byte, against the files and digests ``_vendor/chiplet_format_io.SOURCE`` records",
         also=[("tools", "Dockerfile", "--copy /opt/adk-tools/gds_to_kicad/_vendor/chiplet_format_io")],
         more=[("and at image build, file by file against the staged owner's reader",
                ("tools", "ci/check_vendored_reader.py", "--reference"))]),
    dict(owner="spec", path="reference/python/chiplet_format_io/{__init__,footprint_ids}.py",
         copy=("interposer-pnr", "src/interposer_pnr/_vendor/chiplet_format_io/{__init__,footprint_ids}.py"),
         check=("interposer-pnr", "tests/test_sheet_form.py", "chiplet_format_io.SOURCE"),
         how="byte for byte, against the digests ``_vendor/chiplet_format_io.SOURCE`` records",
         also=[("tools", "Dockerfile", "--copy interposer-pnr/src/interposer_pnr/_vendor/chiplet_format_io")],
         more=[("and at image build, file by file against the staged owner's reader",
                ("tools", "ci/check_vendored_reader.py", "--reference"))]),
    dict(owner="interposer-pnr", path="src/interposer_pnr/round_trip_names.py",
         copy=("plugin", "plugins/chiplet_export/vendor/round_trip_names.py"),
         check=("plugin", "plugins/chiplet_export/tests/test_vendored_copies.py", "round_trip_names.SOURCE"),
         how="byte for byte, against the digest ``vendor/round_trip_names.SOURCE`` records",
         after="nothing compares it with the owner's file"),
    dict(owner="interposer-pnr", path="src/interposer_pnr/round_trip_names.py",
         copy=("packaging-flow", "src/packaging_flow/_vendor/round_trip_names.py"),
         check=("packaging-flow", "tests/test_vendored_copies.py", "SOURCE"),
         how="byte for byte, against the digest ``_vendor/round_trip_names.SOURCE`` records",
         after="nothing compares it with the owner's file"),
    dict(owner="spec", path="conformance/fixtures/top_level_blocks_cases.json",
         copy=("plugin", "plugins/chiplet_export/tests/fixtures/top_level_blocks_cases.json"),
         check=("plugin", "plugins/chiplet_export/tests/test_top_level_block_grammar.py", "spec_blob_at_pin"),
         how="byte for byte, against the sha256 the test pins, which it also checks the owner's file at the "
             "pinned commit against when a chiplet-system-spec checkout is present"),
    dict(owner="interposer-pnr", path="src/interposer_pnr/round_trip_names.py",
         copy=("gds2kicad", "_vendor/round_trip_names.py"),
         check=("gds2kicad", "tests/test_vendored_reader.py", "round_trip_names.SOURCE"),
         how="byte for byte, against the digest ``_vendor/round_trip_names.SOURCE`` records",
         after="nothing compares it with the owner's file"),
]


class Trees:
    """Reads files at the pinned commit of each repository.

    A staged engine with no checkout holding its commit is unchecked: its rows
    are written without reading it. With STAGE_SIBLINGS set, as for a release
    regeneration, every engine must be checked.
    """

    def __init__(self):
        for path, _ in PUBLIC.values():
            require_submodule(path, "src/" + os.path.basename(path))
        self.commits = {key: pinned_commit(path, "src/" + os.path.basename(path))
                        for key, (path, _) in PUBLIC.items()}
        self.paths = {key: path for key, (path, _) in PUBLIC.items()}
        record = read_json(STAGED_RECORD)
        siblings = stage_siblings()
        self.unchecked = set()
        for key in ENGINES:
            if key not in record:
                fail("{} records no {}".format(os.path.relpath(STAGED_RECORD, REPO_ROOT), key))
            path, ref = os.path.join(siblings, key), record[key]["ref"]
            code = run_git(path, "cat-file", "-e", ref + "^{commit}")[0] if os.path.isdir(path) else 1
            if code == 0:
                self.commits[key], self.paths[key] = ref, path
            else:
                self.unchecked.add(key)
        # All engines or none: a partial set would publish some rows checked
        # and others not, with nothing on the page to tell them apart.
        partial = self.unchecked and len(self.unchecked) < len(ENGINES)
        if self.unchecked and (partial or os.environ.get("STAGE_SIBLINGS")):
            fail("{} holds no checkout of {} at its staged commit; check all staged engines or "
                 "none".format(siblings, ", ".join(sorted(self.unchecked))))

    def name(self, key):
        return PUBLIC[key][1] if key in PUBLIC else key

    def has(self, key, path):
        return run_git(self.paths[key], "cat-file", "-e", "{}:{}".format(self.commits[key], path))[0] == 0

    def text(self, key, path):
        if key in self.unchecked:
            fail("{} is read for {} but has no checkout here".format(key, path))
        return git_text(self.paths[key], "show", "{}:{}".format(self.commits[key], path))


def expand(path):
    """``a{b,c}d`` names ``abd`` and ``acd``; any other path names itself."""
    match = re.search(r"\{([^}]*)\}", path)
    if not match:
        return [path]
    return [path[:match.start()] + part + path[match.end():] for part in match.group(1).split(",")]


def require(trees, key, path, what):
    if key in trees.unchecked:
        return
    for one in expand(path):
        if not trees.has(key, one.rstrip("/")):
            fail("{}: {} has no {} at {}".format(what, trees.name(key), one, trees.commits[key][:12]))


def names(trees, key, path, needle, what):
    """Fail unless the file still names the datum."""
    require(trees, key, path, what)
    if key not in trees.unchecked and needle not in trees.text(key, path):
        fail("{}: {} {} no longer names {!r} at {}; update the row".format(
            what, trees.name(key), path, needle, trees.commits[key][:12]))


def page_names(row, needle):
    page = os.path.join(DOCS_DIR, row["page"] + ".rst")
    if needle not in read_text(page):
        fail("{}: {} does not name {!r}; link a page that documents it".format(row["name"], row["page"], needle))


def file_cell(trees, key, path):
    return "``{}`` in {}".format(path, trees.name(key))


def version_cell(trees, row):
    if not row.get("version"):
        return "the owner's release tag"
    data = json.loads(trees.text(row["owner"], row.get("version_file", row["path"])))
    if row["version"] not in data:
        fail("{}: {} has no {} key".format(row["name"], row.get("version_file", row["path"]), row["version"]))
    return "``{}`` {}".format(row["version"], data[row["version"]])


def people_cell(trees, row, role):
    """The repositories, then the role's note (note for readers, writer_note
    for writers), a sentence of its own."""
    cell = ", ".join(sorted({trees.name(entry[0]) for entry in row.get(role, [])}, key=str.lower))
    note = row.get("note" if role == "readers" else "writer_note")
    if note:
        cell = "{}. {}".format(cell, note) if cell else note
    return cell or "none"


def check_people(trees, row, role, needle):
    for entry in row.get(role, []):
        names(trees, entry[0], entry[1], entry[2] if len(entry) > 2 else needle, row["name"])


def registry_artifacts(trees):
    registry = json.loads(trees.text("tools", REGISTRY))
    for artifact in registry["artifacts"]:
        for key in [artifact["owner"]] + [entry[0] for kind in ("mirrors", "checked_elsewhere", "consumers")
                                          for entry in artifact.get(kind, [])]:
            if key not in PUBLIC:
                fail("{} names repository {!r}, which this page does not map".format(REGISTRY, key))
    return registry["artifacts"]


def with_registry_readers(row, artifacts):
    """The row's readers plus the consumers the registry lists for its file."""
    readers = list(row.get("readers", []))
    listed = {(entry[0], entry[1]) for entry in readers}
    for artifact in artifacts:
        if (artifact["owner"], artifact["path"]) != (row["owner"], row["path"]):
            continue
        for key, path in (entry[:2] for entry in artifact.get("consumers", [])):
            if (key, path) not in listed:
                readers.append((key, path))
                listed.add((key, path))
    return dict(row, readers=readers)


def published_rows(trees, rows, artifacts):
    out = []
    for row in rows:
        row = with_registry_readers(row, artifacts)
        needle = row.get("needle") or os.path.basename(row["path"].rstrip("/"))
        require(trees, row["owner"], row["path"], row["name"])
        schema = row.get("schema")
        if schema:
            require(trees, schema[0], schema[1], row["name"])
        check_people(trees, row, "readers", needle)
        page_names(row, needle)
        out.append([row["name"], file_cell(trees, row["owner"], row["path"]),
                    file_cell(trees, *schema) if schema else "none",
                    version_cell(trees, row), people_cell(trees, row, "readers"),
                    ":doc:`/{}`".format(row["page"])])
    return out


def design_rows(trees):
    out = []
    for row in DESIGN:
        if not (row.get("needle") or row.get("file")):
            fail("{}: a row with file_text needs a needle".format(row["name"]))
        needle = row.get("needle") or row["file"]
        file = "``{}``".format(row["file"]) if "file" in row else row["file_text"]
        schema = row.get("schema")
        if schema:
            require(trees, schema[0], schema[1], row["name"])
        check_people(trees, row, "writers", needle)
        check_people(trees, row, "readers", needle)
        page_names(row, row.get("page_needle", needle))
        out.append([row["name"], file,
                    file_cell(trees, *schema) if schema else row["schema_text"],
                    people_cell(trees, row, "writers"), people_cell(trees, row, "readers"),
                    ":doc:`/{}`".format(row["page"])])
    return out


def copy_rows(trees, artifacts):
    out = []
    for artifact in artifacts:
        if artifact.get("checked_elsewhere"):
            fail("{}: {} lists copies another suite checks; this page has no wording for them yet".format(
                REGISTRY, artifact["id"]))
        for key, path in (entry[:2] for entry in artifact.get("mirrors", [])):
            if artifact.get("identity") != "bytes":
                fail("{}: {} mirrors by {!r}; this page has no wording for it".format(
                    REGISTRY, artifact["id"], artifact.get("identity")))
            require(trees, artifact["owner"], artifact["path"], artifact["id"])
            require(trees, key, path, artifact["id"])
            out.append([file_cell(trees, artifact["owner"], artifact["path"]), file_cell(trees, key, path),
                        "byte for byte, by ADK-Tools' contract gate"])
    for row in COPIES:
        more = row.get("more", [])
        for key, path, needle in [row["check"]] + row.get("also", []) + [check for _, check in more]:
            names(trees, key, path, needle, row["path"])
        require(trees, row["owner"], row["path"], row["path"])
        require(trees, row["copy"][0], row["copy"][1], row["path"])
        how = "; ".join("{}, by ``{}`` in {}".format(text, check[1], trees.name(check[0]))
                        for text, check in [(row["how"], row["check"])] + more)
        if row.get("after"):
            how = "{}; {}".format(how, row["after"])
        out.append([file_cell(trees, row["owner"], row["path"]), file_cell(trees, *row["copy"]), how])
    return out


#: the keys a row of each table may carry; any other key is a typo
KEYS = {
    "published": {"name", "owner", "path", "schema", "version", "version_file", "readers", "note",
                  "needle", "page"},
    "design": {"name", "file", "file_text", "schema", "schema_text", "writers", "writer_note", "readers",
               "needle", "page", "page_needle"},
    "copies": {"owner", "path", "copy", "check", "also", "more", "how", "after"},
}


def check_keys():
    for table, rows in (("published", PUBLISHED + RELEASE), ("design", DESIGN), ("copies", COPIES)):
        for row in rows:
            unknown = set(row) - KEYS[table]
            if unknown:
                fail("{} row {!r} has unknown keys {}".format(table, row.get("name", row.get("path")),
                                                              ", ".join(sorted(unknown))))


def check_consumers_placed(artifacts):
    """Every registry consumer must land in a row, or the page silently drops it."""
    placed = {(row["owner"], row["path"]) for row in PUBLISHED + RELEASE}
    for artifact in artifacts:
        if artifact.get("consumers") and (artifact["owner"], artifact["path"]) not in placed:
            fail("{}: {} lists consumers of {} {}, which no row names".format(
                REGISTRY, artifact["id"], artifact["owner"], artifact["path"]))


def main():
    check_keys()
    trees = Trees()
    artifacts = registry_artifacts(trees)
    check_consumers_placed(artifacts)
    write_csv(os.path.join(OUT, "shared_published.csv"), published_rows(trees, PUBLISHED, artifacts))
    write_csv(os.path.join(OUT, "shared_design.csv"), design_rows(trees))
    write_csv(os.path.join(OUT, "shared_release.csv"), published_rows(trees, RELEASE, artifacts))
    write_csv(os.path.join(OUT, "shared_copies.csv"), copy_rows(trees, artifacts))
    for key in sorted(trees.unchecked):
        print("gen_shared_data: no checkout of {} at its staged commit; its rows are written "
              "unchecked".format(key))


if __name__ == "__main__":
    main()
