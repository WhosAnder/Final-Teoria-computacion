"""Chains the five phases. Compilation stops at the first phase that reports
errors (fail fast); warnings never stop it.

    source --scan--> tokens --parse--> AST --analyze--> annotated AST
           --generate--> TAC --run--> output
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from common.diagnostics import Diagnostic
from ir.tac_generator import generate, to_text
from lexer.scanner import Token, scan
from parser.parser import parse
from runtime.tac_vm import TACMachine, TACRuntimeError
from semantics.analyzer import analyze


@dataclass
class CompilationResult:
    source: str
    tokens: list[Token] = field(default_factory=list)
    lexical_errors: list[Diagnostic] = field(default_factory=list)
    ast: Optional[dict] = None
    syntax_errors: list[Diagnostic] = field(default_factory=list)
    semantic: Optional[dict] = None
    tac: Optional[list[str]] = None
    output: Optional[list[str]] = None
    runtime_error: Optional[Diagnostic] = None
    failed_phase: Optional[str] = None
    steps: int = 0

    @property
    def ok(self) -> bool:
        return self.failed_phase is None

    @property
    def tac_text(self) -> str:
        return to_text(self.tac or [])

    @property
    def errors(self) -> list[Diagnostic]:
        if self.failed_phase == "lexical":
            return self.lexical_errors
        if self.failed_phase == "syntax":
            return self.syntax_errors
        if self.failed_phase == "semantic":
            return [Diagnostic.from_dict(e) for e in self.semantic["errors"]]
        if self.failed_phase == "runtime":
            return [self.runtime_error]
        return []


def compile_source(source: str) -> CompilationResult:
    """Run phases 1-4 (front end + code generation)."""
    result = CompilationResult(source)

    result.tokens, result.lexical_errors = scan(source)
    if result.lexical_errors:
        result.failed_phase = "lexical"
        return result

    result.ast, result.syntax_errors = parse(result.tokens)
    if result.syntax_errors:
        result.failed_phase = "syntax"
        return result

    result.semantic = analyze(copy.deepcopy(result.ast))
    if result.semantic["status"] == "FAILED":
        result.failed_phase = "semantic"
        return result

    result.tac = generate(result.semantic["annotated_ast"])
    return result


def run_tac(text: str, max_steps: int = 1_000_000):
    """Phase 5: execute TAC text. Returns (output lines, runtime Diagnostic | None, steps)."""
    machine = TACMachine(max_steps=max_steps)
    try:
        machine.run(text)
        return machine.output, None, machine.steps
    except TACRuntimeError as err:
        return machine.output, Diagnostic("runtime", err.message, err.line, 0), machine.steps


def compile_and_run(source: str, max_steps: int = 1_000_000) -> CompilationResult:
    result = compile_source(source)
    if result.ok:
        result.output, result.runtime_error, result.steps = run_tac(result.tac_text, max_steps)
        if result.runtime_error:
            result.failed_phase = "runtime"
    return result
