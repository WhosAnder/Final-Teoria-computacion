"""Command-line front ends: `compile`, `run` and `minilangc` (full pipeline).

    compile input.src -o out.tac [--artifacts DIR]
    run out.tac [-o output.txt]
    minilangc input.src [-o build/]      # every artifact + execution, phase by phase
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common.diagnostics import format_diagnostic, Diagnostic
from ir.basic_blocks import build_cfg, render_cfg
from parser.ast_printer import render_ast
from semantics.analyzer import semantic_report
from driver.pipeline import CompilationResult, compile_source, run_tac

ARTIFACTS = ["tokens.json", "ast.json", "ast.txt", "semantic.json",
             "program.tac", "cfg.txt", "output.txt"]


# --------------------------------------------------------------------- writers
def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_tokens(path: Path, name: str, r: CompilationResult) -> None:
    """tokens.json with one token per line, easy to read and to diff."""
    tokens = ",\n".join("    " + _dump(t.to_dict()) for t in r.tokens)
    errors = ",\n".join("    " + _dump(e.to_dict()) for e in r.lexical_errors)
    path.write_text(
        "{\n"
        f'  "source": {_dump(name)},\n'
        f'  "status": "{"FAILED" if r.lexical_errors else "PASSED"}",\n'
        f'  "token_count": {len(r.tokens)},\n'
        f'  "tokens": [\n{tokens}\n  ],\n'
        f'  "errors": [{chr(10) + errors + chr(10) + "  " if errors else ""}]\n'
        "}\n", encoding="utf-8")


def write_artifacts(out: Path, name: str, r: CompilationResult) -> list[str]:
    """Write every artifact the compilation produced. Returns the file names written."""
    out.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACTS:
        (out / stale).unlink(missing_ok=True)
    written = ["tokens.json"]
    write_tokens(out / "tokens.json", name, r)
    if r.failed_phase == "lexical":
        return written
    if r.failed_phase == "syntax":
        write_json(out / "ast.json", {"status": "FAILED",
                                      "errors": [e.to_dict() for e in r.syntax_errors],
                                      "partial_ast": r.ast})
        return written + ["ast.json"]
    write_json(out / "ast.json", r.ast)
    (out / "ast.txt").write_text(render_ast(r.ast) + "\n", encoding="utf-8")
    write_json(out / "semantic.json", r.semantic)
    written += ["ast.json", "ast.txt", "semantic.json"]
    if r.failed_phase == "semantic":
        return written
    (out / "program.tac").write_text(r.tac_text, encoding="utf-8")
    (out / "cfg.txt").write_text(render_cfg(build_cfg(r.tac)), encoding="utf-8")
    return written + ["program.tac", "cfg.txt"]


def print_diagnostics(r: CompilationResult, filename: str, stream=sys.stderr) -> None:
    for e in r.errors:
        print(f"{filename}:" + format_diagnostic(e, r.source), file=stream)
    if r.semantic:
        for w in r.semantic["warnings"]:
            print(f"{filename}:" + format_diagnostic(Diagnostic.from_dict(w), r.source,
                                                     "warning"), file=stream)


def _read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"error: file not found: {path}")
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------- compile
def compile_main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="compile", description="Compile a Mini-Lang program to TAC.")
    ap.add_argument("source", help="input .src file")
    ap.add_argument("-o", "--output", help="output .tac file (default: <source>.tac)")
    ap.add_argument("--artifacts", metavar="DIR",
                    help="also write tokens.json, ast.json, semantic.json, cfg.txt to DIR")
    args = ap.parse_args(argv)

    r = compile_source(_read(args.source))
    name = Path(args.source).name
    if args.artifacts:
        write_artifacts(Path(args.artifacts), name, r)
    print_diagnostics(r, name)
    if not r.ok:
        print(f"compilation failed in the {r.failed_phase} phase "
              f"({len(r.errors)} error(s))", file=sys.stderr)
        return 1
    out = Path(args.output) if args.output else Path(args.source).with_suffix(".tac")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(r.tac_text, encoding="utf-8")
    print(f"wrote {out}")
    return 0


# ------------------------------------------------------------------------- run
def run_main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="run", description="Execute a .tac file.")
    ap.add_argument("tac", help="input .tac file")
    ap.add_argument("-o", "--output", help="also write the program output to this file")
    ap.add_argument("--max-steps", type=int, default=1_000_000)
    args = ap.parse_args(argv)

    output, error, _ = run_tac(_read(args.tac), args.max_steps)
    lines = output + ([f"runtime error: {error.message} (TAC line {error.line})"] if error else [])
    if output:
        print("\n".join(output))
    if error:
        print(lines[-1], file=sys.stderr)
    if args.output:
        Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if error else 0


# ------------------------------------------------------------------- minilangc
def minilangc_main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="minilangc",
                                 description="Run the whole pipeline and write every artifact.")
    ap.add_argument("source", help="input .src file")
    ap.add_argument("-o", "--out", default="build", help="artifact directory (default: build)")
    ap.add_argument("--no-run", action="store_true", help="stop after code generation")
    ap.add_argument("--max-steps", type=int, default=1_000_000)
    args = ap.parse_args(argv)

    name, out = Path(args.source).name, Path(args.out)
    r = compile_source(_read(args.source))
    write_artifacts(out, name, r)
    ok, bad = "OK    ", "FAILED"

    print(f"minilangc {name} -> {out}/\n")
    print(f"[1/5] lexical analysis   {bad if r.failed_phase == 'lexical' else ok}"
          f" {len(r.tokens)} tokens            tokens.json")
    if r.failed_phase == "lexical":
        return _fail(r, name)
    print(f"[2/5] syntax analysis    {bad if r.failed_phase == 'syntax' else ok}"
          f" {len(r.ast['body'])} top-level statements  ast.json, ast.txt")
    if r.failed_phase == "syntax":
        return _fail(r, name)
    sem = r.semantic
    print(f"[3/5] semantic analysis  {bad if sem['status'] == 'FAILED' else ok}"
          f" {len(sem['symbol_table'])} symbols            semantic.json")
    print("\n" + "\n".join("      " + l for l in semantic_report(sem).splitlines()) + "\n")
    if r.failed_phase == "semantic":
        return _fail(r, name)
    print_diagnostics(r, name, sys.stdout)
    n = sum(1 for l in r.tac if not l.endswith(":"))
    print(f"[4/5] code generation    {ok} {n} TAC instructions    program.tac, cfg.txt")
    if args.no_run:
        return 0

    output, error, steps = run_tac(r.tac_text, args.max_steps)
    lines = output + ([f"runtime error: {error.message} (TAC line {error.line})"] if error else [])
    (out / "output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[5/5] execution          {bad if error else ok} {steps} steps"
          f"{' ' * max(1, 13 - len(str(steps)))}output.txt")
    print("\n--- program output ---")
    print("\n".join(lines) if lines else "(no output)")
    return 1 if error else 0


def _fail(r: CompilationResult, name: str) -> int:
    print()
    print_diagnostics(r, name, sys.stdout)
    print(f"\ncompilation stopped in the {r.failed_phase} phase.")
    return 1
