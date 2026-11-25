"""Unit tests, one class per compiler phase.

Run from the repository root:   python -m unittest discover -s tests/unit -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from driver.pipeline import compile_and_run, compile_source   # noqa: E402
from ir.basic_blocks import build_cfg                          # noqa: E402
from lexer.scanner import scan                                 # noqa: E402
from parser.parser import parse                                # noqa: E402
from runtime.tac_vm import TACMachine, TACRuntimeError          # noqa: E402
from semantics.analyzer import analyze                         # noqa: E402


def kinds(text):
    tokens, errors = scan(text)
    assert errors == [], errors
    return [t.kind for t in tokens]


def ast_of(text):
    tokens, _ = scan(text)
    ast, errors = parse(tokens)
    assert errors == [], errors
    return ast


def tac_of(text):
    r = compile_source(text)
    assert r.ok, r.errors
    return [line.strip() for line in r.tac]


class ScannerTests(unittest.TestCase):
    def test_simple_assignment(self):
        tokens, _ = scan("x = 1;")
        self.assertEqual([(t.kind, t.lexeme) for t in tokens],
                         [("IDENTIFIER", "x"), ("ASSIGN", "="), ("NUMBER", "1"), ("SEMICOLON", ";")])

    def test_all_keywords(self):
        self.assertEqual(kinds("int bool if else while print true false"),
                         ["INT", "BOOL", "IF", "ELSE", "WHILE", "PRINT", "TRUE", "FALSE"])

    def test_longest_match_operators(self):
        self.assertEqual(kinds("<= < >= > == = != ! && ||"),
                         ["LESS_EQUAL", "LESS", "GREATER_EQUAL", "GREATER", "EQUAL",
                          "ASSIGN", "NOT_EQUAL", "NOT", "AND", "OR"])

    def test_delimiters_including_comma(self):
        self.assertEqual(kinds("( ) { } ; ,"),
                         ["LPAREN", "RPAREN", "LBRACE", "RBRACE", "SEMICOLON", "COMMA"])

    def test_keyword_prefix_is_identifier(self):
        self.assertEqual(kinds("integer whiles iff"), ["IDENTIFIER"] * 3)

    def test_line_and_column(self):
        tokens, _ = scan("int x;\n  x = 10;")
        self.assertEqual((tokens[3].lexeme, tokens[3].line, tokens[3].column), ("x", 2, 3))
        self.assertEqual((tokens[5].lexeme, tokens[5].column), ("10", 7))

    def test_comments_are_skipped(self):
        tokens, errors = scan("// one\nx /* multi\nline */ = 1;")
        self.assertEqual(errors, [])
        self.assertEqual(len(tokens), 4)
        self.assertEqual(tokens[1].line, 3)

    def test_lexical_errors_have_hints(self):
        _, errors = scan("x = 5 @ 3; int 9lives; x = x & 1; /* open")
        self.assertEqual(len(errors), 4)
        self.assertIn("'@'", errors[0].message)
        self.assertIn("digit", errors[1].hint)
        self.assertIn("&&", errors[2].hint)
        self.assertIn("unterminated", errors[3].message)


class ParserTests(unittest.TestCase):
    def test_assignment_node(self):
        node = ast_of("x = 1;")["body"][0]
        self.assertEqual((node["node"], node["target"]), ("Assignment", "x"))
        self.assertEqual(node["value"], {"node": "IntegerLiteral", "value": 1,
                                         "line": 1, "column": 5})

    def test_precedence_mul_over_add(self):
        value = ast_of("x = 1 + 2 * 3;")["body"][0]["value"]
        self.assertEqual((value["operator"], value["right"]["operator"]), ("+", "*"))

    def test_precedence_and_over_or(self):
        value = ast_of("b = a || c && d;")["body"][0]["value"]
        self.assertEqual((value["operator"], value["right"]["operator"]), ("||", "&&"))

    def test_left_associativity(self):
        value = ast_of("x = 10 - 3 - 2;")["body"][0]["value"]
        self.assertEqual(value["left"]["operator"], "-")          # (10 - 3) - 2
        self.assertEqual(value["right"]["value"], 2)

    def test_unary_binds_tighter(self):
        value = ast_of("x = -a * b;")["body"][0]["value"]
        self.assertEqual((value["operator"], value["left"]["node"]), ("*", "UnaryOp"))

    def test_else_if_chain(self):
        stmt = ast_of("if (a) { } else if (b) { } else { }")["body"][0]
        self.assertEqual(stmt["else"]["node"], "If")
        self.assertEqual(stmt["else"]["else"]["node"], "Block")

    def test_recovery_reports_every_error(self):
        tokens, _ = scan("int y\nx = 10;\nwhile (x > 0 { x = x - 1; }\nprint(x;\ny = ;")
        _, errors = parse(tokens)
        self.assertEqual([e.line for e in errors], [1, 3, 4, 5])

    def test_missing_closing_brace(self):
        tokens, _ = scan("while (true) { x = 1;")
        _, errors = parse(tokens)
        self.assertEqual(len(errors), 1)
        self.assertIn("'}'", errors[0].message)

    def test_comma_is_rejected_by_grammar(self):
        tokens, _ = scan("int x, y;")
        _, errors = parse(tokens)
        self.assertIn("';'", errors[0].message)


class SemanticTests(unittest.TestCase):
    def check(self, text):
        return analyze(ast_of(text))

    def counts(self, text):
        s = self.check(text)["summary"]
        return (s["undeclared_variables"], s["duplicate_declarations"],
                s["type_errors"], s["invalid_conditions"])

    def test_valid_program_passes(self):
        r = self.check("int x; bool ok; x = 1; ok = x == 1; if (ok) { print(x); }")
        self.assertEqual(r["status"], "PASSED")
        self.assertEqual({s["name"]: s["type"] for s in r["symbol_table"]},
                         {"x": "int", "ok": "bool"})

    def test_each_rule(self):
        self.assertEqual(self.counts("y = 1;"), (1, 0, 0, 0))
        self.assertEqual(self.counts("int a; int a;"), (0, 1, 0, 0))
        self.assertEqual(self.counts("int a; a = true;"), (0, 0, 1, 0))
        self.assertEqual(self.counts("int a; while (a) { }"), (0, 0, 0, 1))
        self.assertEqual(self.counts("int a; if (a + 1) { }"), (0, 0, 0, 1))

    def test_operator_type_rules(self):
        self.assertEqual(self.counts("bool b; int n; n = b + 1;"), (0, 0, 1, 0))
        self.assertEqual(self.counts("bool b; b = 1 && true;"), (0, 0, 1, 0))
        self.assertEqual(self.counts("bool b; b = !3;"), (0, 0, 1, 0))
        self.assertEqual(self.counts("int n; n = -true;"), (0, 0, 1, 0))
        self.assertEqual(self.counts("bool b; b = 1 == true;"), (0, 0, 1, 0))
        self.assertEqual(self.counts("bool b; b = true == false;"), (0, 0, 0, 0))

    def test_errors_do_not_cascade(self):
        # 'z' is undeclared; the enclosing '+' must not add a second type error.
        self.assertEqual(self.counts("int n; n = z + 1;"), (1, 0, 0, 0))

    def test_types_are_annotated(self):
        ast = self.check("int x; bool b; b = x + 1 > 2;")["annotated_ast"]
        value = ast["body"][2]["value"]
        self.assertEqual((value["type"], value["left"]["type"]), ("bool", "int"))

    def test_scopes_shadowing_and_storage(self):
        r = self.check("int x; x = 0; { int x; x = 2; print(x); } { int x; x = 3; print(x); } print(x);")
        self.assertEqual(r["status"], "PASSED")
        self.assertEqual([s["storage"] for s in r["symbol_table"]], ["x", "x_1", "x_2"])

    def test_out_of_scope(self):
        self.assertEqual(self.counts("{ int y; y = 1; } y = 2;"), (1, 0, 0, 0))

    def test_temporary_names_are_reserved(self):
        r = self.check("int t1; t1 = 5; print(t1);")
        self.assertEqual(r["symbol_table"][0]["storage"], "t1_1")


class CodegenTests(unittest.TestCase):
    def test_assignment_example_from_statement(self):
        self.assertEqual(tac_of("int a; int x; a = 0; x = a + 3;")[-2:],
                         ["t1 := a + 3", "x := t1"])

    def test_conditional_example_from_statement(self):
        code = tac_of("int x; int y; int z; if (x < y) { z = 1; } else { z = 0; }")
        self.assertEqual(code[3:], ["if x < y goto L1", "z := 0", "goto L2",
                                    "L1:", "z := 1", "L2:"])

    def test_while_shape(self):
        code = tac_of("int i; while (i < 3) { i = i + 1; }")
        self.assertEqual(code[1:], ["L1:", "ifFalse i < 3 goto L2", "t1 := i + 1",
                                    "i := t1", "goto L1", "L2:"])

    def test_short_circuit_and(self):
        code = tac_of("bool a; bool b; bool c; c = a && b;")
        self.assertEqual(code[3:], ["t1 := a", "ifFalse t1 goto L1", "t1 := b", "L1:", "c := t1"])

    def test_shadowed_variables_get_distinct_storage(self):
        code = tac_of("int x; x = 1; { int x; x = 2; }")
        self.assertIn("x_1 := 2", code)

    def test_basic_blocks(self):
        r = compile_source("int i; while (i < 3) { i = i + 1; } print(i);")
        blocks = build_cfg(r.tac)
        self.assertEqual([b["successors"] for b in blocks], [["B2"], ["B4", "B3"], ["B2"], []])


class RuntimeTests(unittest.TestCase):
    def run_tac(self, text):
        vm = TACMachine()
        vm.run(text)
        return vm.output

    def test_arithmetic_and_print(self):
        self.assertEqual(self.run_tac("x := 7\nt1 := x * 6\nprint t1"), ["42"])

    def test_c_style_division(self):
        self.assertEqual(self.run_tac("a := -7 / 2\nb := -7 % 2\nprint a\nprint b"), ["-3", "-1"])

    def test_conditional_jump_with_comparison(self):
        self.assertEqual(self.run_tac("x := 1\nif x < 2 goto L1\nprint 0\nL1: print 1"), ["1"])

    def test_bool_printing(self):
        self.assertEqual(self.run_tac("b := ! false\nprint b"), ["true"])

    def test_undefined_label_is_rejected(self):
        with self.assertRaises(TACRuntimeError):
            self.run_tac("goto L9")

    def test_unset_variable(self):
        with self.assertRaises(TACRuntimeError):
            self.run_tac("print y")

    def test_step_limit(self):
        r = compile_and_run("while (true) { }", max_steps=500)
        self.assertEqual(r.failed_phase, "runtime")
        self.assertIn("step limit", r.runtime_error.message)


if __name__ == "__main__":
    unittest.main()
