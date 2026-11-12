#!/usr/bin/env python3
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
"""Copy the shell blocks of an adk-examples page into include files for this site.

The from-scratch guide shows the blocks of a typical application, and the examples
repository is where those blocks are run against the release image. So the guide never
types a block of its own: each one is copied from the example at the adk-examples commit
docs/_blocks/ADK_EXAMPLES_COMMIT names, into docs/_blocks/<example>/<page>-<key>.inc, with
a header naming that commit. The pin is an input: a plain run renders that commit again,
whatever the checkout's HEAD, and ``--pin <rev>`` moves it, one explicit act, then renders.
A block that moves in the examples shows up as a diff in a committed file at the pin move.

The values the guide's prose states about a block are not typed there either: VALUES names,
per example, each one with the block it is read from and a pattern, and they are written as
substitutions into <example>/values.inc. A value is read from the block itself, or from the
output the examples captured when they ran it on the reference image, in the example's
proven/readme.json, only when that capture is of the same block (its digest) on the image
of this release (its lock). What the guide still types by hand is named in a comment at its
top.

The blocks are read from the scripts an example commits beside its page,
<example>/scripts/<page>-<key>-<shell>.sh, which adk-examples' ci/page_scripts.py writes
from the page and checks against it: one script per fenced ``sh <shell>`` block, keyed by
the ``## N.`` heading above it, with a, b, c when the heading holds several. A script is a
comment header, a guard, one blank line, then the block as the page has it. So this site
parses no page and cannot key a block differently from the examples' own check. The
example's system file is copied too, as <example>/system.inc, and EXCERPTS names mapping
keys of it copied on their own, as <example>/<name>.inc, with the mapping lines they sit
under and the comment lines directly above them, so a reader sees where the block goes.

WANTED names, per example, the include files the guide uses, as globs over the file
stems; only those are written. A write ends, and ``--check`` runs, the inclusion test:
every written file is included by a page of this site and every include a page names is
written. So a block added upstream to a page the guide shows in full is noticed at the pin
move, and no dead file is carried. ``--check`` also fails when a committed file differs
from the render, is missing or is stale.

The checkout is $ADK_DOCS_EXAMPLES_ROOT, any clone holding the pinned commit; it is read
with git show, never from its working tree. The variable is this site's own: the examples'
scripts export ADK_EXAMPLES_ROOT, and a shell that ran them must not switch a plain
``make preprocess`` into writing. A render also holds the pin to this site's: the pin's
release-lock.json must name the ADK-Tools commit HEAD pins src/ADK-Tools at. Without a
checkout, as in the public build (the examples repository is private), the committed
files stand, and a plain run verifies them: each file's digest against
docs/_blocks/SHA256SUMS, written at every render, and each header's commit against the
pin. ``--check`` without a checkout cannot compare against the examples and exits 2, so a
quiet pass is never a check that did not run.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
from decimal import Decimal

from _common import (
    DOCS_DIR,
    REPO_ROOT,
    SRC_DIR,
    fail,
    git,
    git_or_fail,
    git_text,
    included as includes,
    own_files,
    pinned_commit,
    read_text,
    write_text,
)

#: example folder -> the include files the guide uses, as globs over the file stems
WANTED = {
    "typical_01_two_die_minimal": ["system", "readme-*"],
    "typical_02_die_with_power": ["rails", "readme-7"],
}
#: example folder -> (include name, key of system.chiplet whose mapping block is copied alone)
EXCERPTS = {"typical_02_die_with_power": [("rails", "rails")]}


def literal(text):
    return "``{}``".format(text)


def milli(text):
    return plain(Decimal(text) * 1000)


def plain(value):
    """A number without trailing zeros: 10.0 is 10, 0.050 is 0.05."""
    return format(Decimal(value).normalize(), "f")


#: example folder -> (name, block stem-key, "block" or "capture", pattern, format) per value
#: the guide states. The pattern's one group is the value; every match must agree.
SUMMARY = r"read: (\d+ refusing, \d+ note\(s\))"
VALUES = {
    "typical_01_two_die_minimal": [
        ("cpus", "readme-1", "block", r"\bCPUS=(\d+)\b", plain),
        ("mem-gib", "readme-1", "block", r"\bMEM=(\d+)\b", plain),
        ("validate-expected", "readme-3a", "block", r"^# expected: (validate exit=\d+)$", literal),
        ("validate-summary", "readme-3a", "capture", SUMMARY, literal),
        ("note-code", "readme-3a", "capture", r"^\[INFO (PFL-\d+)\] [^:]+:\d+:", literal),
        ("refusal-code", "readme-3a", "capture", r"^\[ERROR (PFL-\d+)\] [^:]+:\d+:", literal),
        ("placed-summary", "readme-3b", "capture", SUMMARY, literal),
        ("placed-notes", "readme-3b", "capture", r"read: 0 refusing, (\d+) note\(s\)", plain),
        ("run-expected", "readme-4a", "block", r"^# expected: (run exit=\d+)$", literal),
        ("verify-expected", "readme-7", "block", r"^# expected: (verify exit=\d+)$", literal),
        ("nets", "readme-7", "capture", r"^assembly LVS: \S+ (\d+) nets", plain),
        ("endpoints", "readme-7", "capture", r"^assembly LVS: \S+ \d+ nets (\d+) endpoints", plain),
    ],
    "typical_02_die_with_power": [
        ("rail-width-um", "readme-7", "capture", r"^V\w+: \S+ at ([\d.]+) um from", plain),
        ("rail-ma", "readme-7", "capture", r"^V\w+: .* from ([\d.]+) A at", milli),
        ("rail-density", "readme-7", "capture", r"^V\w+: .* A at ([\d.]+) mA/um", plain),
    ],
}
OUT_DIR = os.path.join(DOCS_DIR, "_blocks")
CAPTURE_SCHEMA = "adk-examples.proven/2"
#: release-lock.json schema -> its required keys (install/00_release, "The release lock")
LOCK_KEYS = {
    "adk-examples.release-lock/1": ("adk_tools", "image", "pin_set"),
    "adk-examples.release-lock/2": ("adk_tools", "image", "image_manifest", "pin_set"),
}
PIN = "ADK_EXAMPLES_COMMIT"
SUMS = "SHA256SUMS"
BLOCK_ID = r"^(?P<stem>[a-z0-9]+)-(?P<key>[a-z0-9-]+?)-(?P<shell>host-after|host|container|review)"
SCRIPT = re.compile(BLOCK_ID + r"\.sh$")
CAPTURE_ID = re.compile(BLOCK_ID + r"$")
TOOLS_VALUE = re.compile(r"^\.\. \|[a-z0-9-]+-adk-tools\| replace:: ``([0-9a-f]+)``$", re.MULTILINE)
SHA = re.compile(r"^[0-9a-f]{40}$")
ROOT_VARIABLE = "ADK_DOCS_EXAMPLES_ROOT"
BANNER = (".. Generated by docs/scripts/gen_example_blocks.py. Do not edit by hand.\n"
          ".. Regenerate with: {}=<adk-examples clone> make -C docs preprocess\n"
          .format(ROOT_VARIABLE))


def rel(path):
    return os.path.relpath(path, os.path.dirname(DOCS_DIR))


def checkout():
    """The adk-examples clone $ADK_DOCS_EXAMPLES_ROOT names, or None when it is unset."""
    root = os.environ.get(ROOT_VARIABLE)
    if not root:
        return None
    if not os.path.isdir(root):
        fail("{}={} is not a directory".format(ROOT_VARIABLE, root))
    return root


def holds(root, commit):
    return git(root, "cat-file", "-t", commit) == "commit"


def pin():
    """The pinned commit, 40 hex characters, from docs/_blocks/ADK_EXAMPLES_COMMIT."""
    path = os.path.join(OUT_DIR, PIN)
    if not os.path.isfile(path):
        fail("{} is missing; set it with --pin <rev> and {}".format(rel(path), ROOT_VARIABLE))
    commit = read_text(path).strip()
    if not SHA.match(commit):
        fail("{} holds {!r}, not a 40-character commit".format(rel(path), commit))
    return commit


def code(commit, example, what, lang, body):
    """One include file: the banner naming the commit and the source, then the code block."""
    indented = "".join("    " + line if line.strip() else "\n" for line in body.splitlines(True))
    return (BANNER + ".. From adk-examples {}: {}/{}\n\n".format(commit, example, what)
            + ".. code-block:: {}\n\n".format(lang) + indented)


def depth_of(line):
    return len(line) - len(line.lstrip())


def excerpt(system, key):
    """The first ``key:`` mapping block of the system file, at any depth, with the comment
    lines directly above it and the mapping lines it sits under, as the file indents them."""
    lines = system.splitlines(True)
    for i, line in enumerate(lines):
        if line.lstrip().startswith(key + ":"):
            depth = depth_of(line)
            end = i + 1
            while end < len(lines) and (not lines[end].strip() or depth_of(lines[end]) > depth):
                end += 1
            start = i
            while start > 0 and lines[start - 1].strip().startswith("#") \
                    and depth_of(lines[start - 1]) == depth:
                start -= 1
            parents, above, want = [], start - 1, depth
            while want > 0 and above >= 0:
                text = lines[above].strip()
                if text and not text.startswith("#") and depth_of(lines[above]) < want:
                    parents.insert(0, lines[above])
                    want = depth_of(lines[above])
                above -= 1
            return "".join(parents + lines[start:end])
    fail("system.chiplet has no {}: block".format(key))


def scripts(root, commit, example):
    """(stem, key, shell, body) per script the example commits at commit."""
    folder = "{}/scripts".format(example)
    out = []
    for name in sorted(git_text(root, "ls-tree", "--name-only", "{}:{}".format(commit, folder)).split()):
        match = SCRIPT.match(name)
        if not match:
            fail("{}/{} at {} is not a <page>-<key>-<shell>.sh script".format(folder, name, commit[:12]))
        text = git_text(root, "show", "{}:{}/{}".format(commit, folder, name))
        header, blank, body = text.partition("\n\n")
        if not blank or not body:
            fail("{}/{} at {} has no block after its header".format(folder, name, commit[:12]))
        out.append((match["stem"], match["key"], match["shell"], body))
    return out


def tools_lock(root, commit):
    """The pin's release-lock.json, whose ADK-Tools commit must be the one this site
    pins src/ADK-Tools at (in the index, as every generator reads its pins)."""
    lock = json.loads(git_text(root, "show", "{}:release-lock.json".format(commit)))
    if lock.get("schema") not in LOCK_KEYS:
        fail("adk-examples {} release-lock.json is schema {}, this generator reads {}"
             .format(commit[:12], lock.get("schema"), " or ".join(sorted(LOCK_KEYS))))
    for key in LOCK_KEYS[lock["schema"]]:
        if not lock.get(key):
            fail("adk-examples {} release-lock.json has no {}".format(commit[:12], key))
    tools = pinned_commit(os.path.join(SRC_DIR, "ADK-Tools"), "src/ADK-Tools")
    if lock["adk_tools"] != tools:
        fail("adk-examples {} locks ADK-Tools {}, but this site pins src/ADK-Tools at {}; "
             "move one pin to the other".format(commit[:12], lock["adk_tools"][:12], tools[:12]))
    return lock


def captures(root, commit, example, lock):
    """{block stem-key: (digest of the block, its captured output)} from the example's
    proven/readme.json, the run of its page on the reference image of this release."""
    path = "{}/proven/readme.json".format(example)
    proven = json.loads(git_text(root, "show", "{}:{}".format(commit, path)))
    # adk-examples.proven/2 (ci/proven_commands.py): a capture proves its page when it
    # was made under the lock's pin set, on the image the lock names, and its container
    # exited 0. Each block keeps only the lines the page declares it prints.
    made = proven.get("lock") or {}
    if proven.get("schema") != CAPTURE_SCHEMA:
        fail("{} at {} is schema {}, this generator reads {}"
             .format(path, commit[:12], proven.get("schema"), CAPTURE_SCHEMA))
    # tools_lock() has checked that the lock holds its schema's keys. A capture made on
    # the containerd image store records the ID a schema /2 lock names as image_manifest.
    images = {lock["image"], lock.get("image_manifest")} - {None}
    if made.get("pin_set") != lock["pin_set"] or \
            made.get("adk_tools") != lock["adk_tools"] or \
            proven.get("image") not in images or \
            proven.get("container_exit") != 0:
        fail("{} at {} is not a clean capture on the reference image its release-lock.json names"
             .format(path, commit[:12]))
    out = {}
    for block in proven.get("blocks", []):
        match = CAPTURE_ID.match(block.get("id", ""))
        if not match:
            fail("{} at {}: block id {!r} is not <page>-<key>-<shell>"
                 .format(path, commit[:12], block.get("id")))
        if block.get("clean"):
            stem = "{}-{}".format(match["stem"], match["key"])
            out[stem] = (block.get("digest"), "\n".join(block.get("printed", [])))
    return out


def values(commit, example, bodies, captured, lock):
    """The include file of substitutions the guide states about the example's blocks,
    after the commit they were read at and the ADK-Tools commit its lock names."""
    prefix = "-".join(example.split("_")[:2])
    lines = [".. |{}-examples-commit| replace:: {}\n".format(prefix, literal(commit[:7])),
             ".. |{}-adk-tools| replace:: {}\n".format(prefix, literal(lock["adk_tools"][:7]))]
    for name, stem, source, pattern, form in VALUES[example]:
        if stem not in bodies:
            fail("{} at {} has no block {} for |{}-{}|".format(example, commit[:12], stem, prefix, name))
        if source == "block":
            text = bodies[stem]
        else:
            if stem not in captured:
                fail("{}/proven/readme.json at {} has no clean capture of {}".format(example, commit[:12], stem))
            digest, text = captured[stem]
            if digest != hashlib.sha256(bodies[stem].encode("utf-8")).hexdigest():
                fail("{}/proven/readme.json at {} captured another version of {}"
                     .format(example, commit[:12], stem))
        found = set(re.findall(pattern, text, re.M))
        if len(found) != 1:
            fail("{} {} at {}: {!r} matches {} for |{}-{}|, not one value".format(
                example, stem, commit[:12], pattern, sorted(found) or "nothing", prefix, name))
        lines.append(".. |{}-{}| replace:: {}\n".format(prefix, name, form(found.pop())))
    return (BANNER + ".. From adk-examples {}: {}/scripts and {}/proven/readme.json\n\n"
            .format(commit, example, example) + "".join(lines))


def render(root, commit):
    """{path under docs/_blocks: content} for the pin and every include file the guide
    uses, read from the example at commit with git show, never from a working tree."""
    lock = tools_lock(root, commit)
    files = {PIN: commit + "\n"}
    for example, globs in WANTED.items():
        have, bodies = {}, {}
        system = git_text(root, "show", "{}:{}/system.chiplet".format(commit, example))
        have["system"] = code(commit, example, "system.chiplet", "yaml", system)
        for name, key in EXCERPTS.get(example, []):
            have[name] = code(commit, example, "system.chiplet, the {} block".format(key), "yaml",
                              excerpt(system, key))
        for stem, key, shell, body in scripts(root, commit, example):
            bodies["{}-{}".format(stem, key)] = body
            have["{}-{}".format(stem, key)] = code(
                commit, example, "scripts/{}-{}-{}.sh".format(stem, key, shell), "bash", body)
        for glob in globs:
            names = fnmatch.filter(have, glob)
            if not names:
                fail("{} at {} has no include matching {!r}; it has {}"
                     .format(example, commit[:12], glob, ", ".join(sorted(have))))
            for name in names:
                files["{}/{}.inc".format(example, name)] = have[name]
        if example in VALUES:
            files["{}/values.inc".format(example)] = values(
                commit, example, bodies, captures(root, commit, example, lock), lock)
    return files


def committed():
    """{path under docs/_blocks: content} as the site holds them now, SHA256SUMS aside."""
    files = {}
    if os.path.isfile(os.path.join(OUT_DIR, PIN)):
        files[PIN] = read_text(os.path.join(OUT_DIR, PIN))
    for example in WANTED:
        folder = os.path.join(OUT_DIR, example)
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".inc"):
                    files["{}/{}".format(example, name)] = read_text(os.path.join(folder, name))
    return files


def digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sums(files):
    return "".join("{}  {}\n".format(digest(files[path]), path) for path in sorted(files))


def included():
    """The files under docs/_blocks that the site's pages include, relative to it."""
    found = set()
    for page in own_files((".rst", ".md")):
        for _target, path in includes(page):
            if os.path.commonpath([path, OUT_DIR]) == OUT_DIR:
                found.add(os.path.relpath(path, OUT_DIR))
    return found


def inclusion(files):
    """The problems between the rendered set and the pages, one line each."""
    rendered = {path for path in files if path.endswith(".inc")}
    named = included()
    return (["{}: written, but no page includes it".format(p) for p in sorted(rendered - named)]
            + ["{}: a page includes it, but no example file renders it".format(p)
               for p in sorted(named - rendered)])


def report(problems, what):
    for line in problems:
        print("gen_example_blocks: {}".format(line))
    if problems:
        fail("{} problem(s) in docs/_blocks; {}".format(len(problems), what))


def write(root, commit):
    files = render(root, commit)  # all of it first, so a failure leaves the tree as it was
    for example in WANTED:
        folder = os.path.join(OUT_DIR, example)
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.endswith(".inc"):
                    os.remove(os.path.join(folder, name))
    for path, content in files.items():
        write_text(os.path.join(OUT_DIR, path), content)
    write_text(os.path.join(OUT_DIR, SUMS), sums(files))
    report(inclusion(files), "include each written file from a page, or drop it from WANTED")


def verify():
    """The committed files against SHA256SUMS, the pin and the pages, with no checkout."""
    commit = pin()
    path = os.path.join(OUT_DIR, SUMS)
    if not os.path.isfile(path):
        fail("{} is missing; render once with {}".format(rel(path), ROOT_VARIABLE))
    recorded = dict(reversed(line.split("  ", 1)) for line in read_text(path).splitlines() if "  " in line)
    files = committed()
    problems = []
    for name in sorted(set(files) | set(recorded)):
        if name not in recorded:
            problems.append("{}: not in SHA256SUMS".format(name))
        elif name not in files:
            problems.append("{}: in SHA256SUMS, but missing".format(name))
        elif digest(files[name]) != recorded[name]:
            problems.append("{}: differs from its SHA256SUMS digest".format(name))
    tools = pinned_commit(os.path.join(SRC_DIR, "ADK-Tools"), "src/ADK-Tools")
    for name, content in files.items():
        if name.endswith(".inc") and "adk-examples {}:".format(commit) not in content:
            problems.append("{}: its header does not name the pinned commit".format(name))
        for short in TOOLS_VALUE.findall(content):
            if not tools.startswith(short):
                problems.append("{}: states ADK-Tools {}, but src/ADK-Tools is pinned at {}; "
                                "move the adk-examples pin to a commit locking it".format(name, short, tools[:12]))
    problems += inclusion(files)
    report(problems, "render again with {} at the pinned commit".format(ROOT_VARIABLE))
    print("gen_example_blocks: no adk-examples checkout ({} unset); {} committed "
          "files verified against SHA256SUMS and the pin {}".format(ROOT_VARIABLE, len(files), commit[:12]))


def check(root):
    """The committed files against what the pinned commit renders."""
    commit = pin()
    if not holds(root, commit):
        print("gen_example_blocks --check: {} does not hold adk-examples {}; fetch it first"
              .format(root, commit[:12]))
        raise SystemExit(2)
    expected, actual = render(root, commit), committed()
    problems = []
    for name in sorted(set(expected) | set(actual)):
        if name not in actual:
            problems.append("{}: missing".format(name))
        elif name not in expected:
            problems.append("{}: stale, not rendered at {}".format(name, commit[:12]))
        elif expected[name] != actual[name]:
            problems.append("{}: differs from what {} renders".format(name, commit[:12]))
    path = os.path.join(OUT_DIR, SUMS)
    if not os.path.isfile(path) or read_text(path) != sums(expected):
        problems.append("{}: not the digests of the render".format(SUMS))
    problems += inclusion(expected)
    report(problems, "render again with {}, or move the pin on purpose with --pin".format(ROOT_VARIABLE))
    print("gen_example_blocks --check: {} files match adk-examples {}".format(len(expected), commit[:12]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="compare the committed files with what the pinned commit renders")
    mode.add_argument("--pin", metavar="REV",
                      help="move the pin to this adk-examples revision, then render")
    args = parser.parse_args(argv)
    root = checkout()
    if args.pin:
        if root is None:
            fail("--pin needs {}, a clone holding the revision".format(ROOT_VARIABLE))
        write(root, git_text(root, "rev-parse", "--verify", args.pin + "^{commit}").strip())
    elif args.check:
        if root is None:
            print("gen_example_blocks --check: no adk-examples checkout ({} unset); "
                  "the includes cannot be checked here".format(ROOT_VARIABLE))
            raise SystemExit(2)
        check(root)
    elif root is None:
        verify()
    else:
        commit = pin()
        if not holds(root, commit):
            fail("{} does not hold adk-examples {}; fetch it, or move the pin with --pin"
                 .format(root, commit[:12]))
        write(root, commit)


if __name__ == "__main__":
    main()
