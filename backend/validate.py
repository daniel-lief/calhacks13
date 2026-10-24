"""
Static checks on generated scene code before it is executed.

This is a guardrail against obviously unsafe or malformed output, not a sandbox:
the scene still runs as ordinary Python in a subprocess on this machine.
"""
from __future__ import annotations

import ast
import re

ALLOWED_IMPORTS = {
    "animai", "manimlib", "numpy", "math", "cmath", "random", "itertools", "functools",
    "operator", "colorsys", "fractions", "collections", "string", "typing", "__future__",
}
BLOCKED_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "input",
    "breakpoint", "help", "exit", "quit", "memoryview", "os", "sys", "subprocess", "shutil",
    "pathlib", "Path", "socket", "importlib", "builtins", "ctypes", "pickle", "requests",
    "urllib", "http", "tempfile", "glob",
}
ALLOWED_DUNDERS = {"__init__", "__name__"}

CODE_BLOCK_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)


def extract_code(reply: str) -> str | None:
    """Return the last fenced Python block in a model reply."""
    blocks = CODE_BLOCK_RE.findall(reply)
    if blocks:
        return blocks[-1].strip() + "\n"
    if "class Explainer" in reply and "from animai import" in reply:
        return reply.strip() + "\n"
    return None


def check_scene(code: str) -> str | None:
    """Return a description of the first problem found, or None if the code passes."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"SyntaxError: {exc.msg} (line {exc.lineno}): {(exc.text or '').strip()}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"Import of '{alias.name}' is not allowed (line {node.lineno})."
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"Import from '{node.module}' is not allowed (line {node.lineno})."
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            return f"Use of '{node.id}' is not allowed (line {node.lineno})."
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr not in ALLOWED_DUNDERS:
                return f"Access to '{node.attr}' is not allowed (line {node.lineno})."

    scene = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Explainer"), None
    )
    if scene is None:
        return "The file must define a class named `Explainer`."
    bases = {b.id for b in scene.bases if isinstance(b, ast.Name)}
    if "AnimaiScene" not in bases:
        return "`Explainer` must subclass `AnimaiScene`."
    if not any(isinstance(n, ast.FunctionDef) and n.name == "construct" for n in scene.body):
        return "`Explainer` must define `construct(self)`."
    if count_voiceovers(code) == 0:
        return "The scene has no `self.voiceover(...)` blocks; all narration must use them."
    return None


def count_voiceovers(code: str) -> int:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    return sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "voiceover"
    )


MAX_TAGS = 15
MAX_TAG_LENGTH = 24


def clean_tags(tags) -> list[str]:
    """Lowercase, trimmed, de-duplicated, length-limited tags."""
    out: list[str] = []
    for tag in tags if isinstance(tags, (list, tuple)) else []:
        if not isinstance(tag, str):
            continue
        tag = " ".join(tag.lower().split()).lstrip("#").strip()[:MAX_TAG_LENGTH].strip()
        if tag and tag not in out:
            out.append(tag)
    return out[:MAX_TAGS]


def extract_tags(code: str) -> list[str]:
    match = re.search(r"^TAGS\s*=\s*(\[.*?\])", code, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    try:
        return clean_tags(ast.literal_eval(match.group(1)))
    except (ValueError, SyntaxError):
        return []


def extract_title(code: str) -> str | None:
    match = re.search(r'^TITLE\s*=\s*(["\'])(.+?)\1', code, re.MULTILINE)
    return match.group(2) if match else None
