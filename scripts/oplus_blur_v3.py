#!/usr/bin/env python3
"""Convert WeType's Monet-painted IME surfaces into ColorOS glass tints.

The ColorOS compositor blur belongs at the IME window/root level. Child views
(keys, candidate/tool containers, emoji/symbol tabs, clipboard cards, etc.)
should normally be translucent material tints over that already-blurred
backdrop, not independent BackgroundBlurDrawables. This avoids double blur,
extra compositor cost, and inconsistent sampling between child layers.

Only *surface/background* colors are changed here. Foreground/text/icon colors
remain on-surface colors for contrast and accessibility.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

# The root BackgroundBlurDrawable owns these regions, so keep them fully clear.
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

# Neutral translucent surfaces above the root blur. Values are intentionally
# neutral so Monet accent hues cannot turn the glass blue/green/purple.
CONTAINER_KEYS = {
    "ime_skin_color_18",
    "ime_skin_dark_color_18",
    "ime_skin_clipboard_item_bg_color",
    "ime_skin_dark_clipboard_item_bg_color",
    "ime_skin_color_16",
    "ime_skin_dark_color_16",
    "ime_skin_color_10",                 # emoji/symbol tab-bar background
    "ime_skin_dark_color_10",
    "ime_skin_alternative_keyboard_bg_color",
    "ime_skin_dark_alternative_keyboard_bg_color",
    "ime_skin_color_15",
    "ime_skin_dark_color_15",
    "ime_skin_BW_97",
    "ime_skin_dark_BW_97",
}

# Ordinary key/button surfaces.
KEY_KEYS = {
    "ime_skin_color_12",
    "ime_skin_dark_color_12",
    "ime_skin_color_btn_white_bg",
    "ime_skin_dark_color_btn_white_bg",
}

# Function/selected/semantic controls. These stay visually separated from
# ordinary keys but no longer carry Monet secondary-container hues.
FUNCTION_KEYS = {
    "ime_skin_S5_type_selected_color",   # emoji/symbol selected tab
    "ime_skin_dark_S5_type_selected_color",
    "ime_skin_color_13",
    "ime_skin_dark_color_13",
    "ime_skin_color_btn_green_bg",
    "ime_skin_dark_color_btn_green_bg",
    "ime_skin_color_14",
    "ime_skin_dark_color_14",
    "ime_skin_color_14_Alpha_20",
    "ime_skin_dark_color_14_Alpha_20",
    "ime_skin_color_17",
    "ime_skin_dark_color_17",
}

# Already-transparent structural surfaces. Keep them transparent explicitly so
# later Monet/resource passes cannot repaint them.
STRUCTURAL_CLEAR_KEYS = {
    "ime_skin_candidate_type_container_bg_color_fixed",
    "ime_skin_dark_candidate_type_container_bg_color_fixed",
    "ime_skin_toolbar_select_bg_color",
    "ime_skin_dark_toolbar_select_bg_color",
}

# ARGB. The root already carries ColorOS material tint through
# OplusBlurParam.setMaterialParams(); these are deliberately lower-alpha child
# layers. Dark mode uses white veils to lift controls above the dark material;
# light mode uses white veils with higher alpha, matching the visual hierarchy
# of ColorOS's glass keyboard without re-introducing dynamic accent color.
PALETTE = {
    "clear": {"light": "#00000000", "dark": "#00000000"},
    "container": {"light": "#38FFFFFF", "dark": "#18FFFFFF"},
    "key": {"light": "#8CFFFFFF", "dark": "#2EFFFFFF"},
    "function": {"light": "#66FFFFFF", "dark": "#42FFFFFF"},
}


def _mode_for_key(key: str) -> str:
    return "dark" if key.startswith("ime_skin_dark_") else "light"


def _role_for_key(key: str) -> str | None:
    if key in ROOT_CLEAR_KEYS or key in STRUCTURAL_CLEAR_KEYS:
        return "clear"
    if key in CONTAINER_KEYS:
        return "container"
    if key in KEY_KEYS:
        return "key"
    if key in FUNCTION_KEYS:
        return "function"
    return None


def _resolved_surface_map(config_file: Path) -> dict[str, tuple[str, str, str]]:
    """Return obfuscated resource name -> (semantic key, role, ARGB)."""
    config = json.loads(Path(config_file).read_text(encoding="utf-8"))
    resolved: dict[str, tuple[str, str, str]] = {}
    missing_semantic: list[str] = []

    indexed = {
        item.get("unobfuscated_key"): item.get("obfuscated_key")
        for item in config.get("theme_colors", [])
        if item.get("unobfuscated_key")
    }

    expected = ROOT_CLEAR_KEYS | STRUCTURAL_CLEAR_KEYS | CONTAINER_KEYS | KEY_KEYS | FUNCTION_KEYS
    for semantic in sorted(expected):
        obfuscated = indexed.get(semantic)
        # Some WeType versions genuinely lack a surface; tolerate version drift
        # but report it so the CI artifact tells us exactly what was present.
        if not obfuscated:
            missing_semantic.append(semantic)
            continue
        role = _role_for_key(semantic)
        assert role is not None
        mode = _mode_for_key(semantic)
        resolved[obfuscated] = (semantic, role, PALETTE[role][mode])

    return resolved


def apply_glass_surface_palette(decompile_dir: Path, config_file: Path) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    config_file = Path(config_file)
    targets = _resolved_surface_map(config_file)
    if not targets:
        raise RuntimeError("No WeType glass-surface resources resolved")

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
                is_color = tag == "color" or (tag == "item" and element.get("type") == "color")
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
            "Resolved glass-surface resources were not found in decoded APK: "
            + ", ".join(unresolved_resources)
        )

    role_counts: dict[str, int] = {}
    for item in changed.values():
        role_counts[item["role"]] = role_counts.get(item["role"], 0) + 1

    return {
        "strategy": "single root compositor blur + translucent child material tints",
        "secondary_child_blur": False,
        "reason": (
            "emoji/symbol UI is a child layer in the same IME window; transparent/tinted child "
            "surfaces reveal the existing root BackgroundBlurDrawable without double-blurring"
        ),
        "palette": PALETTE,
        "role_counts": role_counts,
        "changed_resources": changed,
        "resource_files": sorted(files),
    }
