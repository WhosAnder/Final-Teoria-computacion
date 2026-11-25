"""AST node contract shared by the parser, the semantic analyzer and codegen.

Nodes are plain dictionaries so they serialize directly to JSON. Every node has
a "node" key (its kind) plus "line" and "column". The fields of each kind are:

  Program        body: [stmt]
  Block          body: [stmt]
  Declaration    var_type: "int" | "bool", name: str
  Assignment     target: str, value: expr
  If             condition: expr, then: Block, else: Block | If | None
  While          condition: expr, body: Block
  Print          expression: expr
  BinaryOp       operator: str, left: expr, right: expr
  UnaryOp        operator: "-" | "!", operand: expr
  IntegerLiteral value: int
  BooleanLiteral value: bool
  Identifier     name: str

The semantic analyzer adds (and codegen relies on):
  expressions          "type": "int" | "bool"
  Declaration, Assignment, Identifier   "storage": unique storage name
"""
from __future__ import annotations

STATEMENTS = {"Declaration", "Assignment", "If", "While", "Print", "Block"}
EXPRESSIONS = {"BinaryOp", "UnaryOp", "IntegerLiteral", "BooleanLiteral", "Identifier"}


def make_node(kind: str, token, **fields) -> dict:
    node = {"node": kind}
    node.update(fields)
    node["line"] = token.line
    node["column"] = token.column
    return node
