#!/usr/bin/env python3
"""End-to-end (golden) test runner.

For every tests/programs/<name>.src the runner compiles and runs the program
and compares the results with the expected files in tests/expected/:

  <name>.tac   expected TAC              (only for programs that compile)
  <name>.out   expected program output, or the expected diagnostics
               ("line:col: phase error: message") for programs that must fail

Usage:
  python scripts/run_tests.py              run all tests, print a pass/fail matrix
  python scripts/run_tests.py -v           also show a diff for each failure
  python scripts/run_tests.py --markdown tests/results.md
  python scripts/run_tests.py --update     regenerate expected files (review the diff!)
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from driver.pipeline import compile_and_run  # noqa: E402

PROGRAMS = ROOT / "tests" / "programs"
EXPECTED = ROOT / "tests" / "expected"
CATEGORIES = {"b": "basic", "c": "control-flow", "s": "semantic-error",
              "i": "integration", "x": "extra-negative"}


def describe(src: str) -> str:
    for line in src.splitlines():
        if "TEST:" in line:
            return line.split("TEST:", 1)[1].strip()
    return ""


def actual_results(src: str):
    """Return (tac text or None, output text, failed phase or None)."""
    r = compile_and_run(src)
    if r.failed_phase in ("lexical", "syntax", "semantic"):
        lines = [f"{e.line}:{e.column}: {e.phase} error: {e.message}" for e in r.errors]
        return None, "\n".join(lines) + "\n", r.failed_phase
    out = list(r.output)
    if r.runtime_error:
        out.append(f"runtime error: {r.runtime_error.message} (TAC line {r.runtime_error.line})")
    return r.tac_text, "\n".join(out) + "\n", r.failed_phase


def check(name: str, label: str, expected_path: Path, actual: str | None, problems: list):
    if actual is None and not expected_path.exists():
        return
    expected = expected_path.read_text(encoding="utf-8") if expected_path.exists() else None
    if expected != actual:
        diff = difflib.unified_diff((expected or "").splitlines(), (actual or "").splitlines(),
                                    f"expected/{expected_path.name}", "actual", lineterm="")
        problems.append((label, "\n".join(diff)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--markdown", metavar="FILE")
    args = ap.parse_args()

    EXPECTED.mkdir(parents=True, exist_ok=True)
    rows, failures = [], 0
    for src_path in sorted(PROGRAMS.glob("*.src")):
        name = src_path.stem
        src = src_path.read_text(encoding="utf-8")
        tac, out, phase = actual_results(src)
        if args.update:
            (EXPECTED / f"{name}.out").write_text(out, encoding="utf-8")
            tac_file = EXPECTED / f"{name}.tac"
            if tac is not None:
                tac_file.write_text(tac, encoding="utf-8")
            else:
                tac_file.unlink(missing_ok=True)
        problems: list = []
        check(name, "TAC", EXPECTED / f"{name}.tac", tac, problems)
        check(name, "output", EXPECTED / f"{name}.out", out, problems)
        status = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        rows.append({"name": name, "category": CATEGORIES.get(name[0], "other"),
                     "expect": f"fails in {phase}" if phase else "runs",
                     "checked": "TAC + output" if tac is not None else "diagnostics",
                     "status": status, "description": describe(src), "problems": problems})

    width = max(len(r["name"]) for r in rows)
    print(f"{'test':<{width}}  {'category':<15} {'expected result':<22} {'checked':<13} status")
    print("-" * (width + 62))
    for r in rows:
        print(f"{r['name']:<{width}}  {r['category']:<15} {r['expect']:<22} "
              f"{r['checked']:<13} {r['status']}")
        if r["problems"] and args.verbose:
            for label, diff in r["problems"]:
                print(f"    {label} mismatch:\n" + "\n".join("      " + l for l in diff.splitlines()))
    passed = len(rows) - failures
    negatives = sum(1 for r in rows if r["expect"] != "runs")
    print(f"\n{passed}/{len(rows)} tests passed ({negatives} negative tests)"
          + (" [expected files updated]" if args.update else ""))

    if args.markdown:
        md = ["| Test | Category | Expected result | Checked | Status |",
              "|---|---|---|---|---|"]
        md += [f"| `{r['name']}` | {r['category']} | {r['expect']} | {r['checked']} | "
               f"{r['status']} |" for r in rows]
        md.append(f"\n**{passed}/{len(rows)} passed** ({negatives} negative tests)\n")
        Path(args.markdown).write_text("\n".join(md), encoding="utf-8")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
