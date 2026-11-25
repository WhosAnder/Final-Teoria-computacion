"""Phase 5 - Execution: an interpreter (virtual machine) for Three-Address Code.

Loading: every line is parsed into an instruction tuple and every label is
mapped to the index of the instruction that follows it. Unknown instructions
or jumps to undefined labels are rejected before execution starts.

Execution: a program counter walks the instruction list; variables live in a
dictionary (the VM's memory). Integer division truncates toward zero, as in C.
Run-time errors (division by zero, read of an unset variable, step limit
exceeded) stop the machine with a diagnostic that points at the TAC line.
"""
from __future__ import annotations

import operator
import re

INT_LITERAL = re.compile(r"-?\d+")
NAME = re.compile(r"[A-Za-z_]\w*")


class TACRuntimeError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(message)
        self.message, self.line = message, line


def c_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def c_mod(a: int, b: int) -> int:
    return a - b * c_div(a, b)


BINARY = {
    "+": operator.add, "-": operator.sub, "*": operator.mul, "/": c_div, "%": c_mod,
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
    "==": operator.eq, "!=": operator.ne,
}
UNARY = {"-": operator.neg, "!": operator.not_}


def load(text: str):
    """Parse TAC text -> (instructions, label table). Raises TACRuntimeError."""
    program, labels = [], {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        # Leading labels, possibly on the same line as an instruction ("L1: x := 1").
        while True:
            m = re.match(r"([A-Za-z_]\w*):(?!=)\s*", line)
            if not m:
                break
            labels[m.group(1)] = len(program)
            line = line[m.end():]
        if not line:
            continue
        p = line.split()
        if p[0] == "goto" and len(p) == 2:
            program.append(("goto", p[1], lineno))
        elif p[0] in ("if", "ifFalse") and p[-2] == "goto" and len(p) in (4, 6):
            cond = p[1:-2]
            if len(cond) == 3 and cond[1] not in BINARY:
                raise TACRuntimeError(f"unknown operator in '{line}'", lineno)
            program.append((p[0], cond, p[-1], lineno))
        elif p[0] == "print" and len(p) == 2:
            program.append(("print", p[1], lineno))
        elif len(p) >= 3 and p[1] == ":=" and NAME.fullmatch(p[0]):
            rhs = p[2:]
            if len(rhs) == 1:
                program.append(("copy", p[0], rhs[0], lineno))
            elif len(rhs) == 2 and rhs[0] in UNARY:
                program.append(("unary", p[0], rhs[0], rhs[1], lineno))
            elif len(rhs) == 3 and rhs[1] in BINARY:
                program.append(("binary", p[0], rhs[0], rhs[1], rhs[2], lineno))
            else:
                raise TACRuntimeError(f"invalid TAC instruction '{line}'", lineno)
        else:
            raise TACRuntimeError(f"invalid TAC instruction '{line}'", lineno)

    for ins in program:
        target = ins[1] if ins[0] == "goto" else ins[2] if ins[0] in ("if", "ifFalse") else None
        if target is not None and target not in labels:
            raise TACRuntimeError(f"jump to undefined label '{target}'", ins[-1])
    return program, labels


def format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class TACMachine:
    def __init__(self, max_steps: int = 1_000_000):
        self.max_steps = max_steps
        self.memory: dict = {}
        self.output: list[str] = []
        self.steps = 0

    def value(self, operand: str, lineno: int):
        if INT_LITERAL.fullmatch(operand):
            return int(operand)
        if operand in ("true", "false"):
            return operand == "true"
        if operand not in self.memory:
            raise TACRuntimeError(f"read of unset variable '{operand}'", lineno)
        return self.memory[operand]

    def compute(self, a, op, b, lineno):
        try:
            return BINARY[op](self.value(a, lineno), self.value(b, lineno))
        except ZeroDivisionError:
            raise TACRuntimeError("division by zero", lineno) from None

    def test(self, cond: list[str], lineno: int) -> bool:
        if len(cond) == 1:
            return bool(self.value(cond[0], lineno))
        return bool(self.compute(cond[0], cond[1], cond[2], lineno))

    def run(self, text: str) -> list[str]:
        program, labels = load(text)
        pc = 0
        while pc < len(program):
            self.steps += 1
            if self.steps > self.max_steps:
                raise TACRuntimeError(f"step limit of {self.max_steps} exceeded "
                                      f"(infinite loop?)", program[pc][-1])
            ins = program[pc]
            kind, lineno = ins[0], ins[-1]
            pc += 1
            if kind == "copy":
                self.memory[ins[1]] = self.value(ins[2], lineno)
            elif kind == "unary":
                self.memory[ins[1]] = UNARY[ins[2]](self.value(ins[3], lineno))
            elif kind == "binary":
                self.memory[ins[1]] = self.compute(ins[2], ins[3], ins[4], lineno)
            elif kind == "goto":
                pc = labels[ins[1]]
            elif kind == "if":
                if self.test(ins[1], lineno):
                    pc = labels[ins[2]]
            elif kind == "ifFalse":
                if not self.test(ins[1], lineno):
                    pc = labels[ins[2]]
            elif kind == "print":
                self.output.append(format_value(self.value(ins[1], lineno)))
        return self.output
