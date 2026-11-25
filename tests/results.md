| Test | Category | Expected result | Checked | Status |
|---|---|---|---|---|
| `b01_declarations` | basic | runs | TAC + output | PASS |
| `b02_assignments` | basic | runs | TAC + output | PASS |
| `b03_arithmetic` | basic | runs | TAC + output | PASS |
| `b04_relational_logical` | basic | runs | TAC + output | PASS |
| `c01_if_else` | control-flow | runs | TAC + output | PASS |
| `c02_while` | control-flow | runs | TAC + output | PASS |
| `c03_nested` | control-flow | runs | TAC + output | PASS |
| `c04_short_circuit` | control-flow | runs | TAC + output | PASS |
| `i01_primes` | integration | runs | TAC + output | PASS |
| `i02_full_program` | integration | runs | TAC + output | PASS |
| `s01_undeclared` | semantic-error | fails in semantic | diagnostics | PASS |
| `s02_type_error` | semantic-error | fails in semantic | diagnostics | PASS |
| `x01_lexical_error` | extra-negative | fails in lexical | diagnostics | PASS |
| `x02_syntax_error` | extra-negative | fails in syntax | diagnostics | PASS |
| `x03_duplicate_declaration` | extra-negative | fails in semantic | diagnostics | PASS |
| `x04_runtime_error` | extra-negative | fails in runtime | TAC + output | PASS |

**16/16 passed** (6 negative tests)
