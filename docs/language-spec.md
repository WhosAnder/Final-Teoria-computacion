# Mini-Lang Language Specification (v1.0)

Mini-Lang is a small, statically typed, imperative language. A program is a sequence of statements, executed top to bottom. This document defines the language's lexical structure (§2), syntax (§3), static semantics (§4) and dynamic semantics (§5). It also gives the target code (§6) and the limits of the language (§7).

## 1. Example

```c
int x;
int sum;
bool ok;

x = 1;
sum = 0;
while (x <= 3) {
  sum = sum + x;
  x = x + 1;
}
ok = sum == 6;
if (ok) { print(sum); } else { print(0); }     // prints 6
```

## 2. Lexical structure

The scanner reads the source from left to right. At each position it tries the rules below in order and takes the first match. Two-character operators are listed before their one-character prefixes, so the longest lexeme always wins.

| Category | Token kinds and lexemes |
|---|---|
| Keywords | `INT` int, `BOOL` bool, `IF` if, `ELSE` else, `WHILE` while, `PRINT` print, `TRUE` true, `FALSE` false |
| Identifiers | `IDENTIFIER`: `[a-zA-Z_][a-zA-Z0-9_]*`, excluding keywords. Identifiers are case-sensitive. |
| Integers | `NUMBER`: `[0-9]+` (decimal, non-negative; a minus sign is the unary operator) |
| Arithmetic | `PLUS` +, `MINUS` -, `STAR` *, `SLASH` /, `PERCENT` % |
| Relational | `LESS` <, `LESS_EQUAL` <=, `GREATER` >, `GREATER_EQUAL` >=, `EQUAL` ==, `NOT_EQUAL` != |
| Logical | `AND` &&, `OR` \|\|, `NOT` ! |
| Assignment | `ASSIGN` = |
| Delimiters | `LPAREN` (, `RPAREN` ), `LBRACE` {, `RBRACE` }, `SEMICOLON` ;, `COMMA` , |
| Skipped | whitespace `\s+`, line comments `//…`, block comments `/* … */` (they do not nest) |

The scanner appends an `EOF` token at the end of the input. `COMMA` is recognized so that the token set matches the project statement, but no production of the grammar uses it.

The scanner reports these lexical errors:

- an invalid character, such as `@`, or a lone `&` or `|`
- a malformed number, meaning digits immediately followed by letters, such as `9lives`
- an unterminated block comment

## 3. Syntax

The grammar below is context-free and has no left recursion. `scripts/ll1_check.py` computes its FIRST and FOLLOW sets and confirms that it is **LL(1)**: 31 non-terminals, 59 productions and no conflicts in the predictive table. The complete grammar, including the expression levels, is in `docs/grammar.txt`.

```
program     → stmt_list EOF
stmt_list   → stmt stmt_list | ε
stmt        → declaration | assignment | while_stmt | if_stmt | print_stmt | block
declaration → type IDENTIFIER ;          type → int | bool
assignment  → IDENTIFIER = expression ;
while_stmt  → while ( expression ) block
if_stmt     → if ( expression ) block else_part
else_part   → else else_body | ε         else_body → block | if_stmt
print_stmt  → print ( expression ) ;
block       → { stmt_list }
expression  → or_expr
or_expr     → and_expr or_tail           or_tail → || and_expr or_tail | ε
   …          (one level per row of the precedence table below)
unary       → ! unary | - unary | primary
primary     → NUMBER | true | false | IDENTIFIER | ( expression )
```

The bodies of `if`, `else` and `while` must be blocks. Because of that rule there is no dangling-else ambiguity, and `else if` chains are allowed.

**Operator precedence** runs from lowest to highest. All binary operators are left-associative.

| Level | Operators | Operand types | Result |
|---|---|---|---|
| 1 | `\|\|` | bool, bool | bool |
| 2 | `&&` | bool, bool | bool |
| 3 | `==` `!=` | same type (int or bool) | bool |
| 4 | `<` `<=` `>` `>=` | int, int | bool |
| 5 | `+` `-` | int, int | int |
| 6 | `*` `/` `%` | int, int | int |
| 7 | unary `-` | int | int |
| 7 | unary `!` | bool | bool |

## 4. Static semantics (typing rules)

The type environment Γ is a stack of scopes. Each `{ … }` block, and the program itself, opens a new scope.

**R1 – declared before use.**

- An identifier *x* must be bound in some scope of Γ.
- The innermost binding wins. A declaration in an inner block may shadow an outer one; the compiler warns about it.
- A variable is not visible after the block that declared it ends.

**R2 – no duplicates.** The same name cannot be declared twice in the same scope.

**R3 – type consistency.** Expression types follow these rules:

```
Γ ⊢ n : int        Γ ⊢ true : bool       Γ ⊢ false : bool        Γ(x) = τ  ⟹  Γ ⊢ x : τ

Γ ⊢ e1 : int   Γ ⊢ e2 : int   op ∈ {+,-,*,/,%}           ⟹  Γ ⊢ e1 op e2 : int
Γ ⊢ e1 : int   Γ ⊢ e2 : int   op ∈ {<,<=,>,>=}           ⟹  Γ ⊢ e1 op e2 : bool
Γ ⊢ e1 : τ     Γ ⊢ e2 : τ     op ∈ {==,!=}, τ ∈ {int,bool}  ⟹  Γ ⊢ e1 op e2 : bool
Γ ⊢ e1 : bool  Γ ⊢ e2 : bool  op ∈ {&&,||}               ⟹  Γ ⊢ e1 op e2 : bool
Γ ⊢ e : int  ⟹  Γ ⊢ -e : int                Γ ⊢ e : bool  ⟹  Γ ⊢ !e : bool

Γ(x) = τ   Γ ⊢ e : τ   ⟹   x = e;  is well typed
```

Types are never converted implicitly. `int` and `bool` are distinct, so `x = true` with `int x` and `1 == true` are both type errors.

**R4 – boolean conditions.** In `if (e)` and `while (e)`, the condition must satisfy Γ ⊢ e : bool.

**Operator arity.** Arity is enforced by the grammar: every binary operator needs two operands and every unary operator needs one. R3 then checks the operand types.

**Error reporting.**

- All semantic errors are collected and reported together. An expression whose type cannot be determined (because of an undeclared name) does not produce a second error higher up.
- The analyzer also issues warnings, which do not stop compilation:
  - unused variable
  - use before assignment
  - shadowing
  - division by the constant 0

## 5. Dynamic semantics

| Construct | Behaviour |
|---|---|
| Declaration | Allocates the variable and sets it to its default value: `0` for `int`, `false` for `bool`. |
| Assignment `x = e;` | Evaluates `e`, then stores the result in `x`. |
| Arithmetic | Integers are unbounded (no overflow). `/` and `%` truncate toward zero, as in C (`-7 / 2 = -3`, `-7 % 2 = -1`). Division or modulo by zero is a run-time error. |
| Evaluation order | Left operand first, then right. |
| `&&`, `\|\|` | Short-circuit. The right operand is evaluated only when the left one does not decide the result, so `d != 0 && n / d > 1` is safe. |
| `if`/`else` | Executes exactly one branch, chosen by the condition. |
| `while` | Tests the condition before every iteration. |
| `print(e)` | Writes the value of `e` on its own line. Booleans print as `true` or `false`. |

The interpreter stops after a configurable number of steps (1,000,000 by default) and reports a probable infinite loop.

## 6. Target: Three-Address Code

Each instruction has at most one operator and three addresses. The full instruction table is in `README.md §5`.

The translation from AST to TAC follows these rules:

| AST | TAC |
|---|---|
| `T x;` | `x := 0` or `x := false` |
| `x = e;` | code(e) → *p*; `x := p` |
| `e1 op e2` | code(e1) → *a*; code(e2) → *b*; `tN := a op b` |
| `e1 && e2` | `tN := a`; `ifFalse tN goto Lend`; `tN := b`; `Lend:` |
| `e1 \|\| e2` | `tN := a`; `if tN goto Lend`; `tN := b`; `Lend:` |
| `if (c) S1 else S2` | `if c goto Lthen`; S2; `goto Lend`; `Lthen:` S1; `Lend:` |
| `if (c) S1` | `ifFalse c goto Lend`; S1; `Lend:` |
| `while (c) S` | `Lstart:`; `ifFalse c goto Lend`; S; `goto Lstart`; `Lend:` |
| `print(e)` | `print p` |

When the condition `c` is a comparison, it is placed directly in the jump (`if x < y goto L1`) instead of first being stored in a temporary. Shadowed variables get distinct storage names (`x`, `x_1`, …). Names of the form `t<N>` are reserved for temporaries, so a user variable called `t1` is stored as `t1_1`.

## 7. Limits and non-goals

The language has no functions, arrays, strings, floats, input, declaration initializers or `for` loop. The compiler does not optimize (no SSA, register allocation or constant folding).

Each of these is a contained change because the phases are separated. For example, a `for` loop needs:

- one grammar rule
- one parser method
- one semantic visitor
- one code-generation rule, which can reuse the `while` scheme

## 8. Rubric mapping (ABET SO1)

- **Identify:** this specification fixes the scope, including what the language deliberately leaves out (§7).
- **Formulate:** the scanner applies regular languages (§2), the grammar is a verified LL(1) context-free grammar (§3), and the type system is given as formal inference rules (§4).
- **Evaluate:** each rule here is exercised by at least one test in `tests/`.
