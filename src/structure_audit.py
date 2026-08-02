"""Static structural audit for cleanup candidates; it does not mutate code."""

from __future__ import annotations

import ast
from pathlib import Path


def audit_python_tree(root: Path) -> dict[str, object]:
    """Report broad exception handlers, TODOs and module syntax failures."""
    broad_handlers: list[str] = []
    todo_files: list[str] = []
    syntax_errors: list[str] = []
    modules = 0
    for path in sorted(root.rglob("*.py")):
        modules += 1
        relative = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        if "TODO" in text or "FIXME" in text:
            todo_files.append(relative)
        try:
            tree = ast.parse(text)
        except SyntaxError as error:
            syntax_errors.append(f"{relative}: {error}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                broad_handlers.append(relative)
    return {
        "modules": modules,
        "broad_exception_handlers": len(broad_handlers),
        "broad_exception_files": sorted(set(broad_handlers)),
        "todo_files": sorted(todo_files),
        "syntax_errors": syntax_errors,
        "passed": not syntax_errors,
        "production_weights_changed": False,
        "verdict_mutated": False,
    }
