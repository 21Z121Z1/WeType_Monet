#!/usr/bin/env python3
"""Directive-tolerant ColorOS V2 visual pass.

Apktool may keep .line/.local directives between an invoke and its move-result.
The first V5 regex intentionally required adjacency and therefore missed
WeType's real bundled-font loaders. This wrapper installs a bytecode-safe,
directive-tolerant font rewriter into the V5 module before running the full
SystemUI G2/V2 corner + system-font transform.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

try:
    import oplus_visual_v5 as base
except ModuleNotFoundError:
    # Unit tests load this file directly with importlib rather than executing it
    # from scripts/. Resolve the sibling module explicitly so the transform is
    # importable in both environments.
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v5.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v5", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling visual pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)

_CUSTOM_FONT_MARKERS = (
    "Landroid/graphics/Typeface;->createFromAsset(",
    "Landroid/graphics/Typeface;->createFromFile(",
    "Lcom/tencent/wetype/plugin/hld/utils/WxImeUtil;->t0(Ljava/lang/String;)",
)
_MOVE_RESULT = re.compile(r"^(?P<indent>\s*)move-result-object\s+(?P<dest>[vp]\d+)\s*$")


def _is_non_code_directive_or_comment(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith(".")
        or stripped.startswith("#")
        or stripped.startswith(":")
    )


def patch_font_factories_directive_tolerant(content: str) -> tuple[str, int]:
    """Replace bundled/custom typeface loaders with Typeface.DEFAULT.

    Dalvik requires move-result to follow the invoke in instruction order, but
    smali debug directives may be printed between the two. We preserve those
    directives, replace the invoke with an sget-object into the destination
    register, and remove only the now-invalid move-result instruction.
    """

    lines = content.splitlines(keepends=True)
    count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if "invoke-static" not in line or not any(
            marker in line for marker in _CUSTOM_FONT_MARKERS
        ):
            i += 1
            continue

        found = None
        # A small bounded window is enough for apktool debug directives and
        # avoids crossing into an unrelated instruction sequence.
        for j in range(i + 1, min(i + 10, len(lines))):
            candidate = lines[j].rstrip("\r\n")
            match = _MOVE_RESULT.match(candidate)
            if match:
                found = (j, match)
                break
            if not _is_non_code_directive_or_comment(candidate):
                break

        if found is None:
            i += 1
            continue

        j, match = found
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        indent_match = re.match(r"^\s*", line)
        indent = indent_match.group(0) if indent_match else ""
        lines[i] = (
            f"{indent}sget-object {match.group('dest')}, "
            "Landroid/graphics/Typeface;->DEFAULT:Landroid/graphics/Typeface;"
            f"{newline}"
        )
        lines[j] = ""
        count += 1
        i = j + 1

    return "".join(lines), count


def apply_coloros_v2_visual_profile(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    # base.patch_keyboard_smali resolves this global at runtime, so replacing it
    # here keeps one source of truth for the G2 helper injection/tree adapter.
    original = base._patch_font_factories
    base._patch_font_factories = patch_font_factories_directive_tolerant
    try:
        result = base.apply_coloros_v2_visual_profile(decompile_dir, patch_report)
    finally:
        base._patch_font_factories = original

    result["font_patch_engine"] = (
        "directive-tolerant bundled/custom loader replacement"
    )
    return result
