"""Phase 2 - Syntax analysis (recursive-descent LL(1) parser).

Consumes the token stream and checks it against the context-free grammar in
docs/grammar.txt. Each non-terminal of the grammar is one method below. The
output is an AST (see ast_nodes.py).

Error recovery (panic mode): when a syntax error is found it is recorded and
tokens are skipped until a safe point (';', '}' or the start of a statement),
so several independent syntax errors can be reported in a single run.
"""
from __future__ import annotations

from common.diagnostics import Diagnostic
from lexer.scanner import Token
from parser.ast_nodes import make_node

DESCRIBE = {
    "SEMICOLON": "';'", "ASSIGN": "'='", "LPAREN": "'('", "RPAREN": "')'",
    "LBRACE": "'{'", "RBRACE": "'}'", "IDENTIFIER": "an identifier", "EOF": "end of file",
}
STATEMENT_START = {"INT", "BOOL", "IDENTIFIER", "WHILE", "IF", "PRINT", "LBRACE"}

# Binary operator precedence levels, lowest first. All are left-associative.
PRECEDENCE = [
    {"OR"},
    {"AND"},
    {"EQUAL", "NOT_EQUAL"},
    {"LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL"},
    {"PLUS", "MINUS"},
    {"STAR", "SLASH", "PERCENT"},
]


class ParseError(Exception):
    def __init__(self, message: str, line: int, column: int, hint: str | None = None):
        super().__init__(message)
        self.message, self.line, self.column, self.hint = message, line, column, hint


class Parser:
    def __init__(self, tokens: list[Token]):
        last = tokens[-1] if tokens else None
        eof = Token("EOF", "", last.line, last.column + len(last.lexeme)) if last \
            else Token("EOF", "", 1, 1)
        self.tokens = list(tokens) + [eof]
        self.pos = 0
        self.errors: list[Diagnostic] = []

    # ---------------------------------------------------------------- helpers
    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.peek()
        if token.kind != "EOF":
            self.pos += 1
        return token

    def check(self, *kinds: str) -> bool:
        return self.peek().kind in kinds

    def unexpected(self, expected: str) -> ParseError:
        token = self.peek()
        found = "end of file" if token.kind == "EOF" else f"'{token.lexeme}'"
        return ParseError(f"expected {expected} but found {found}", token.line, token.column)

    def expect(self, kind: str) -> Token:
        if self.check(kind):
            return self.advance()
        if kind == "SEMICOLON" and self.pos > 0:
            # A missing ';' is reported right after the previous token.
            prev = self.tokens[self.pos - 1]
            raise ParseError(f"expected ';' after '{prev.lexeme}'",
                             prev.line, prev.column + len(prev.lexeme),
                             "every declaration, assignment and print ends with ';'")
        raise self.unexpected(DESCRIBE.get(kind, kind))

    def synchronize(self) -> None:
        """Panic-mode recovery: skip tokens until a safe restart point."""
        while not self.check("EOF"):
            if self.check("SEMICOLON"):
                self.advance()
                return
            if self.check("RBRACE"):
                return
            kind = self.peek().kind
            if kind in STATEMENT_START - {"IDENTIFIER"}:
                return
            if kind == "IDENTIFIER" and self.peek(1).kind == "ASSIGN":
                return
            self.advance()

    # ---------------------------------------------------------------- grammar
    def parse_program(self) -> tuple[dict, list[Diagnostic]]:
        """program -> stmt_list EOF"""
        body = self.statement_list(stop={"EOF"})
        return {"node": "Program", "body": body, "line": 1, "column": 1}, self.errors

    def statement_list(self, stop: set[str]) -> list[dict]:
        """stmt_list -> stmt stmt_list | epsilon"""
        statements = []
        while not self.check("EOF", *stop):
            start = self.pos
            try:
                statements.append(self.statement())
            except ParseError as err:
                self.errors.append(Diagnostic("syntax", err.message, err.line,
                                              err.column, hint=err.hint))
                self.synchronize()
                if self.pos == start:            # guarantee progress
                    self.advance()
        return statements

    def statement(self) -> dict:
        """stmt -> declaration | assignment | while_stmt | if_stmt | print_stmt | block"""
        kind = self.peek().kind
        if kind in ("INT", "BOOL"):
            return self.declaration()
        if kind == "IDENTIFIER":
            return self.assignment()
        if kind == "WHILE":
            return self.while_statement()
        if kind == "IF":
            return self.if_statement()
        if kind == "PRINT":
            return self.print_statement()
        if kind == "LBRACE":
            return self.block()
        raise self.unexpected("a statement")

    def declaration(self) -> dict:
        """declaration -> type IDENTIFIER ;      type -> int | bool"""
        type_token = self.advance()
        name = self.expect("IDENTIFIER")
        self.expect("SEMICOLON")
        return make_node("Declaration", type_token, var_type=type_token.lexeme, name=name.lexeme)

    def assignment(self) -> dict:
        """assignment -> IDENTIFIER = expression ;"""
        target = self.advance()
        self.expect("ASSIGN")
        value = self.expression()
        self.expect("SEMICOLON")
        return make_node("Assignment", target, target=target.lexeme, value=value)

    def while_statement(self) -> dict:
        """while_stmt -> while ( expression ) block"""
        keyword = self.advance()
        self.expect("LPAREN")
        condition = self.expression()
        self.expect("RPAREN")
        return make_node("While", keyword, condition=condition, body=self.block())

    def if_statement(self) -> dict:
        """if_stmt -> if ( expression ) block else_part
           else_part -> else else_body | epsilon      else_body -> block | if_stmt"""
        keyword = self.advance()
        self.expect("LPAREN")
        condition = self.expression()
        self.expect("RPAREN")
        then_branch = self.block()
        else_branch = None
        if self.check("ELSE"):
            self.advance()
            else_branch = self.if_statement() if self.check("IF") else self.block()
        return make_node("If", keyword, condition=condition, then=then_branch,
                         **{"else": else_branch})

    def print_statement(self) -> dict:
        """print_stmt -> print ( expression ) ;"""
        keyword = self.advance()
        self.expect("LPAREN")
        expression = self.expression()
        self.expect("RPAREN")
        self.expect("SEMICOLON")
        return make_node("Print", keyword, expression=expression)

    def block(self) -> dict:
        """block -> { stmt_list }"""
        brace = self.expect("LBRACE")
        body = self.statement_list(stop={"RBRACE"})
        self.expect("RBRACE")
        return make_node("Block", brace, body=body)

    # ------------------------------------------------------------- expressions
    def expression(self) -> dict:
        """expression -> or_expr"""
        return self.binary(0)

    def binary(self, level: int) -> dict:
        """One method for every precedence level:
             level_i -> level_{i+1} tail_i
             tail_i  -> op_i level_{i+1} tail_i | epsilon
           The loop builds the tree left-associatively."""
        if level == len(PRECEDENCE):
            return self.unary()
        left = self.binary(level + 1)
        while self.check(*PRECEDENCE[level]):
            operator = self.advance()
            right = self.binary(level + 1)
            left = make_node("BinaryOp", operator, operator=operator.lexeme,
                             left=left, right=right)
        return left

    def unary(self) -> dict:
        """unary -> ! unary | - unary | primary"""
        if self.check("NOT", "MINUS"):
            operator = self.advance()
            return make_node("UnaryOp", operator, operator=operator.lexeme,
                             operand=self.unary())
        return self.primary()

    def primary(self) -> dict:
        """primary -> NUMBER | true | false | IDENTIFIER | ( expression )"""
        token = self.peek()
        if token.kind == "NUMBER":
            self.advance()
            return make_node("IntegerLiteral", token, value=int(token.lexeme))
        if token.kind in ("TRUE", "FALSE"):
            self.advance()
            return make_node("BooleanLiteral", token, value=token.kind == "TRUE")
        if token.kind == "IDENTIFIER":
            self.advance()
            return make_node("Identifier", token, name=token.lexeme)
        if token.kind == "LPAREN":
            self.advance()
            inner = self.expression()
            self.expect("RPAREN")
            return inner
        raise self.unexpected("an expression")


def parse(tokens: list[Token]) -> tuple[dict, list[Diagnostic]]:
    """Public entry point: tokens -> (AST, syntax diagnostics)."""
    return Parser(tokens).parse_program()
