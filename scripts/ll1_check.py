"""Computes FIRST, FOLLOW and the predictive parse table of a grammar and checks LL(1).

Usage:  python scripts/ll1_check.py docs/grammar.txt [--table]

Grammar format: one production per line   A → α | β | ε
(-> is also accepted). Lines starting with # are comments.
"""
from __future__ import annotations

import re
import sys

EPS = "ε"
END = "$"


def load(path: str):
    rules: dict[str, list[list[str]]] = {}
    order = []
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        head, body = re.split(r"\s*(?:→|->)\s*", line, maxsplit=1)
        alts = [a.split() for a in re.split(r"\s\|\s", " " + body + " ")]
        alts = [[] if a == [EPS] else a for a in alts]
        if head not in rules:
            order.append(head)
        rules.setdefault(head, []).extend(alts)
    return rules, order


def first_of_seq(seq, first, nonterminals):
    result = set()
    for sym in seq:
        f = first[sym] if sym in nonterminals else {sym}
        result |= f - {EPS}
        if EPS not in f:
            return result
    result.add(EPS)
    return result


def compute(rules, order):
    nts = set(rules)
    first = {a: set() for a in nts}
    changed = True
    while changed:
        changed = False
        for a, alts in rules.items():
            for alt in alts:
                f = first_of_seq(alt, first, nts)
                if not f <= first[a]:
                    first[a] |= f
                    changed = True

    follow = {a: set() for a in nts}
    follow[order[0]].add(END)
    changed = True
    while changed:
        changed = False
        for a, alts in rules.items():
            for alt in alts:
                for i, sym in enumerate(alt):
                    if sym not in nts:
                        continue
                    rest = first_of_seq(alt[i + 1:], first, nts)
                    new = (rest - {EPS}) | (follow[a] if EPS in rest else set())
                    if not new <= follow[sym]:
                        follow[sym] |= new
                        changed = True

    table, conflicts = {}, []
    for a in order:
        for alt in rules[a]:
            f = first_of_seq(alt, first, nts)
            predict = (f - {EPS}) | (follow[a] if EPS in f else set())
            for t in predict:
                if (a, t) in table:
                    conflicts.append((a, t, table[(a, t)], alt))
                else:
                    table[(a, t)] = alt
    return first, follow, table, conflicts


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rules, order = load(sys.argv[1])
    first, follow, table, conflicts = compute(rules, order)
    fmt = lambda s: "{ " + ", ".join(sorted(s)) + " }"
    width = max(map(len, order))

    print("FIRST")
    for a in order:
        print(f"  {a:<{width}}  {fmt(first[a])}")
    print("\nFOLLOW")
    for a in order:
        print(f"  {a:<{width}}  {fmt(follow[a])}")

    if "--table" in sys.argv:
        print("\nPREDICTIVE TABLE  M[A, a] = production")
        for (a, t), alt in sorted(table.items(), key=lambda x: (order.index(x[0][0]), x[0][1])):
            print(f"  M[{a}, {t}] = {a} → {' '.join(alt) or EPS}")

    print()
    if conflicts:
        print(f"The grammar is NOT LL(1): {len(conflicts)} conflicts")
        for a, t, p1, p2 in conflicts:
            print(f"  M[{a}, {t}]: {' '.join(p1) or EPS}  vs  {' '.join(p2) or EPS}")
        return 1
    print(f"The grammar IS LL(1): {len(order)} non-terminals, "
          f"{sum(len(v) for v in rules.values())} productions, no conflicts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
