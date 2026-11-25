"""Pretty-prints an AST as an indented tree (├── / └──)."""
from __future__ import annotations

HIDDEN = {"node", "line", "column", "type", "storage", "target_type"}
LEAVES = {"IntegerLiteral", "BooleanLiteral", "Identifier"}


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f'"{value}"' if isinstance(value, str) else str(value)


def _label(node: dict, show_types: bool) -> str:
    kind = node["node"]
    if kind in ("IntegerLiteral", "BooleanLiteral"):
        text = f"{kind}({_fmt(node['value'])})"
    elif kind == "Identifier":
        text = f"Identifier({node['name']})"
    else:
        text = kind
    if show_types and node.get("type"):
        text += f" : {node['type']}"
    return text


def _children(node: dict):
    if node["node"] in LEAVES:
        return []
    items = []
    for key, value in node.items():
        if key in HIDDEN or value is None:
            continue
        if isinstance(value, list):
            items.extend((None, child) for child in value)
        else:
            items.append((key, value))
    return items


def _render(node: dict, prefix: str, out: list[str], show_types: bool) -> None:
    items = _children(node)
    for i, (key, value) in enumerate(items):
        last = i == len(items) - 1
        branch, extension = ("└── ", "    ") if last else ("├── ", "│   ")
        label = f"{key}: " if key else ""
        if isinstance(value, dict):
            out.append(prefix + branch + label + _label(value, show_types))
            _render(value, prefix + extension, out, show_types)
        else:
            out.append(prefix + branch + label + _fmt(value))


def render_ast(ast: dict, show_types: bool = False) -> str:
    out = [_label(ast, show_types)]
    _render(ast, "", out, show_types)
    return "\n".join(out)
