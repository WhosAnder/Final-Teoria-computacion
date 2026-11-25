"""Shared diagnostic type used by every phase of the compiler.

Every error or warning carries the phase that produced it, a message, a
1-based line/column position and, when useful, a short hint. Using one type
everywhere keeps error reporting uniform across the pipeline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

PHASES = ("lexical", "syntax", "semantic", "runtime")


@dataclass
class Diagnostic:
    phase: str                      # one of PHASES
    message: str
    line: int
    column: int
    category: Optional[str] = None  # semantic error class, or "warning"
    hint: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(data: dict) -> "Diagnostic":
        return Diagnostic(data["phase"], data["message"], data["line"], data["column"],
                          data.get("category"), data.get("hint"))


def format_diagnostic(diag: Diagnostic, source: str, severity: str = "error") -> str:
    """Render a diagnostic as `file:line:col: phase error: message`, followed by
    the offending source line and a caret under the column."""
    head = f"{diag.line}:{diag.column}: {diag.phase} {severity}: {diag.message}"
    lines = source.splitlines()
    if 1 <= diag.line <= len(lines):
        src_line = lines[diag.line - 1].replace("\t", " ")
        head += f"\n    {src_line}\n    {' ' * max(diag.column - 1, 0)}^"
    if diag.hint:
        head += f"\n    hint: {diag.hint}"
    return head
