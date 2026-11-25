"""Phase 4 - Code generation: validated AST -> Three-Address Code (TAC).

The full instruction set is documented in docs/language-spec.md, section 6.

Translation scheme (one rule per AST node kind):

  Declaration     x := 0          (int)   |  x := false   (bool)
  Assignment      x := <operand of the value>
  BinaryOp        tN := a op b              (+ - * / % < <= > >= == !=)
  && / ||         short-circuit: tN := a ; ifFalse/if tN goto Lend ; tN := b ; Lend:
  UnaryOp         tN := op a                (- !)
  If (with else)  if c goto Lthen ; <else> ; goto Lend ; Lthen: <then> ; Lend:
  If (no else)    ifFalse c goto Lend ; <then> ; Lend:
  While           Lstart: ifFalse c goto Lend ; <body> ; goto Lstart ; Lend:
  Print           print a

When a condition is a relational/equality comparison, the comparison is folded
into the jump (if x < y goto L1) instead of materializing a temporary.
"""
from __future__ import annotations

COMPARISONS = {"<", "<=", ">", ">=", "==", "!="}
INDENT = "    "


class TACGenerator:
    def __init__(self):
        self.code: list[str] = []
        self.temp_count = 0
        self.label_count = 0

    # ---------------------------------------------------------------- helpers
    def new_temp(self) -> str:
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self) -> str:
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, instruction: str) -> None:
        self.code.append(INDENT + instruction)

    def place(self, label: str) -> None:
        self.code.append(f"{label}:")

    def generate(self, ast: dict) -> list[str]:
        self.statement(ast)
        return self.code

    # ------------------------------------------------------------- statements
    def statement(self, node: dict) -> None:
        getattr(self, f"gen_{node['node']}")(node)

    def gen_Program(self, node):
        for stmt in node["body"]:
            self.statement(stmt)

    gen_Block = gen_Program

    def gen_Declaration(self, node):
        default = "0" if node["var_type"] == "int" else "false"
        self.emit(f"{node['storage']} := {default}")

    def gen_Assignment(self, node):
        self.emit(f"{node['storage']} := {self.expression(node['value'])}")

    def condition(self, node: dict) -> str:
        """Text placed between 'if'/'ifFalse' and 'goto'."""
        if node["node"] == "BinaryOp" and node["operator"] in COMPARISONS:
            left = self.expression(node["left"])
            right = self.expression(node["right"])
            return f"{left} {node['operator']} {right}"
        return self.expression(node)

    def gen_If(self, node):
        cond = self.condition(node["condition"])
        if node["else"] is None:
            end = self.new_label()
            self.emit(f"ifFalse {cond} goto {end}")
            self.statement(node["then"])
            self.place(end)
        else:
            then_label, end = self.new_label(), self.new_label()
            self.emit(f"if {cond} goto {then_label}")
            self.statement(node["else"])
            self.emit(f"goto {end}")
            self.place(then_label)
            self.statement(node["then"])
            self.place(end)

    def gen_While(self, node):
        start, end = self.new_label(), self.new_label()
        self.place(start)
        cond = self.condition(node["condition"])
        self.emit(f"ifFalse {cond} goto {end}")
        self.statement(node["body"])
        self.emit(f"goto {start}")
        self.place(end)

    def gen_Print(self, node):
        self.emit(f"print {self.expression(node['expression'])}")

    # ------------------------------------------------------------ expressions
    def expression(self, node: dict) -> str:
        """Emit code for an expression and return the operand holding its value."""
        return getattr(self, f"expr_{node['node']}")(node)

    def expr_IntegerLiteral(self, node):
        return str(node["value"])

    def expr_BooleanLiteral(self, node):
        return "true" if node["value"] else "false"

    def expr_Identifier(self, node):
        return node["storage"]

    def expr_UnaryOp(self, node):
        operand = self.expression(node["operand"])
        temp = self.new_temp()
        self.emit(f"{temp} := {node['operator']} {operand}")
        return temp

    def expr_BinaryOp(self, node):
        if node["operator"] in ("&&", "||"):
            return self.short_circuit(node)
        left = self.expression(node["left"])
        right = self.expression(node["right"])
        temp = self.new_temp()
        self.emit(f"{temp} := {left} {node['operator']} {right}")
        return temp

    def short_circuit(self, node):
        """a && b: b is evaluated only if a is true.  a || b: only if a is false."""
        temp = self.new_temp()
        self.emit(f"{temp} := {self.expression(node['left'])}")
        end = self.new_label()
        jump = "ifFalse" if node["operator"] == "&&" else "if"
        self.emit(f"{jump} {temp} goto {end}")
        self.emit(f"{temp} := {self.expression(node['right'])}")
        self.place(end)
        return temp


def generate(ast: dict) -> list[str]:
    """Public entry point: annotated AST -> list of TAC lines."""
    return TACGenerator().generate(ast)


TAC_HEADER = "# Three-Address Code generated by minilangc"


def to_text(code: list[str]) -> str:
    return TAC_HEADER + "\n" + "\n".join(code) + "\n"
