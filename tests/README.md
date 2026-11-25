# Test suite

```bash
python scripts/run_tests.py          # 16 end-to-end tests: compares TAC and output with tests/expected/
python scripts/run_tests.py -v       # also prints a diff for each failure
python -m unittest discover -s tests/unit -v    # 38 unit tests
```

There are no `*.in` files because Mini-Lang has no input statement. Every program is deterministic.

## Expected files

Each program `tests/programs/<name>.src` has expected files in `tests/expected/`:

- `<name>.tac` holds the expected Three-Address Code. It exists only for programs that compile.
- `<name>.out` holds the expected program output. For programs that must fail to compile, it holds the expected diagnostics instead.

Every expected value was worked out by hand and is written as a comment next to the statement that produces it in the `.src` file. When the compiler changes on purpose, run `python scripts/run_tests.py --update` and review `git diff tests/expected` before committing.

| Category | Tests | What they cover |
|---|---|---|
| Basic (4) | `b01`–`b04` | declarations and default values, assignments, arithmetic precedence and associativity, relational and logical operators |
| Control flow (4) | `c01`–`c04` | if/else, while, nested loops with else-if, short-circuit evaluation |
| Semantic errors (2) | `s01`, `s02` | undeclared identifier (including one used out of scope), type errors |
| Integration (2) | `i01`, `i02` | prime numbers below 30; Fibonacci, GCD, Collatz and nested scopes |
| Extra negative (4) | `x01`–`x04` | lexical errors, syntax errors with recovery, duplicate declaration, division by zero at run time |

**Rubric (Evaluate):** the suite covers positive, negative and run-time cases in every phase. Results are compared mechanically against reviewed expected files, not inspected by eye.
