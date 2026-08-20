#!/usr/bin/env python3
"""
Claim 2 -- Phase 4: negative test for the leakage check in validate_step4.py.

A leakage check that never fires is worthless -- it would pass just as
happily on a pipeline that reads the answer key on every line. This test
proves the check actually catches the two realistic leak paths by injecting
each into a throwaway copy of Condition B and asserting the validator
rejects it:

  1. opening the ground truth label table directly
  2. reading the v2 _change_log field (the real-vs-cosmetic answer key)

It also asserts the unmodified sources pass, so the test fails loudly if the
check ever degrades into a rubber stamp in either direction.

Run from the repository root:  python3 scripts/test_leakage_check.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def load_validator(scripts_dir):
    """Import a fresh copy of validate_step4 with its module-level FAILS reset,
    resolving script paths relative to scripts_dir's parent."""
    spec = importlib.util.spec_from_file_location(
        "v_under_test", os.path.join(scripts_dir, "validate_step4.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.FAILS.clear()
    return mod


def run_case(name, mutate, expect_fail):
    with tempfile.TemporaryDirectory() as tmp:
        dst = os.path.join(tmp, "scripts")
        os.makedirs(dst)
        for f in ("validate_step4.py", "run_condition_a.py", "run_condition_b.py"):
            shutil.copy(os.path.join(SCRIPTS, f), dst)

        if mutate:
            path = os.path.join(dst, "run_condition_b.py")
            src = open(path).read()
            new = mutate(src)
            assert new != src, f"{name}: injection did not modify the source"
            open(path, "w").write(new)

        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            mod = load_validator(dst)
            mod.check_leakage()
            fails = list(mod.FAILS)
        finally:
            os.chdir(cwd)

    caught = bool(fails)
    ok = caught == expect_fail
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    for f in fails:
        print(f"         caught: {f}")
    if not ok:
        print(f"         expected {'a violation' if expect_fail else 'no violation'}, "
              f"got {'a violation' if caught else 'none'}")
    return ok


def inject_label_read(src):
    return src.replace(
        'links = json.load(open(LINK_TABLE))["links"]',
        'links = json.load(open(LINK_TABLE))["links"]\n'
        '    _leak = json.load(open("ground_truth/labels.json"))')


def inject_changelog_read(src):
    return src.replace(
        'links = json.load(open(LINK_TABLE))["links"]',
        'links = json.load(open(LINK_TABLE))["links"]\n'
        '    _leak = json.load(open("policy_corpus/v2/POL-001_v2.json"))["_change_log"]')


def main():
    results = [
        run_case("unmodified sources pass", None, expect_fail=False),
        run_case("injected read of ground_truth/labels.json is caught",
                 inject_label_read, expect_fail=True),
        run_case("injected read of the _change_log answer key is caught",
                 inject_changelog_read, expect_fail=True),
    ]
    if not all(results):
        sys.exit(1)
    print("\nAll leakage-check negative tests passed.")


if __name__ == "__main__":
    main()
