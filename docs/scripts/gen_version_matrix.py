#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the cross-repository version and schema matrices.

The ecosystem versions on several unrelated axes: the ADK carries a semantic
VERSION, ADK-Tools tags calendar releases, the chiplet format carries its own
format_version, and each manifest schema is pinned independently. Nothing in
the source repositories relates them, so this table is the only place the
relationship is written down, and it is derived rather than typed.
"""

import glob
import json
import os
import re
import subprocess
import tomllib

from _common import (
    ADK,
    DOCS_DIR,
    INTERCONNECT,
    INTERPOSER,
    SPEC,
    SRC_DIR,
    fail,
    read_json,
    read_text,
    require_submodule,
    write_csv,
    write_text,
)

# Repository order matches the flow, not the alphabet.
REPOSITORIES = [
    ("IHP-Open-ADK", "Assembly Design Kit", "Apache-2.0"),
    ("chiplet-system-spec", "Interchange format specification", "Apache-2.0"),
    ("OpenIntM4TM2", "Interposer PDK", "Apache-2.0"),
    ("IHP-Interconnect-IntM4TM2", "Interconnect PDK", "Apache-2.0"),
    ("KiCad-ADK-MOD", "KiCad fork", "GPL-3.0-or-later"),
    ("Chiplets-KiCad-Plugin", "KiCad chiplet export plugin", "GPL-3.0-or-later"),
    ("gds2kicad", "GDS to KiCad converter", "GPL-3.0-or-later"),
    ("chiplet-studio", "3D assembly viewer", "GPL-3.0-or-later"),
    ("ADK-Tools", "Toolchain image", "GPL-3.0-or-later"),
]

# KiCad-ADK-MOD is deliberately not a submodule of this repository: it is a
# full KiCad tree and nothing on this site is generated from it.
NOT_SUBMODULED = {"KiCad-ADK-MOD"}

# A repository renamed after its submodule was added keeps its old path under
# src/, so the path does not have to move with the name.
SUBMODULE_DIRS = {"chiplet-system-spec": os.path.basename(SPEC)}

# Repositories that release by the ``[project].version`` of their
# pyproject.toml and keep no VERSION file. Elsewhere that field is a scaffold
# value nobody moves, so it is read only where the repository bumps it.
PYPROJECT_VERSIONED = {"OpenIntM4TM2"}

# The specification repository versions by reader release; its tags are not a
# reliable source (a clone may lack them), so the reader's own number is used.
SPEC_READER = os.path.join(SPEC, "reference", "python", "chiplet_format_io", "__init__.py")


def git(repo, *args):
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def constant(path, name):
    """A string constant, or a tuple of them joined as "1.0.0, 1.1.0"."""
    match = re.search(
        r"^{}\s*[:=]\s*(\([^)]*\)|['\"][^'\"]+['\"])".format(re.escape(name)),
        read_text(path),
        re.MULTILINE,
    )
    values = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)) if match else []
    if not values:
        fail("could not read {} from {}".format(name, path))
    return ", ".join(values)


def declared_version(repo_path, from_pyproject=False):
    """The VERSION file, or for a PYPROJECT_VERSIONED repository that has none,
    ``[project].version`` of pyproject.toml, named in the cell as its source."""
    version_file = os.path.join(repo_path, "VERSION")
    if os.path.isfile(version_file):
        return read_text(version_file).strip()
    if from_pyproject:
        pyproject = os.path.join(repo_path, "pyproject.toml")
        with open(pyproject, "rb") as f:
            value = tomllib.load(f).get("project", {}).get("version")
        if not isinstance(value, str) or not value:
            fail("{} has no [project].version".format(pyproject))
        return "{} (pyproject.toml)".format(value)
    return ""


def main():
    require_submodule(ADK, "src/IHP-Open-ADK")

    rows = []
    for name, role, license_id in REPOSITORIES:
        directory = SUBMODULE_DIRS.get(name, name)
        path = os.path.join(SRC_DIR, directory)
        if name in NOT_SUBMODULED:
            rows.append([name, role, license_id, "not pinned here", ""])
            continue
        require_submodule(path, "src/" + directory)
        version = declared_version(path, name in PYPROJECT_VERSIONED)
        if name == "chiplet-system-spec":
            version = "reader " + constant(SPEC_READER, "__version__")
        described = git(path, "describe", "--tags", "--always")
        commit = git(path, "rev-parse", "--short", "HEAD")
        # A repo without a VERSION file versions by tag or by commit; say which
        # rather than leaving the cell blank.
        if not version:
            version = described if described and described != commit else "by commit"
        rows.append([name, role, license_id, version, commit])
    write_csv(os.path.join(DOCS_DIR, "tools", "tables", "versions.csv"), rows)

    # Schema and format versions. These are pinned independently of any
    # repository version, and they are what a file on disk actually has to
    # match: every reader compares the file's version against a constant. The
    # sidecar readers treat a mismatch as a hard error; the .chiplet reader
    # refuses another major and warns on a higher minor. The JSON Schemas
    # themselves type the field as a plain string, so the constants in the
    # consuming modules are the authoritative pin.
    SIDECAR_PINS = [
        (
            "Chiplet boundary manifest",
            "``adk-boundary-manifest``",
            os.path.join(ADK, "klayout", "drc", "run_drc.py"),
            "SUPPORTED_MANIFEST_VERSION",
            "IHP-Open-ADK ``klayout/drc/run_drc.py``",
        ),
        (
            "Per-method interconnect sidecar",
            "``adk-ixn-methods``",
            os.path.join(ADK, "klayout", "drc", "run_drc.py"),
            "SUPPORTED_IXN_METHODS_VERSION",
            "IHP-Open-ADK ``klayout/drc/run_drc.py``",
        ),
        (
            "Pillar manifest",
            "``adk-pillar-manifest``",
            os.path.join(ADK, "checks", "pads_vs_pillars.py"),
            "SUPPORTED_PILLAR_MANIFEST_VERSIONS",
            "IHP-Open-ADK ``checks/pads_vs_pillars.py``",
        ),
    ]

    schema_rows = []

    spec_reader = SPEC_READER
    if not os.path.isfile(spec_reader):
        fail(
            "chiplet-system-spec reference reader not found at {}. It moved or was "
            "renamed.".format(spec_reader)
        )
    schema_rows.append(
        [
            "Assembly file",
            "``.chiplet``",
            constant(spec_reader, "SUPPORTED_FORMAT_VERSION"),
            "chiplet-system-spec ``reference/python/chiplet_format_io``",
        ]
    )
    schema_rows.append(
        [
            "Source file (with a ``system`` block)",
            "``.chiplet``",
            constant(spec_reader, "SOURCE_FORMAT_VERSION"),
            "chiplet-system-spec ``reference/python/chiplet_format_io``",
        ]
    )

    for title, schema_id, path, name, source in SIDECAR_PINS:
        schema_rows.append([title, schema_id, constant(path, name), source])

    # Shared registries carry their version inline.
    for basename in ("rule_params", "interconnect", "layers", "chiplet_pads"):
        registry_path = os.path.join(ADK, "config", "{}.json".format(basename))
        if not os.path.isfile(registry_path):
            continue
        registry = read_json(registry_path)
        schema_rows.append(
            [
                "Registry",
                "``config/{}.json``".format(basename),
                str(registry.get("version", "")),
                "IHP-Open-ADK",
            ]
        )

    methods_manifest = os.path.join(INTERCONNECT, "manifest", "interconnect_methods.json")
    if os.path.isfile(methods_manifest):
        manifest = read_json(methods_manifest)
        schema_rows.append(
            [
                "Interconnect method registry",
                "``interconnect_methods.json``",
                str(manifest.get("schema_version", "")),
                "IHP-Interconnect-IntM4TM2",
            ]
        )

    write_csv(os.path.join(DOCS_DIR, "tools", "tables", "schema_versions.csv"), schema_rows)

    # Counts that older project material states incorrectly. Deriving them here
    # means the prose can cite a number without anyone having to remember to
    # recount it. Every count says exactly what it counts, because "layers" is
    # ambiguous for a technology file: named display entries, layer/datatype
    # pairs and distinct GDS layer numbers are three different figures.
    lyp_paths = sorted(
        glob.glob(os.path.join(INTERPOSER, "libs.tech", "klayout", "tech", "*.lyp"))
    )
    if not lyp_paths:
        fail(
            "no .lyp found under {}. The interposer technology moved.".format(
                os.path.join(INTERPOSER, "libs.tech", "klayout", "tech")
            )
        )
    lyp_text = read_text(lyp_paths[0])
    # <name> elements also appear in custom dither patterns and line styles, so
    # the raw count is not a layer count. The layer entries proper are the
    # <properties> blocks, each carrying one <name> and one <source>.
    named_entries = len(re.findall(r"<name>", lyp_text))
    blocks = re.findall(r"<properties>(.*?)</properties>", lyp_text, re.DOTALL)
    pairs = set()
    layer_names = set()
    for block in blocks:
        name_match = re.search(r"<name>([^<]*)</name>", block)
        if name_match:
            # Entries are named "Layer.purpose - l/d"; the layer name is the
            # part before the first dot or space.
            layer_names.add(name_match.group(1).strip().split(".")[0].split(" ")[0])
        source_match = re.search(r"<source>([^<]+)</source>", block)
        if source_match:
            match = re.match(r"\s*(\d+)/(\d+)", source_match.group(1))
            if match:
                pairs.add((int(match.group(1)), int(match.group(2))))
    gds_layers = {pair[0] for pair in pairs}
    layer_names.discard("")

    deck_dir = os.path.join(
        INTERPOSER, "libs.tech", "klayout", "tech", "drc", "rule_decks"
    )
    # layers_def.drc declares layers and density.drc is a fill check, so neither
    # is a fabrication rule deck.
    non_decks = {"layers_def.drc", "density.drc"}
    decks = [
        os.path.basename(path)
        for path in glob.glob(os.path.join(deck_dir, "*.drc"))
        if os.path.basename(path) not in non_decks
    ]
    if not decks:
        fail("no interposer rule decks found under {}".format(deck_dir))

    # Count every test function under tests/, including helpers defined in
    # conftest.py, which is what "the suite has N tests" means to a reader.
    adk_tests = 0
    adk_test_files = 0
    for root, _dirs, files in os.walk(os.path.join(ADK, "tests")):
        for name in files:
            if not name.endswith(".py"):
                continue
            found = len(re.findall(r"\bdef test_", read_text(os.path.join(root, name))))
            if found:
                adk_test_files += 1
                adk_tests += found
    if not adk_tests:
        fail("no test functions found under {}".format(os.path.join(ADK, "tests")))

    facts = ".. Generated by docs/scripts/gen_version_matrix.py. Do not edit by hand.\n\n"
    facts += ".. |interposer-lyp-entries| replace:: {}\n".format(named_entries)
    facts += ".. |interposer-layer-datatype-pairs| replace:: {}\n".format(len(pairs))
    facts += ".. |interposer-gds-layers| replace:: {}\n".format(len(gds_layers))
    facts += ".. |interposer-layer-names| replace:: {}\n".format(len(layer_names))
    facts += ".. |interposer-layer-entries| replace:: {}\n".format(len(blocks))
    facts += ".. |interposer-rule-decks| replace:: {}\n".format(len(decks))
    facts += ".. |adk-test-count| replace:: {}\n".format(adk_tests)
    facts += ".. |adk-test-files| replace:: {}\n".format(adk_test_files)
    write_text(os.path.join(DOCS_DIR, "_counts.inc"), facts)

    # The ADK vendors a copy of the chiplet-system-spec reference reader. Whether that
    # copy is currently identical to the specification is a fact readers of the
    # format page need, so derive it instead of asserting it in prose.
    vendored = os.path.join(ADK, "vendor", "chiplet_format_io", "__init__.py")
    if os.path.isfile(vendored):
        ours = constant(vendored, "__version__")
        theirs = constant(spec_reader, "__version__")
        if read_text(vendored) == read_text(spec_reader):
            state = "identical to the specification's reference reader"
        else:
            def release(version):
                return tuple(int(part) for part in version.split("."))

            if release(ours) == release(theirs):
                fail("the vendored reader and the specification's both say {} but "
                     "differ in content".format(ours))
            state = "reader {}, **{}** than the specification's reference reader ({}) at this documentation's pin".format(
                ours, "newer" if release(ours) > release(theirs) else "older", theirs)
        note = (
            ".. Generated by docs/scripts/gen_version_matrix.py. Do not edit by hand.\n\n"
            ".. |vendored-reader-state| replace:: {}\n"
            ".. |vendored-reader-formats| replace:: {}\n".format(
                state, constant(vendored, "ACCEPTED_FORMAT_VERSIONS"))
        )
        write_text(os.path.join(DOCS_DIR, "formats", "_vendored_state.inc"), note)


if __name__ == "__main__":
    main()
