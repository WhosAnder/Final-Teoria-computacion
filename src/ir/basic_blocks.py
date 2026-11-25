"""Splits TAC into basic blocks and builds the control-flow graph (CFG).

Classic leader algorithm:
  1. the first instruction is a leader;
  2. every labelled instruction (a jump target) is a leader;
  3. every instruction that follows a jump is a leader.
A basic block runs from one leader up to (not including) the next one.
Edges: a block falls through to the next block unless it ends in 'goto';
a conditional jump adds an edge to its target block.
"""
from __future__ import annotations


def _parse(code: list[str]):
    """Return [(labels_before, instruction_text)] ignoring comments/blank lines."""
    items, pending = [], []
    for raw in code:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.endswith(":") and " " not in line:
            pending.append(line[:-1])
            continue
        items.append((pending, line))
        pending = []
    if pending:                       # trailing labels: empty exit instruction
        items.append((pending, None))
    return items


def _jump_target(instr: str | None):
    if instr is None:
        return None, None
    parts = instr.split()
    if parts[0] == "goto":
        return "goto", parts[1]
    if parts[0] in ("if", "ifFalse") and "goto" in parts:
        return "cond", parts[-1]
    return None, None


def build_cfg(code: list[str]) -> list[dict]:
    items = _parse(code)
    leaders = set()
    for i, (labels, instr) in enumerate(items):
        if i == 0 or labels or _jump_target(items[i - 1][1])[0]:
            leaders.add(i)
    starts = sorted(leaders)
    blocks = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(items)
        blocks.append({"id": f"B{n + 1}", "labels": items[start][0],
                       "instructions": [ins for _, ins in items[start:end] if ins],
                       "successors": []})
    label_to_block = {lab: b["id"] for b in blocks for lab in b["labels"]}
    for n, block in enumerate(blocks):
        last = block["instructions"][-1] if block["instructions"] else None
        kind, target = _jump_target(last)
        if kind in ("goto", "cond"):
            block["successors"].append(label_to_block[target])
        if kind != "goto" and n + 1 < len(blocks):
            block["successors"].append(blocks[n + 1]["id"])
    return blocks


def render_cfg(blocks: list[dict]) -> str:
    out = []
    for b in blocks:
        labels = f"  [{', '.join(b['labels'])}]" if b["labels"] else ""
        out.append(f"{b['id']}{labels}")
        out.extend(f"    {ins}" for ins in b["instructions"]) if b["instructions"] \
            else out.append("    (exit)")
        succ = ", ".join(b["successors"]) or "exit"
        out.append(f"    -> {succ}\n")
    return "\n".join(out)
