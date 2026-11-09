#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the cross-repository version and schema matrices.

The ecosystem versions on several unrelated axes: the ADK carries a semantic
VERSION, ADK-Tools tags calendar releases, the chiplet format carries its own
format_version, and each manifest schema is pinned independently. Nothing in
the source repositories relates them, so this table is the only place the
relationship is written down, and it is derived rather than typed.

The flow engines ADK-Tools stages are not submodules here: their commits come
from the pinned ADK-Tools ``staging.pin``, and each version from the
``pyproject.toml`` at that commit in a sibling checkout (beside this
repository, or in the directory ``STAGE_SIBLINGS`` names, as for ADK-Tools
itself). The pinned commits are local-only, so a build without the sibling
checkouts (CI, Read the Docs) reuses the version recorded for that exact commit
in ``tools/tables/staged_engines.json`` and fails when staging.pin has moved
past it. That record is a reviewed input, not proof: only a run with the
sibling checkouts verifies it, and the script prints which source each
version came from.
"""

import glob
import json
import os
import re
import tomllib

from _common import (
    ADK,
    DOCS_DIR,
    GENERATED_BANNER,
    INTERCONNECT,
    INTERPOSER,
    REPO_ROOT,
    SPEC,
    SRC_DIR,
    TOOLS,
    fail,
    git,
    git_or_fail,
    pinned_commit,
    run_git,
    release_tags,
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


STAGING_PIN = os.path.join(TOOLS, "staging.pin")
STAGED_RECORD = os.path.join(DOCS_DIR, "tools", "tables", "staged_engines.json")
# staging.pin keeps every assignment a plain literal on one line, because
# ADK-Tools' own checks match some of them as whole lines.
STAGE_ASSIGNMENT = re.compile(r"^STAGE_([A-Z0-9_]+)_(PATH|REF)=(.*)$")
STAGE_VALUE = {"PATH": re.compile(r"[A-Za-z0-9._-]+"), "REF": re.compile(r"[0-9a-f]{40}")}


def staged_trees():
    """(path, ref) of every tree staging.pin stages, in file order."""
    assigned = {"PATH": {}, "REF": {}}
    for line in read_text(STAGING_PIN).splitlines():
        match = STAGE_ASSIGNMENT.match(line)
        if not match:
            continue
        tree, kind, value = match.groups()
        if not STAGE_VALUE[kind].fullmatch(value):
            fail("staging.pin: cannot read {!r}".format(line))
        if tree in assigned[kind]:
            fail("staging.pin assigns STAGE_{}_{} twice".format(tree, kind))
        assigned[kind][tree] = value
    paths, refs = assigned["PATH"], assigned["REF"]
    if not paths or set(paths) != set(refs):
        fail("staging.pin: every STAGE_*_PATH needs one STAGE_*_REF and back")
    return [(paths[key], refs[key]) for key in paths]


def is_submodule(path):
    """Whether this repository pins src/<path> as a submodule."""
    entry = git_or_fail(REPO_ROOT, "ls-files", "--stage", "--", "src/" + path)
    return entry.startswith("160000 ")


def engine_identity(siblings, path, ref):
    """Distribution name and version at ref in the sibling checkout of path,
    or None when there is no such checkout holding that commit."""
    clone = os.path.join(siblings, path)
    if not os.path.isdir(clone):
        return None
    code, _, _ = run_git(clone, "cat-file", "-e", ref + "^{commit}")
    if code != 0:
        return None
    project = tomllib.loads(git_or_fail(clone, "show", ref + ":pyproject.toml")).get("project", {})
    name, version = project.get("name"), project.get("version")
    if not isinstance(name, str) or not isinstance(version, str) or not name or not version:
        fail("{} at {} has no [project] name and version".format(clone, ref[:12]))
    return {"distribution": name, "version": version}


def staged_engines():
    """Every staged tree that is not a submodule here, with its version.

    Read from the sibling checkouts when they hold the pinned commit, else
    taken from the record, which must then be for the same commit. A version
    taken from the record is not verified, so each one says where it came
    from. A staged tree that is a submodule here must be staged at the commit
    this repository pins, or the matrix would describe a tree the image does
    not ship.
    """
    require_submodule(TOOLS, "src/ADK-Tools")
    siblings = os.environ.get("STAGE_SIBLINGS") or os.path.dirname(REPO_ROOT)
    record = read_json(STAGED_RECORD) if os.path.isfile(STAGED_RECORD) else {}
    engines = {}
    for path, ref in staged_trees():
        if is_submodule(path):
            pinned = pinned_commit(os.path.join(SRC_DIR, path), "src/" + path)
            if pinned != ref:
                fail("staging.pin stages {} at {}, but this repository pins src/{} at {}. "
                     "Move the two pins together".format(path, ref[:12], path, pinned[:12]))
            continue
        identity = engine_identity(siblings, path, ref)
        if identity is None:
            kept = record.get(path, {})
            if kept.get("ref") != ref:
                fail(
                    "staging.pin stages {} at {}, but {} records its version for {}. "
                    "Rerun with a checkout of {} that has the commit, beside this "
                    "repository or in STAGE_SIBLINGS".format(
                        path, ref[:12], os.path.relpath(STAGED_RECORD, REPO_ROOT),
                        (kept.get("ref") or "no commit")[:12], path))
            identity = {key: kept[key] for key in ("distribution", "version")}
            source = "the record (unverified: no sibling checkout holds the commit)"
        else:
            source = "pyproject.toml in {}".format(os.path.join(siblings, path))
        print("staged {} {} at {}: version {} from {}".format(
            path, identity["distribution"], ref[:12], identity["version"], source))
        engines[path] = dict(ref=ref, **identity)
    if not engines:
        fail("staging.pin stages no tree outside this repository's submodules")
    return engines


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
        commit = git(path, "rev-parse", "--short", "HEAD")
        # A repo without a VERSION file versions by release tag when it is
        # pinned exactly at one, and by commit otherwise: a pin past a release
        # is not that release. Release tags are v-prefixed (RELEASE_TAG_GLOB).
        if not version:
            tags = release_tags(path)
            version = ", ".join(sorted(tags)) if tags else "by commit"
        rows.append([name, role, license_id, version, commit])
    write_csv(os.path.join(DOCS_DIR, "tools", "tables", "versions.csv"), rows)

    engines = staged_engines()
    write_text(STAGED_RECORD, json.dumps(engines, indent=2, sort_keys=True) + "\n")
    write_csv(
        os.path.join(DOCS_DIR, "tools", "tables", "staged_engines.csv"),
        [[path, e["distribution"], e["version"], e["ref"][:7]] for path, e in engines.items()],
    )
    write_text(
        os.path.join(DOCS_DIR, "tools", "_staged_engines.inc"),
        GENERATED_BANNER.format(script="gen_version_matrix.py") + "\n" + "".join(
            ".. |{}-version| replace:: {}\n".format(path, e["version"])
            for path, e in engines.items()),
    )

    # Schema and format versions. These are pinned independently of any
    # repository version, and they are what a file on disk actually has to
    # match: every reader compares the file's version against a constant. The
    # sidecar readers treat a mismatch as a hard error; the .chiplet reader
    # refuses another major and warns on a higher minor. The JSON Schemas
    # themselves type the field as a plain string, so the constants in the
    # consuming modules are the authoritative pin.
    #
    # Each sidecar names its schema either by a constant in the reader or, where
    # the reader has none, by the literal it compares against, which must then
    # appear quoted in that file.
    run_drc = ("klayout", "drc", "run_drc.py")
    SIDECAR_PINS = [
        ("Chiplet boundary manifest", run_drc,
         ("literal", "adk-boundary-manifest"), "SUPPORTED_MANIFEST_VERSION"),
        ("Per-method interconnect sidecar", run_drc,
         ("literal", "adk-ixn-methods"), "SUPPORTED_IXN_METHODS_VERSION"),
        ("Pillar manifest", ("checks", "pads_vs_pillars.py"),
         ("constant", "PILLAR_MANIFEST_SCHEMA"), "SUPPORTED_PILLAR_MANIFEST_VERSIONS"),
        ("Resolved-v2 attachment sidecar", ("bridges", "assembly_lvs", "resolved_v2_entry.py"),
         ("constant", "SIDECAR_SCHEMA"), "SIDECAR_VERSION"),
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

    for title, parts, (kind, schema), version_name in SIDECAR_PINS:
        path = os.path.join(ADK, *parts)
        if kind == "constant":
            schema = constant(path, schema)
        elif not re.search(r"['\"]{}['\"]".format(re.escape(schema)), read_text(path)):
            fail("{} no longer compares against the schema {!r}".format(path, schema))
        schema_rows.append([
            title,
            "``{}``".format(schema),
            constant(path, version_name),
            "IHP-Open-ADK ``{}``".format("/".join(parts)),
        ])

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
