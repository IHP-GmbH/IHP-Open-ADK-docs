#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Generate the assembly rule tables from the ADK KLayout decks.

Reads the shipped rule decks and parameter registries, and emits the CSV
tables consumed by ``docs/adk/03_asm_rules.rst`` and
``docs/adk/04_ixn_rules.rst`` plus a rule-count snippet.

The generator cross-checks the rule identifiers it finds in the deck against
the table below. A rule added to, removed from or renamed in the deck fails
this script, and therefore the documentation build, until it is described
here. That is deliberate: an undocumented rule is worse than a broken build.
"""

import os
import re

from _common import (
    ADK,
    DOCS_DIR,
    GENERATED_BANNER,
    fail,
    format_number,
    format_number as fmt,
    read_json,
    read_text,
    require_submodule,
    write_csv,
    write_text,
)

# rule id -> (parameter key or None, unit, notes shown in the "Parameter" column
# when the rule takes no parameter)
ASM_RULES = {
    "ASM.a": (None, "", "none (geometric)"),
    "ASM.b": ("ASM_b", "um", ""),
    "ASM.e": ("ASM_e", "um2", ""),
    "ASM.f": (None, "", "none (geometric)"),
}

# Interconnect rule identifiers. The per-method forms are built at run time
# from the identifiers in the methods manifest, so the deck contains Ruby
# interpolation rather than a literal; the generator normalises those to a
# placeholder form.
IXN_RULES = {
    "IXN.b": ("IXN_spacing", "um", "", "assembly-global"),
    "IXN.e": ("IXN_pitch", "um", "", "assembly-global"),
    "IXN.b.<method>": ("IXN_spacing", "um", "", "per method"),
    "IXN.e.<method>": ("IXN_pitch", "um", "", "per method"),
    "IXN.x.<method1>.<method2>": ("IXN_spacing", "um", "", "cross method"),
    "IXN.b.unclaimed": ("IXN_spacing", "um", "", "pads outside every method region"),
    "IXN.e.unclaimed": ("IXN_pitch", "um", "", "pads outside every method region"),
}

OUTPUT_CALL = re.compile(
    r"""\.output\(\s*(['"])(?P<rid>.+?)\1\s*,\s*(['"])(?P<desc>.+?)\3\s*\)""",
    re.DOTALL,
)


def normalise(rule_id):
    """Turn a Ruby-interpolated rule id into its documented placeholder form."""
    rule_id = rule_id.replace("#{m1}.#{m2}", "<method1>.<method2>")
    rule_id = rule_id.replace("#{mid}", "<method>")
    return rule_id


def strip_prefix(rule_id, description):
    """Drop the leading "ASM.b : " that the deck repeats inside the message."""
    for prefix in (rule_id + " : ", rule_id + ": "):
        if description.startswith(prefix):
            return description[len(prefix) :]
    # Per-method messages carry the interpolated id, which normalise() has
    # already rewritten in the key but not in the message body.
    parts = description.split(" : ", 1)
    if len(parts) == 2:
        return parts[1]
    return description


def clean_description(rule_id, description, values):
    """Resolve the Ruby interpolations in a rule message.

    For assembly-global rules the interpolated number is the shipped default,
    so substituting it is accurate. For per-method rules the number comes from
    the interconnect methods manifest at run time, and printing the adapter
    default there would be wrong, so those are rendered as a placeholder.
    """
    per_method = "<" in rule_id
    description = description.replace("#{mid}", "the method")
    description = description.replace("#{m1} vs #{m2}", "the two methods")
    description = description.replace("#{m1}", "method 1").replace("#{m2}", "method 2")

    if per_method:
        replacement = (
            "the larger of the two declared spacings"
            if rule_id.startswith("IXN.x")
            else "the value declared for that method"
        )
        # Swallow the trailing unit too: the placeholder text already reads as
        # a quantity, so "is <placeholder> um" would be ungrammatical.
        description = re.sub(r"#\{[^}]*\}(\s*um2?)?", replacement, description)
    else:
        for name, value in values.items():
            description = description.replace("#{%s}" % name, fmt(value))

    leftover = re.search(r"#\{[^}]*\}", description)
    if leftover:
        fail(
            "unresolved interpolation {!r} in rule message: {!r}".format(
                leftover.group(0), description
            )
        )
    return description.strip()


def parse_deck(path, values):
    """Return {rule_id: description} for every output() call in a rule deck."""
    found = {}
    for match in OUTPUT_CALL.finditer(read_text(path)):
        rule_id = normalise(match.group("rid"))
        description = strip_prefix(match.group("rid"), match.group("desc"))
        found[rule_id] = clean_description(rule_id, description, values)
    if not found:
        fail("no output() calls parsed from {}".format(path))
    return found


def check_coverage(found, documented, deck_name):
    extra = sorted(set(found) - set(documented))
    missing = sorted(set(documented) - set(found))
    if extra:
        fail(
            "{} declares rule(s) {} that this generator does not describe. "
            "Add them to the table in docs/scripts/gen_rule_tables.py and "
            "write the prose in docs/adk/.".format(deck_name, ", ".join(extra))
        )
    if missing:
        fail(
            "this generator describes rule(s) {} that {} no longer declares. "
            "Remove them here and from the prose.".format(", ".join(missing), deck_name)
        )


def main():
    require_submodule(ADK, "src/IHP-Open-ADK")

    rule_params = read_json(os.path.join(ADK, "config", "rule_params.json"))
    interconnect = read_json(os.path.join(ADK, "config", "interconnect.json"))

    asm_values = rule_params["rules"]
    ixn_values = interconnect["rules"]

    # The deck interpolates local Ruby variables into its messages, not the
    # registry key names, so map both spellings to the shipped default.
    asm_interp = dict(asm_values)
    asm_interp.update({"asm_b_value": asm_values["ASM_b"], "asm_e_value": asm_values["ASM_e"]})
    ixn_interp = dict(ixn_values)
    ixn_interp.update(
        {
            "ixn_b_value": ixn_values["IXN_spacing"],
            "ixn_pitch_value": ixn_values["IXN_pitch"],
            "ixn_pad_size": ixn_values["IXN_pad_size"],
            "ixn_x_value": ixn_values["IXN_spacing"],
        }
    )

    decks = os.path.join(ADK, "klayout", "drc", "rule_decks")
    asm_found = parse_deck(os.path.join(decks, "8_1_assembly.drc"), asm_interp)
    ixn_found = parse_deck(os.path.join(decks, "8_2_interconnect.drc"), ixn_interp)

    check_coverage(asm_found, ASM_RULES, "8_1_assembly.drc")
    check_coverage(ixn_found, IXN_RULES, "8_2_interconnect.drc")

    asm_rows = []
    for rule_id in sorted(ASM_RULES):
        param, unit, note = ASM_RULES[rule_id]
        value = fmt(asm_values[param]) if param else ""
        asm_rows.append(
            [
                rule_id,
                asm_found[rule_id],
                param if param else note,
                value,
                unit,
            ]
        )
    write_csv(os.path.join(DOCS_DIR, "adk", "tables", "asm_rules.csv"), asm_rows)

    ixn_order = [
        "IXN.b",
        "IXN.e",
        "IXN.b.<method>",
        "IXN.e.<method>",
        "IXN.x.<method1>.<method2>",
        "IXN.b.unclaimed",
        "IXN.e.unclaimed",
    ]
    ixn_rows = []
    for rule_id in ixn_order:
        param, unit, note, mode = IXN_RULES[rule_id]
        source = "adapter default" if "unclaimed" in rule_id or "<" not in rule_id else "methods manifest"
        value = fmt(ixn_values[param]) if source == "adapter default" else "per method"
        ixn_rows.append([rule_id, ixn_found[rule_id], mode, param, value])
    write_csv(os.path.join(DOCS_DIR, "adk", "tables", "ixn_rules.csv"), ixn_rows)

    # Parameter registry tables, one row per tunable value.
    param_rows = []
    for key in sorted(asm_values):
        param_rows.append(
            [
                key,
                rule_params["rule_descriptions"][key],
                fmt(asm_values[key]),
                "um2" if key.endswith("_e") else "um",
            ]
        )
    write_csv(os.path.join(DOCS_DIR, "adk", "tables", "asm_params.csv"), param_rows)

    ixn_param_rows = []
    for key in ("IXN_spacing", "IXN_pitch", "IXN_pad_size"):
        ixn_param_rows.append(
            [key, interconnect["rule_descriptions"][key], fmt(ixn_values[key]), "um"]
        )
    write_csv(os.path.join(DOCS_DIR, "adk", "tables", "ixn_params.csv"), ixn_param_rows)

    snippet = GENERATED_BANNER.format(script="gen_rule_tables.py")
    snippet += "\n"
    snippet += ".. |asm-rule-count| replace:: {}\n".format(len(asm_rows))
    snippet += ".. |ixn-rule-count| replace:: {}\n".format(len(ixn_rows))
    snippet += ".. |adk-config-version| replace:: {}\n".format(rule_params["version"])
    write_text(os.path.join(DOCS_DIR, "adk", "tables", "_rule_counts.inc"), snippet)


if __name__ == "__main__":
    main()
