"""Phase 1 - Lexical analysis (scanner).

Turns source text into an ordered list of tokens using regular expressions.
Each token records its kind, its lexeme and its 1-based line/column.

Rules are tried in order. Two-character operators (<=, ==, &&, ...) are listed
before their one-character prefixes (<, =, !) so the longest lexeme wins.
Identifiers that match a keyword are re-classified as that keyword.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from common.diagnostics import Diagnostic

KEYWORDS = {
    "int": "INT", "bool": "BOOL", "if": "IF", "else": "ELSE",
    "while": "WHILE", "print": "PRINT", "true": "TRUE", "false": "FALSE",
}

# (token kind, regex). Order matters.
TOKEN_RULES = [
    ("COMMENT",        r"//[^\n]*|/\*[\s\S]*?\*/"),
    ("WHITESPACE",     r"\s+"),
    ("BAD_NUMBER",     r"[0-9]+[a-zA-Z_][a-zA-Z0-9_]*"),     # e.g. 9lives
    ("NUMBER",         r"[0-9]+"),
    ("IDENTIFIER",     r"[a-zA-Z_][a-zA-Z0-9_]*"),
    ("LESS_EQUAL",     r"<="),
    ("GREATER_EQUAL",  r">="),
    ("EQUAL",          r"=="),
    ("NOT_EQUAL",      r"!="),
    ("AND",            r"&&"),
    ("OR",             r"\|\|"),
    ("LESS",           r"<"),
    ("GREATER",        r">"),
    ("ASSIGN",         r"="),
    ("NOT",            r"!"),
    ("PLUS",           r"\+"),
    ("MINUS",          r"-"),
    ("STAR",           r"\*"),
    ("SLASH",          r"/"),
    ("PERCENT",        r"%"),
    ("LPAREN",         r"\("),
    ("RPAREN",         r"\)"),
    ("LBRACE",         r"\{"),
    ("RBRACE",         r"\}"),
    ("SEMICOLON",      r";"),
    ("COMMA",          r","),
]

COMPILED_RULES = [(kind, re.compile(pattern)) for kind, pattern in TOKEN_RULES]
BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
SKIPPED = {"WHITESPACE", "COMMENT"}
HINTS = {"&": "did you mean '&&'?", "|": "did you mean '||'?"}

# Every token kind the parser may receive (the scanner/parser contract).
TOKEN_KINDS = sorted({k for k, _ in TOKEN_RULES if k not in SKIPPED | {"BAD_NUMBER"}}
                     | set(KEYWORDS.values()) | {"EOF"})


@dataclass(frozen=True)
class Token:
    kind: str
    lexeme: str
    line: int
    column: int

    def to_dict(self) -> dict:
        return {"kind": self.kind, "lexeme": self.lexeme,
                "line": self.line, "column": self.column}


class Scanner:
    def __init__(self, text: str):
        self.text = text
        self.pos, self.line, self.column = 0, 1, 1
        self.tokens: list[Token] = []
        self.errors: list[Diagnostic] = []

    def _advance(self, lexeme: str) -> None:
        """Move past `lexeme`, keeping line and column up to date."""
        newlines = lexeme.count("\n")
        if newlines:
            self.line += newlines
            self.column = len(lexeme) - lexeme.rfind("\n")
        else:
            self.column += len(lexeme)
        self.pos += len(lexeme)

    def _error(self, message: str, hint: str | None = None) -> None:
        self.errors.append(Diagnostic("lexical", message, self.line, self.column, hint=hint))

    def scan(self) -> tuple[list[Token], list[Diagnostic]]:
        text = self.text
        while self.pos < len(text):
            if text.startswith("/*", self.pos) and not BLOCK_COMMENT.match(text, self.pos):
                self._error("unterminated block comment", "close it with '*/'")
                break

            for kind, regex in COMPILED_RULES:
                match = regex.match(text, self.pos)
                if match:
                    break
            else:                                    # no rule matched
                char = text[self.pos]
                self._error(f"invalid character '{char}'", HINTS.get(char))
                self._advance(char)
                continue

            lexeme = match.group()
            if kind == "BAD_NUMBER":
                self._error(f"malformed number '{lexeme}'",
                            "identifiers cannot start with a digit")
            elif kind not in SKIPPED:
                if kind == "IDENTIFIER":
                    kind = KEYWORDS.get(lexeme, "IDENTIFIER")
                self.tokens.append(Token(kind, lexeme, self.line, self.column))
            self._advance(lexeme)
        return self.tokens, self.errors


def scan(text: str) -> tuple[list[Token], list[Diagnostic]]:
    """Public entry point: source text -> (tokens, lexical diagnostics)."""
    return Scanner(text).scan()
