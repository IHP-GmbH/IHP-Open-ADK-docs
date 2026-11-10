#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Check that tools/05 still describes the exit codes of ``bump_mirror.py``.

tools/05 states in prose when the Cu-pillar generator exits 0 and when it
exits 1, and what ``--auto-resolve-best-effort`` does to a device. No value
carries those statements, so this check reads OpenIntM4TM2
``libs.tech/klayout/python/bump_mirror.py`` at the commit this repository
pins, parses it with ast and stops the build, naming the statement on the
page, when the code no longer does what the page says. It also fails when
one of the tests that pin those exit codes upstream is gone.

The sources are read out of the pinned commit with ``git show``, never
imported and never from the checkout. It writes nothing.
"""

import ast
import os

from _common import INTERPOSER, fail, git, git_text, pinned_commit

NAME = "src/OpenIntM4TM2"
SOURCE = "libs.tech/klayout/python/bump_mirror.py"
TESTS = "libs.tech/klayout/intm4tm2_tests/test_bump_mirror.py"
PAGE = "tools/05"

EXIT_0 = "0 when no device failed and, in a generate run, at least one device passed"
EXIT_1 = "1 when any device failed DRC or had no bump locations"
BAD_INPUT = "1 also when the input is bad"
NO_PASSED = "A generate run in which no device passed ... exits 1"
BEST_EFFORT = ("--auto-resolve-best-effort: a device with collisions left still "
               "fails DRC and is dropped")

# The upstream tests that pin the exit codes the page states.
EXIT_CODE_TESTS = (
    "test_validate_only_with_a_failing_device_exits_1",
    "test_generate_with_a_failing_device_exits_1_with_the_passing_pads",
    "test_a_skipped_device_alone_exits_0",
    "test_a_generate_run_with_only_a_skipped_device_writes_nothing_and_exits_1",
)


def show(commit, path):
    toplevel = git(INTERPOSER, "rev-parse", "--show-toplevel")
    if not toplevel or os.path.realpath(toplevel) != os.path.realpath(INTERPOSER):
        fail("submodule {} is not initialised. Run: git submodule update --init "
             "{}".format(NAME, NAME))
    return git_text(INTERPOSER, "show", "{}:{}".format(commit, path))


def functions(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def is_call(node, name):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == name)


def returns_constant(statements, value):
    return any(isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
               and node.value.value == value
               for statement in statements for node in ast.walk(statement))


def branch(function, test):
    """The body of the first if statement in function whose test is test."""
    for node in ast.walk(function):
        if isinstance(node, ast.If) and ast.unparse(node.test) == test:
            return node.body
    return None


def check_exit_for(found):
    exit_for = found.get("_exit_for")
    if exit_for is None:
        return ["_exit_for is gone"]
    values = set()
    for node in ast.walk(exit_for):
        if isinstance(node, ast.Return):
            if not isinstance(node.value, ast.Constant) or node.value.value not in (0, 1):
                return ["_exit_for returns {}, not only 0 or 1".format(
                    ast.unparse(node.value) if node.value else "None")]
            values.add(node.value.value)
    if values != {0, 1}:
        return ["_exit_for returns {} only".format(sorted(values))]
    return []


def check_run_main(found):
    run_main = found.get("_run_main")
    if run_main is None:
        return ["_run_main is gone"]
    problems = []
    validate_only = branch(run_main, "args.validate_only")
    if not validate_only or not any(
            isinstance(node, ast.Return) and is_call(node.value, "_exit_for")
            for node in validate_only):
        problems.append("the --validate-only return no longer calls _exit_for")
    last = run_main.body[-1]
    if not (isinstance(last, ast.Return) and is_call(last.value, "_exit_for")):
        problems.append("the final return of _run_main no longer calls _exit_for")
    return problems


def check_no_passed(found):
    run_main = found.get("_run_main")
    if run_main is None:
        return ["_run_main is gone"]
    no_passed = branch(run_main, "not passed_devices")
    if not no_passed or not returns_constant(no_passed, 1):
        return ["the branch with no passed device no longer returns 1"]
    return []


def check_main(found):
    main = found.get("main")
    if main is None:
        return ["main is gone"]
    tries = [node for node in ast.walk(main) if isinstance(node, ast.Try)]
    caught = [handler for node in tries for handler in node.handlers
              if handler.type is not None and "CliInputError" in ast.unparse(handler.type)]
    if not caught or not returns_constant(caught[0].body, 1):
        return ["main no longer turns a CliInputError into exit 1"]
    guarded = [node for t in tries for statement in t.body for node in ast.walk(statement)]
    parse = [node for node in ast.walk(main) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "parse_args"]
    if not parse:
        return ["main no longer calls parse_args"]
    if any(node in guarded for node in parse):
        return ["main parses its arguments inside the try, so a usage error may not "
                "exit 2"]
    return []


def check_best_effort(tree):
    helps = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument" and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "--auto-resolve-best-effort"):
            helps += [k.value for k in node.keywords if k.arg == "help"]
    if len(helps) != 1 or not isinstance(helps[0], ast.Constant):
        return ["no single help string for --auto-resolve-best-effort"]
    if "left out of the GDS" not in " ".join(str(helps[0].value).split()):
        return ["the --auto-resolve-best-effort help no longer says the device is "
                "left out of the GDS"]
    return []


def main():
    commit = pinned_commit(INTERPOSER, NAME)
    label = "{}@{} {}".format(NAME, commit[:7], SOURCE)
    tree = ast.parse(show(commit, SOURCE))
    found = functions(tree)

    stale = []
    for statement, problems in (
            (EXIT_0, check_exit_for(found)),
            (EXIT_1, check_run_main(found)),
            (NO_PASSED, check_no_passed(found)),
            (BAD_INPUT, check_main(found)),
            (BEST_EFFORT, check_best_effort(tree))):
        stale += ["{} says \"{}\", but in {} {}".format(PAGE, statement, label, problem)
                  for problem in problems]

    tests = ast.parse(show(commit, TESTS))
    names = {node.name for node in ast.walk(tests) if isinstance(node, ast.FunctionDef)}
    for name in EXIT_CODE_TESTS:
        if name not in names:
            stale.append("{} states the exit codes these tests pin, but {}@{} {} has no "
                         "{}".format(PAGE, NAME, commit[:7], TESTS, name))

    if stale:
        fail("bump_mirror.py no longer matches {}:\n  {}".format(PAGE, "\n  ".join(stale)))
    print("{} matches the exit codes of bump_mirror.py at {}".format(PAGE, commit[:7]))


if __name__ == "__main__":
    main()
