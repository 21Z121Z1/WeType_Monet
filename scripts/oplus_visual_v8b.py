#!/usr/bin/env python3
"""Correct V8 interpretation of WeType Tool v1.3.2 gradient strings.

The first V8 pass treated four strings found together in WeType Tool as resource
names. Real 3.5.3 (56201) build validation proved they are not exported HLD
color resources. Re-reading the module smali shows those four strings are built
into one static List, consistent with a DexKit target signature. By contrast,
`ime_skin_clipboard_item_bg_color` is declared through the module's Color
resource descriptor and *does* resolve to an HLD resource ID.

This wrapper keeps the useful V8 event-driven lifecycle architecture but narrows
resource rewriting to the two clipboard light/dark resources that are actually
proven resource surfaces. The gradient strings remain evidence for locating the
full keyboard/emoji painter classes; V6/V7 already suppress/clear those layers
through their real runtime hierarchy, so inventing non-existent color IDs would
be both brittle and incorrect.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v8 as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v8.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v8", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V8 pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


WETYPE_TOOL_DEXKIT_GRADIENT_SIGNATURES = (
    "ime_emoji_keyboard_gradient_bg_color",
    "ime_keyboard_full_gradient_bg_color",
    "ime_emoji_keyboard_gradient_bg_color_dark",
    "ime_keyboard_full_gradient_bg_color_dark",
)

# These are the actual resource semantics proven by both the WeType Tool module
# and the current WeType HLD R mapping. They are elevated item cards rather than
# a second compositor blur owner.
WETYPE_TOOL_RESOURCE_COLORS = {
    "ime_skin_clipboard_item_bg_color": "#46FFFFFF",
    "ime_skin_dark_clipboard_item_bg_color": "#24FFFFFF",
}


def apply_coloros_v2_visual_profile_v8(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    original = base.WETYPE_TOOL_SURFACE_COLORS
    base.WETYPE_TOOL_SURFACE_COLORS = WETYPE_TOOL_RESOURCE_COLORS
    try:
        result = base.apply_coloros_v2_visual_profile_v8(decompile_dir, patch_report)
    finally:
        base.WETYPE_TOOL_SURFACE_COLORS = original

    evidence = result.get("wetype_tool_evidence")
    if not isinstance(evidence, dict):
        raise RuntimeError("V8 result lost WeType Tool evidence block")
    evidence["dexkit_gradient_signature_strings"] = list(
        WETYPE_TOOL_DEXKIT_GRADIENT_SIGNATURES
    )
    evidence["gradient_signature_interpretation"] = (
        "static DexKit class-location signature, not HLD color resource IDs; "
        "runtime painter/hierarchy handling remains V6/V7"
    )
    evidence["resource_surfaces"] = list(WETYPE_TOOL_RESOURCE_COLORS)

    surfaces = result.get("tool_surfaces")
    if not isinstance(surfaces, dict):
        raise RuntimeError("V8 result lost tool_surfaces block")
    surfaces["policy"] = (
        "Only WeType-Tool-proven clipboard item color resources are rewritten. "
        "The four emoji/full-gradient strings are DexKit signatures and are "
        "handled through the real V6/V7 painter/view hierarchy instead of fake IDs."
    )

    result["resource_resolution_correction"] = {
        "real_build_evidence": (
            "WeType 3.5.3 (56201) generated 101/101 color mappings; the four "
            "gradient strings have no HLD R/public color IDs, while clipboard "
            "light/dark resources resolve successfully"
        ),
        "verified_non_resource_signatures": list(
            WETYPE_TOOL_DEXKIT_GRADIENT_SIGNATURES
        ),
        "verified_resource_semantics": list(WETYPE_TOOL_RESOURCE_COLORS),
    }
    return result
