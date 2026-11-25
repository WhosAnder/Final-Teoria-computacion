"""Phase 3 - Semantic analysis.

Walks the AST with a stack of scopes (one per { } block), builds the symbol
table and enforces the static rules of Mini-Lang:

  R1  a variable must be declared before it is used    -> undeclared_variables
  R2  no duplicate declaration in the same scope        -> duplicate_declarations
  R3  operands/assignments must have compatible types   -> type_errors
  R4  if/while conditions must have type bool           -> invalid_conditions

An inner declaration may shadow an outer one. To keep shadowed variables apart
in the generated code, every symbol gets a unique storage name (x, x_1, ...).
Names of the form t<N> are reserved for TAC temporaries.

Output: the symbol table and the AST annotated with "type" and "storage".
"""
from __future__ import annotations

import re

from common.diagnostics import Diagnostic

ARITHMETIC = {"+", "-", "*", "/", "%"}
RELATIONAL = {"<", "<=", ">", ">="}
EQUALITY = {"==", "!="}
LOGICAL = {"&&", "||"}

CATEGORIES = ["undeclared_variables", "duplicate_declarations",
              "type_errors", "invalid_conditions"]
TEMP_NAME = re.compile(r"t\d+")


def article(type_name: str) -> str:
    return f"an {type_name}" if type_name == "int" else f"a {type_name}"


def operator_signature(op: str) -> tuple[str | None, str]:
    """(operand type, result type). Operand type None means 'both sides equal'."""
    if op in ARITHMETIC:
        return "int", "int"
    if op in RELATIONAL:
        return "int", "bool"
    if op in LOGICAL:
        return "bool", "bool"
    return None, "bool"                      # == and != work on int or bool


class SemanticAnalyzer:
    def __init__(self):
        self.scopes: list[dict] = []
        self.symbols: list[dict] = []
        self.errors: list[Diagnostic] = []
        self.warnings: list[Diagnostic] = []
        self.storage_names: set[str] = set()

    # ---------------------------------------------------------------- helpers
    def error(self, category: str, message: str, node: dict, hint: str | None = None):
        self.errors.append(Diagnostic("semantic", message, node["line"], node["column"],
                                      category, hint))

    def warn(self, message: str, node: dict):
        self.warnings.append(Diagnostic("semantic", message, node["line"], node["column"],
                                        "warning"))

    def lookup(self, name: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def new_storage(self, name: str) -> str:
        candidate, k = name, 0
        while candidate in self.storage_names or TEMP_NAME.fullmatch(candidate):
            k += 1
            candidate = f"{name}_{k}"
        self.storage_names.add(candidate)
        return candidate

    # ---------------------------------------------------------------- driver
    def analyze(self, ast: dict) -> dict:
        self.visit(ast)
        for sym in self.symbols:
            if not sym["used"]:
                self.warn(f"variable '{sym['name']}' is declared but never used", sym)
        summary = {c: sum(1 for e in self.errors if e.category == c) for c in CATEGORIES}
        summary["warnings"] = len(self.warnings)
        return {
            "status": "FAILED" if self.errors else "PASSED",
            "summary": summary,
            "symbol_table": [{k: s[k] for k in ("name", "type", "scope", "storage",
                                                "line", "column", "used")}
                             for s in self.symbols],
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "annotated_ast": ast,
        }

    def visit(self, node: dict) -> None:
        getattr(self, f"visit_{node['node']}")(node)

    # ------------------------------------------------------------- statements
    def visit_Program(self, node):
        self._scoped(node)

    def visit_Block(self, node):
        self._scoped(node)

    def _scoped(self, node):
        self.scopes.append({})
        for stmt in node["body"]:
            self.visit(stmt)
        self.scopes.pop()

    def visit_Declaration(self, node):
        name, scope = node["name"], self.scopes[-1]
        if name in scope:
            first = scope[name]
            self.error("duplicate_declarations",
                       f"variable '{name}' is already declared in this scope "
                       f"(line {first['line']})", node,
                       "remove the second declaration or rename it")
            node["storage"] = first["storage"]
            return
        if self.lookup(name) is not None:
            self.warn(f"variable '{name}' shadows a variable from an outer scope", node)
        symbol = {"name": name, "type": node["var_type"], "scope": len(self.scopes) - 1,
                  "storage": self.new_storage(name), "line": node["line"],
                  "column": node["column"], "used": False, "assigned": False,
                  "warned": False}
        scope[name] = symbol
        self.symbols.append(symbol)
        node["storage"] = symbol["storage"]

    def visit_Assignment(self, node):
        value_type = self.expression(node["value"])
        symbol = self.lookup(node["target"])
        if symbol is None:
            self.error("undeclared_variables",
                       f"variable '{node['target']}' is not declared", node,
                       f"declare it first, e.g. 'int {node['target']};'")
            return
        node["storage"], node["target_type"] = symbol["storage"], symbol["type"]
        if value_type is not None and value_type != symbol["type"]:
            self.error("type_errors",
                       f"type mismatch: cannot assign {article(value_type)} value to "
                       f"'{node['target']}' of type {symbol['type']}", node)
        symbol["assigned"] = True

    def _condition(self, node, statement: str):
        cond_type = self.expression(node["condition"])
        if cond_type is not None and cond_type != "bool":
            self.error("invalid_conditions",
                       f"{statement} condition must be bool, but it is {cond_type}",
                       node["condition"], "use a comparison, e.g. (x != 0)")

    def visit_While(self, node):
        self._condition(node, "while")
        self.visit(node["body"])

    def visit_If(self, node):
        self._condition(node, "if")
        self.visit(node["then"])
        if node["else"] is not None:
            self.visit(node["else"])

    def visit_Print(self, node):
        self.expression(node["expression"])

    # ------------------------------------------------------------ expressions
    def expression(self, node: dict):
        """Return the type of an expression ('int' / 'bool'), or None on error."""
        result = getattr(self, f"expr_{node['node']}")(node)
        if result is not None:
            node["type"] = result
        return result

    def expr_IntegerLiteral(self, node):
        return "int"

    def expr_BooleanLiteral(self, node):
        return "bool"

    def expr_Identifier(self, node):
        symbol = self.lookup(node["name"])
        if symbol is None:
            self.error("undeclared_variables", f"variable '{node['name']}' is not declared",
                       node, f"declare it first, e.g. 'int {node['name']};'")
            return None
        symbol["used"] = True
        node["storage"] = symbol["storage"]
        if not symbol["assigned"] and not symbol["warned"]:
            symbol["warned"] = True
            default = "0" if symbol["type"] == "int" else "false"
            self.warn(f"variable '{node['name']}' is used before being assigned "
                      f"(it holds its default value {default})", node)
        return symbol["type"]

    def expr_UnaryOp(self, node):
        operand = self.expression(node["operand"])
        expected = "int" if node["operator"] == "-" else "bool"
        if operand is not None and operand != expected:
            self.error("type_errors", f"operator '{node['operator']}' expects {article(expected)} "
                       f"operand, got {operand}", node)
        return expected

    def expr_BinaryOp(self, node):
        op = node["operator"]
        left = self.expression(node["left"])
        right = self.expression(node["right"])
        operand_type, result = operator_signature(op)

        if operand_type is None:                       # == / !=
            if left is not None and right is not None and left != right:
                self.error("type_errors", f"cannot compare {left} {op} {right}: "
                           f"both sides must have the same type", node)
        else:
            for side, side_type in (("left", left), ("right", right)):
                if side_type is not None and side_type != operand_type:
                    self.error("type_errors", f"operator '{op}' expects {operand_type} "
                               f"operands, but the {side} side is {side_type}", node)

        if op in ("/", "%") and node["right"]["node"] == "IntegerLiteral" \
                and node["right"]["value"] == 0:
            self.warn("division by the constant 0 will fail at run time", node)
        return result


def analyze(ast: dict) -> dict:
    """Public entry point: AST -> semantic result (status, symbol table, annotated AST)."""
    return SemanticAnalyzer().analyze(ast)


def semantic_report(result: dict) -> str:
    s = result["summary"]
    return (f"SEMANTIC ANALYSIS: {result['status']}\n\n"
            f"Undeclared variables: {s['undeclared_variables']}\n"
            f"Duplicate declarations: {s['duplicate_declarations']}\n"
            f"Type errors: {s['type_errors']}\n"
            f"Invalid conditions: {s['invalid_conditions']}")
