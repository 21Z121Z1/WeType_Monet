#!/usr/bin/env python3
"""Apply a Breeno/ColorOS-derived glass appearance profile to WeType.

This is intentionally an *appearance* pass, not another blur engine.

Evidence from com.oplus.keyboard 15.17.238 shows that ColorOS separates the
keyboard into several visual roles instead of painting every surface with one
Monet container color. The APK exposes, among others:

- bgKeyboardBlur
- bgKeyNormalBlur / bgKeyPressedBlur
- bgSymbolBlur
- bgToolboxItemNormalBlur
- bgTipsContainerBlur
- ImeContainerBlurDelegate
- applyBlurEffectToAllButtons / applyBlurEffectToButton
- keyRadius / keyShadowRadius
- COUIMaterialBlurEffect / COUIMaterialThemeBlurEffect

WeType does not expose those same view-level blur delegates, so this pass
reconstructs the same hierarchy with the resources that *are* stable in the
WeType skin contract: clear root regions, low-alpha panels, elevated cards,
neutral key/function/selected surfaces, and subtle glass edges.

The actual root blur remains the private ColorOS FAST_KAWASE material installed
by oplus_blur_v2. We deliberately do not guess at per-key View targets here:
doing so with geometry/class-name heuristics would be fragile and can attach
blur to text/icon children. A later pass can add true per-key BackgroundBlur
only after stable WeType key-view call sites are mapped.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


# Root-level surfaces must not repaint the compositor blur.
ROOT_CLEAR_KEYS = {
    "ime_skin_candidate_start_color",
    "ime_skin_candidate_end_color",
    "ime_skin_keyboard_end_color",
    "ime_skin_keyboard_background",
    "ime_skin_dark_candidate_start_color",
    "ime_skin_dark_candidate_end_color",
    "ime_skin_dark_keyboard_end_color",
    "ime_skin_dark_keyboard_background",
}

# Flat chrome over the root blur: emoji/symbol navigation and alternate panels.
PANEL_KEYS = {
    "ime_skin_color_10",
    "ime_skin_dark_color_10",
    "ime_skin_alternative_keyboard_bg_color",
    "ime_skin_dark_alternative_keyboard_bg_color",
}

# Raised surfaces: clipboard/menu/toolbox-like cards and auxiliary panels.
ELEVATED_KEYS = {
    "ime_skin_color_18",
    "ime_skin_dark_color_18",
    "ime_skin_clipboard_item_bg_color",
    "ime_skin_dark_clipboard_item_bg_color",
    "ime_skin_color_16",
    "ime_skin_dark_color_16",
    "ime_skin_color_15",
    "ime_skin_dark_color_15",
    "ime_skin_BW_97",
    "ime_skin_dark_BW_97",
}

# Ordinary alphanumeric keys and the shared first-candidate/popup surface.
KEY_KEYS = {
    "ime_skin_color_12",
    "ime_skin_dark_color_12",
    "ime_skin_color_btn_white_bg",
    "ime_skin_dark_color_btn_white_bg",
}

# Function/special keys. On light material these are darkened slightly instead
# of being painted with Monet secondary-container hues; on dark material they
# are lifted with a neutral white veil.
FUNCTION_KEYS = {
    "ime_skin_color_13",
    "ime_skin_dark_color_13",
    "ime_skin_color_btn_green_bg",
    "ime_skin_dark_color_btn_green_bg",
}

# Explicit selected/pressed-like surfaces that are safe to recolor as a
# background. Keep this separate from generic function keys so selection still
# reads clearly after accent hue is removed.
SELECTED_KEYS = {
    "ime_skin_S5_type_selected_color",
    "ime_skin_dark_S5_type_selected_color",
    "ime_skin_color_14_Alpha_20",
    "ime_skin_dark_color_14_Alpha_20",
    "ime_skin_color_17",
    "ime_skin_dark_color_17",
}

# Structurally transparent regions and dividers stay clear.
STRUCTURAL_CLEAR_KEYS = {
    "ime_skin_candidate_type_container_bg_color_fixed",
    "ime_skin_dark_candidate_type_container_bg_color_fixed",
    "ime_skin_toolbar_select_bg_color",
    "ime_skin_dark_toolbar_select_bg_color",
    "ime_skin_color_divider",
    "ime_skin_dark_color_divider",
    "ime_skin_color_09",
    "ime_skin_dark_color_09",
}

# Breeno's APK has explicit key radius/shadow machinery. The WeType theme
# exposes border/shadow tokens, but the original Monet fork zeroed them out.
# Keep a restrained neutral edge contrast, but DO NOT restore WeType's shadow
# resources. On the real 3.5.3 key renderer those tokens are drawn as a hard
# bottom slab rather than ColorOS-style elevation, producing the visible dark
# rectangle under every key (V4 regression confirmed on device).
KEY_EDGE_KEYS = {
    "ime_skin_key_white_border_color",
    "ime_skin_dark_key_white_border_color",
    "ime_skin_color_btn_white_border",
    "ime_skin_dark_color_btn_white_border",
}

CONTROL_EDGE_KEYS = {
    "ime_skin_key_grey_border_color",
    "ime_skin_dark_key_grey_border_color",
    "ime_skin_key_green_border_color",
    "ime_skin_dark_key_green_border_color",
    "ime_skin_color_btn_grey_border",
    "ime_skin_dark_color_btn_grey_border",
    "ime_skin_color_btn_green_border",
    "ime_skin_dark_color_btn_green_border",
    "ime_skin_color_00_Alpha_25",
    "ime_skin_dark_color_00_Alpha_25",
}

SHADOW_KEYS = {
    "UN_BW_0_Alpha_0_5",
    "ime_skin_color_00_Alpha_15",
    "ime_skin_dark_color_00_Alpha_15",
    "ime_skin_key_white_shadow_color",
    "ime_skin_dark_key_white_shadow_color",
    "ime_skin_key_grey_shadow_color",
    "ime_skin_dark_key_grey_shadow_color",
    "ime_skin_key_green_shadow_color",
    "ime_skin_dark_key_green_shadow_color",
    "ime_skin_color_btn_white_shadow",
    "ime_skin_dark_color_btn_white_shadow",
    "ime_skin_color_btn_grey_shadow",
    "ime_skin_dark_color_btn_grey_shadow",
    "ime_skin_color_btn_green_shadow",
    "ime_skin_dark_color_btn_green_shadow",
}

# These two resources are semantically overloaded by WeType: selected text in
# the segmentation UI *and* a special-key background. V3 treated them as a
# background globally, which can reduce foreground contrast. Do not recolor
# them until call sites are split.
MIXED_ROLE_EXCLUSIONS = {
    "ime_skin_color_14",
    "ime_skin_dark_color_14",
}

REFERENCE_EVIDENCE = (
    "bgKeyboardBlur",
    "bgKeyNormalBlur",
    "bgKeyPressedBlur",
    "bgSymbolBlur",
    "bgToolboxItemNormalBlur",
    "bgTipsContainerBlur",
    "ImeContainerBlurDelegate",
    "applyBlurEffectToAllButtons",
    "applyBlurEffectToButton",
    "keyRadius",
    "keyShadowRadius",
    "COUIMaterialBlurEffect",
    "COUIMaterialThemeBlurEffect",
)

# ARGB role palette. These values are deliberately neutral and hierarchical.
# They are not claimed to be byte-for-byte ColorOS resource values: the
# original keyboard resolves its own theme resources at runtime. The important
# parity target here is role separation and depth ordering.
PALETTE = {
    "clear": {"light": "#00000000", "dark": "#00000000"},
    "panel": {"light": "#24FFFFFF", "dark": "#14FFFFFF"},
    "elevated": {"light": "#46FFFFFF", "dark": "#24FFFFFF"},
    "key": {"light": "#72FFFFFF", "dark": "#30FFFFFF"},
    "function": {"light": "#18000000", "dark": "#32FFFFFF"},
    "selected": {"light": "#58FFFFFF", "dark": "#48FFFFFF"},
    "key_edge": {"light": "#5CFFFFFF", "dark": "#34FFFFFF"},
    "control_edge": {"light": "#1F000000", "dark": "#38FFFFFF"},
    # WeType's shadow tokens are geometry-bearing bottom strips, not a soft
    # elevation shadow. Keeping them transparent restores the pre-V4 geometry.
    "shadow": {"light": "#00000000", "dark": "#00000000"},
}


def _mode_for_key(key: str) -> str:
    return "dark" if key.startswith("ime_skin_dark_") else "light"


def _role_for_key(key: str) -> str | None:
    if key in ROOT_CLEAR_KEYS or key in STRUCTURAL_CLEAR_KEYS:
        return "clear"
    if key in PANEL_KEYS:
        return "panel"
    if key in ELEVATED_KEYS:
        return "elevated"
    if key in KEY_KEYS:
        return "key"
    if key in FUNCTION_KEYS:
        return "function"
    if key in SELECTED_KEYS:
        return "selected"
    if key in KEY_EDGE_KEYS:
        return "key_edge"
    if key in CONTROL_EDGE_KEYS:
        return "control_edge"
    if key in SHADOW_KEYS:
        return "shadow"
    return None


def _resolved_style_map(
    config_file: Path,
) -> tuple[dict[str, tuple[str, str, str]], list[str]]:
    """Resolve obfuscated resource -> (semantic key, role, ARGB)."""
    config = json.loads(Path(config_file).read_text(encoding="utf-8"))
    indexed = {
        item.get("unobfuscated_key"): item.get("obfuscated_key")
        for item in config.get("theme_colors", [])
        if item.get("unobfuscated_key")
    }

    expected = (
        ROOT_CLEAR_KEYS
        | STRUCTURAL_CLEAR_KEYS
        | PANEL_KEYS
        | ELEVATED_KEYS
        | KEY_KEYS
        | FUNCTION_KEYS
        | SELECTED_KEYS
        | KEY_EDGE_KEYS
        | CONTROL_EDGE_KEYS
        | SHADOW_KEYS
    )

    resolved: dict[str, tuple[str, str, str]] = {}
    missing: list[str] = []
    for semantic in sorted(expected):
        obfuscated = indexed.get(semantic)
        if not obfuscated:
            missing.append(semantic)
            continue
        role = _role_for_key(semantic)
        assert role is not None
        mode = _mode_for_key(semantic)
        resolved[obfuscated] = (semantic, role, PALETTE[role][mode])

    return resolved, missing


def apply_breeno_appearance_profile(
    decompile_dir: Path, config_file: Path
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    config_file = Path(config_file)
    targets, missing_semantics = _resolved_style_map(config_file)
    if not targets:
        raise RuntimeError("No WeType resources resolved for Breeno appearance profile")

    changed: dict[str, dict[str, str]] = {}
    files: set[str] = set()
    res_dir = decompile_dir / "res"

    for values_dir in sorted(res_dir.glob("values*")):
        if not values_dir.is_dir():
            continue
        for xml_path in sorted(values_dir.rglob("*.xml")):
            if xml_path.name == "public.xml":
                continue
            try:
                tree = ET.parse(xml_path)
            except ET.ParseError as error:
                raise RuntimeError(f"Failed to parse resource XML: {xml_path}") from error

            dirty = False
            for element in tree.getroot():
                tag = element.tag.rsplit("}", 1)[-1]
                is_color = tag == "color" or (
                    tag == "item" and element.get("type") == "color"
                )
                if not is_color:
                    continue

                resource_name = element.get("name")
                if resource_name not in targets:
                    continue

                semantic, role, argb = targets[resource_name]
                old = (element.text or "").strip()
                element.text = argb
                changed[resource_name] = {
                    "semantic": semantic,
                    "role": role,
                    "old": old,
                    "new": argb,
                }
                dirty = True

            if dirty:
                tree.write(xml_path, encoding="utf-8", xml_declaration=True)
                files.add(str(xml_path.relative_to(decompile_dir)))

    unresolved_resources = sorted(set(targets) - set(changed))
    if unresolved_resources:
        raise RuntimeError(
            "Resolved Breeno appearance resources were not found in decoded APK: "
            + ", ".join(unresolved_resources)
        )

    role_counts: dict[str, int] = {}
    for item in changed.values():
        role = item["role"]
        role_counts[role] = role_counts.get(role, 0) + 1

    config = json.loads(config_file.read_text(encoding="utf-8"))
    available_semantics = {
        item.get("unobfuscated_key")
        for item in config.get("theme_colors", [])
        if item.get("unobfuscated_key")
    }
    excluded_present = sorted(MIXED_ROLE_EXCLUSIONS & available_semantics)

    return {
        "strategy": "ColorOS/Breeno-derived layered glass appearance over root FAST_KAWASE blur",
        "root_blur_owner": "oplus_blur_v2 / ViewRootManager BackgroundBlurDrawable",
        "true_child_blur": False,
        "true_child_blur_status": (
            "deferred until stable WeType key/panel View call sites are mapped; "
            "v4 reconstructs Breeno role hierarchy without unsafe view heuristics"
        ),
        "reference_apk_evidence": list(REFERENCE_EVIDENCE),
        "palette": PALETTE,
        "mixed_role_exclusions": excluded_present,
        "missing_semantics": missing_semantics,
        "role_counts": role_counts,
        "changed_resources": changed,
        "resource_files": sorted(files),
    }
