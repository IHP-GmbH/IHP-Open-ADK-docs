#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Capture the --help output of every ADK command line tool.

The usage blocks on this site are transcripts of the shipped tools, not
retyped summaries, so an added or renamed flag shows up as a diff rather than
as documentation that quietly stops matching the code.

Output is written under docs/adk/_usage/ and included with literalinclude.
COLUMNS is pinned so the wrapping is stable across machines; without it argparse
formats against the terminal width and every run produces a different diff.
"""

import os
import subprocess
import sys

from _common import ADK, DOCS_DIR, fail, require_submodule

# label -> path relative to the ADK checkout
COMMANDS = {
    "run_drc": os.path.join("klayout", "drc", "run_drc.py"),
    "chiplet2dbx": os.path.join("openroad", "chiplet2dbx.py"),
    "pads_vs_pillars": os.path.join("checks", "pads_vs_pillars.py"),
    "generate_assembly_dru": os.path.join("kicad", "dru", "generate_assembly_dru.py"),
}

WRAP_COLUMNS = "80"


def capture(script_path):
    env = dict(os.environ)
    env["COLUMNS"] = WRAP_COLUMNS
    # Keep the transcript free of machine-specific noise.
    env.pop("PYTHONWARNINGS", None)
    try:
        result = subprocess.run(
            [sys.executable, script_path, "--help"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=os.path.dirname(script_path),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail("could not run {} --help: {}".format(script_path, exc))
    if result.returncode != 0:
        fail(
            "{} --help exited {}:\n{}".format(
                script_path, result.returncode, result.stderr.strip()
            )
        )
    text = result.stdout.rstrip() + "\n"
    if not text.startswith("usage:"):
        fail("unexpected --help output from {}: {!r}".format(script_path, text[:80]))
    return text


def main():
    require_submodule(ADK, "src/IHP-Open-ADK")
    out_dir = os.path.join(DOCS_DIR, "adk", "_usage")
    os.makedirs(out_dir, exist_ok=True)

    for label, relative in sorted(COMMANDS.items()):
        script_path = os.path.join(ADK, relative)
        if not os.path.isfile(script_path):
            fail(
                "command {} not found at {}. It moved or was renamed in the "
                "ADK.".format(label, script_path)
            )
        text = capture(script_path)
        target = os.path.join(out_dir, "{}.txt".format(label))
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("wrote docs/adk/_usage/{}.txt".format(label))


if __name__ == "__main__":
    main()
