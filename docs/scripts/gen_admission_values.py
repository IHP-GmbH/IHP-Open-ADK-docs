#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the values adk/10 and adk/11 quote from the ADK's own constants.

Sources, each read at its pin and never imported:

- IHP-Open-ADK ``checks/assembly_admission.py``: the strict admission
  revisions it accepts, the three component type buckets, the outcome to exit
  code mapping and the two undecidable causes;
- the specification's strict reader, chiplet-spec
  ``reference/python/chiplet_format_io/die_contract.py``: its admission
  revision, the die contract minor it accepts and the ``DieContractIncomplete``
  class;
- IHP-Open-ADK ``bridges/assembly_lvs/resolved_v2_entry.py``: the profile, the
  schema names and versions, the coordinate range, the ``assembly.id`` rule,
  the attachment roles and the exit codes;
- IHP-Open-ADK ``bridges/assembly_lvs/derive_attachment_sidecar.py``: the
  default of ``--methods-manifest``, which its ``--help`` does not print.

Some statements on the pages are prose that a value cannot carry, such as the
exit code tables and the note that ``DieContractIncomplete`` is reported as a
refusal. For those the generator checks the source still says what the page
says, and stops the build when it does not.

Writes ``docs/_admission_values.inc`` and
``docs/adk/tables/admission_types.csv``.
"""

import ast
import os
import re

from _common import (
    ADK,
    DOCS_DIR,
    GENERATED_BANNER,
    SPEC,
    fail,
    read_text,
    require_submodule,
    write_csv,
    write_text,
)

ADMISSION = os.path.join("checks", "assembly_admission.py")
ENTRY = os.path.join("bridges", "assembly_lvs", "resolved_v2_entry.py")
DERIVE = os.path.join("bridges", "assembly_lvs", "derive_attachment_sidecar.py")
READER = os.path.join("reference", "python", "chiplet_format_io", "die_contract.py")

# What the pages state about outcomes and codes, checked rather than generated.
ADMISSION_EXIT_CODES = {"ADMITTED": 0, "NOT_REQUESTED": 0, "REFUSED": 1, "UNDECIDABLE": 2}
ADMISSION_CAUSES = {"CAUSE_TOOLING": "tooling_unavailable",
                    "CAUSE_COVERAGE": "coverage_incomplete"}
ENTRY_EXIT_CODES = {"EXIT_OK": 0, "EXIT_USAGE": 1, "EXIT_REFUSED": 2}


def literal(text):
    return "``{}``".format(text)


def literal_list(items):
    """``a``, ``b`` and ``c``."""
    items = [literal(item) for item in items]
    if len(items) < 2:
        return "".join(items)
    return "{} and {}".format(", ".join(items[:-1]), items[-1])


class Module:
    """The top-level constants and functions of a Python source, read with ast."""

    def __init__(self, root, relative, label):
        self.label = "{}/{}".format(label, relative)
        self.tree = ast.parse(read_text(os.path.join(root, relative)))
        self.nodes = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.nodes[target.id] = node.value
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.nodes[node.name] = node

    def node(self, name):
        if name not in self.nodes:
            fail("{}: {} not found".format(self.label, name))
        return self.nodes[name]

    def value(self, name):
        return self.evaluate(self.node(name), name)

    def evaluate(self, node, name):
        """A literal, a frozenset of one, simple integer arithmetic, a constant name."""
        if isinstance(node, ast.Name):
            return self.value(node.id)
        if isinstance(node, ast.BinOp):
            left = self.evaluate(node.left, name)
            right = self.evaluate(node.right, name)
            ops = {ast.LShift: lambda a, b: a << b, ast.Sub: lambda a, b: a - b,
                   ast.Add: lambda a, b: a + b, ast.Mult: lambda a, b: a * b}
            if type(node.op) not in ops or not all(isinstance(v, int) for v in (left, right)):
                fail("{}: {} is not simple integer arithmetic".format(self.label, name))
            return ops[type(node.op)](left, right)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "frozenset" and len(node.args) == 1):
            return frozenset(self.evaluate(node.args[0], name))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "compile" and node.args):
            return self.evaluate(node.args[0], name)
        if isinstance(node, ast.Dict):
            return {self.evaluate(k, name): self.evaluate(v, name)
                    for k, v in zip(node.keys, node.values)}
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            items = [self.evaluate(item, name) for item in node.elts]
            return set(items) if isinstance(node, ast.Set) else tuple(items)
        try:
            return ast.literal_eval(node)
        except ValueError:
            fail("{}: {} is not a constant this generator can read".format(self.label, name))

    def function(self, name):
        node = self.node(name)
        if not isinstance(node, ast.FunctionDef):
            fail("{}: {} is not a function".format(self.label, name))
        return node


def handler_names(function):
    """The exception names each except clause of a function catches, as written."""
    caught = []
    for node in ast.walk(function):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            caught.append(ast.unparse(node.type))
    return caught


def admission_values(admission, reader):
    revisions = admission.value("SUPPORTED_REVISIONS")
    if len(revisions) != 1:
        fail("{}: SUPPORTED_REVISIONS is {}; adk/10 says the check accepts one "
             "revision".format(admission.label, sorted(revisions)))
    revision = next(iter(revisions))
    reader_revision = reader.value("STRICT_ADMISSION_API_VERSION")
    if reader_revision != revision:
        fail("{} is revision {} and the check accepts {}; adk/10 names the contract "
             "minor of the reader the check accepts".format(
                 reader.label, reader_revision, revision))
    minors = reader.value("ACCEPTED_DIE_CONTRACT_VERSIONS")
    if len(minors) != 1 or not re.match(r"^\d+\.\d+$", minors[0]):
        fail("{}: ACCEPTED_DIE_CONTRACT_VERSIONS is {}; adk/10 names one minor".format(
            reader.label, minors))
    major, minor = minors[0].split(".")

    incomplete = reader.node("DieContractIncomplete")
    if not any(isinstance(b, ast.Name) and b.id == "DieContractError"
               for b in getattr(incomplete, "bases", [])):
        fail("{}: DieContractIncomplete is no longer a DieContractError; adk/10 says "
             "it is reported as a refusal".format(reader.label))
    caught = handler_names(admission.function("admit_assembly"))
    if any("DieContractIncomplete" in name for name in caught):
        fail("{}: admit_assembly now catches DieContractIncomplete on its own; adk/10 "
             "says it is reported REFUSED".format(admission.label))
    if not any(name.endswith("DieContractError") for name in caught):
        fail("{}: admit_assembly no longer turns a DieContractError into a "
             "refusal".format(admission.label))
    if "Exception" not in handler_names(admission.function("main")):
        fail("{}: main no longer guards the whole run; adk/10 says an unexpected "
             "failure exits 2".format(admission.label))

    outcomes = {name[len("OUTCOME_"):]: admission.value(name)
                for name in admission.nodes if name.startswith("OUTCOME_")}
    codes = admission.value("EXIT_CODES")
    if set(outcomes.values()) != set(ADMISSION_EXIT_CODES) or codes != ADMISSION_EXIT_CODES:
        fail("{}: EXIT_CODES is {}; adk/10 documents {}".format(
            admission.label, codes, ADMISSION_EXIT_CODES))
    for name, value in ADMISSION_CAUSES.items():
        if admission.value(name) != value:
            fail("{}: {} is {!r}; adk/10 documents {!r}".format(
                admission.label, name, admission.value(name), value))

    admitted = admission.value("ADMITTED_TYPES")
    permitted = admission.value("PERMITTED_TYPES")
    refused = admission.value("REFUSED_TYPES")
    if not admitted or not refused or not permitted:
        fail("{}: a component type bucket is empty".format(admission.label))
    rows = [
        [literal_list(admitted), "Checked against its die contract."],
        [literal_list(permitted), "Recognized and excluded. A die contract does not "
                                  "describe them."],
        [literal_list(refused), "Refused by name. A die contract binds one layout and "
                                "one top cell, so it cannot speak for the several "
                                "instances such a component places."],
        ["anything else", "Unclassified. The assembly cannot be decided, even when "
                          "every die in it was admitted."],
    ]
    values = [
        ("admission-revision", str(revision)),
        ("admission-contract-minor", minors[0]),
        ("admission-contract-next-minor", "{}.{}".format(major, int(minor) + 1)),
        ("admission-refused-types", literal_list(refused)),
    ]
    return values, rows


def entry_values(entry):
    for name, value in ENTRY_EXIT_CODES.items():
        if entry.value(name) != value:
            fail("{}: {} is {}; adk/11 documents {}".format(
                entry.label, name, entry.value(name), value))
    stem = entry.value("OUTPUT_STEM_RE")
    match = re.match(r"^\[A-Za-z0-9\](\[[^\]]+\])\{0,(\d+)\}\\Z$", stem)
    if not match:
        fail("{}: OUTPUT_STEM_RE is {!r}; adk/11 describes a first character from "
             "[A-Za-z0-9] then a bounded run".format(entry.label, stem))
    roles = entry.value("ATTACHMENT_ROLES")
    return [
        ("entry-profile", literal(entry.value("PROFILE"))),
        ("entry-resolved-schema", literal(entry.value("RESOLVED_SCHEMA_VERSION"))),
        ("entry-sidecar-schema", literal(entry.value("SIDECAR_SCHEMA"))),
        ("entry-sidecar-version", entry.value("SIDECAR_VERSION")),
        ("entry-schema", literal(entry.value("ENTRY_SCHEMA"))),
        ("entry-version", entry.value("ENTRY_VERSION")),
        ("entry-safe-grid-coord", str(entry.value("SAFE_GRID_COORD"))),
        ("entry-id-max-length", str(int(match.group(2)) + 1)),
        ("entry-id-chars", literal(match.group(1))),
        ("entry-attachment-roles", literal_list(roles)),
    ]


def derive_values(derive):
    defaults = []
    for node in ast.walk(derive.function("main")):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument" and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "--methods-manifest"):
            defaults += [ast.literal_eval(k.value) for k in node.keywords if k.arg == "default"]
    if len(defaults) != 1 or not isinstance(defaults[0], str):
        fail("{}: no single string default for --methods-manifest".format(derive.label))
    return [("derive-methods-manifest-default", literal(defaults[0]))]


def main():
    require_submodule(ADK, "IHP-Open-ADK")
    require_submodule(SPEC, "chiplet-spec")

    admission = Module(ADK, ADMISSION, "IHP-Open-ADK")
    reader = Module(SPEC, READER, "chiplet-spec")
    entry = Module(ADK, ENTRY, "IHP-Open-ADK")
    derive = Module(ADK, DERIVE, "IHP-Open-ADK")

    values, rows = admission_values(admission, reader)
    values += entry_values(entry)
    values += derive_values(derive)

    text = GENERATED_BANNER.format(script=os.path.basename(__file__)) + "\n"
    for name, value in values:
        text += ".. |{}| replace:: {}\n".format(name, value)
    write_text(os.path.join(DOCS_DIR, "_admission_values.inc"), text)
    write_csv(os.path.join(DOCS_DIR, "adk", "tables", "admission_types.csv"), rows)


if __name__ == "__main__":
    main()
