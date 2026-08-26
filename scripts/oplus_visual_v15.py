#!/usr/bin/env python3
"""V15: dark-mode popup refinement and floating-outline cleanup.

Real-device V14 feedback shows two remaining visual issues:

1. Root-blur reuse is stable and cheap, but the popup's high-density tint is
   still too translucent in dark mode. The underlying keycap/glyph remains
   legible through the popup. V15 makes the bubble paint explicitly theme-aware:
   a dense #2C2C2E material in night mode and white material in day mode. This
   still reuses the single IME root blur and never registers a popup blur region.

2. The floating keyboard can show a 1dp conventional GradientDrawable outline
   whose circular corner does not visually match the ColorOS smooth corner used
   by the blur carrier. That creates a double-geometry effect: a smoother/rounder
   blurred rectangle inside a less-round outer wireframe. V15 disables only that
   decorative highlight View. The ColorOS blur carrier remains unchanged and
   keeps the verified 14dp floating material geometry. This also removes one
   unnecessary overdraw layer.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v14 as base
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v14.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v14", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V14 pass: {_P}")
    base = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(base)

LOCAL_RELATIVE_PATH = base.LOCAL_RELATIVE_PATH
LOCAL_DESCRIPTOR = base.LOCAL_DESCRIPTOR

LIGHT_BUBBLE_COLOR = 0xFFFFFFFF
DARK_BUBBLE_COLOR = 0xFF2C2C2E
LIGHT_BUBBLE_ALPHA = 0xE8
DARK_BUBBLE_ALPHA = 0xF4

_BUBBLE_FILL_METHOD = f'''.method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V
    .locals 2
    if-eqz p1, :return

    invoke-static {{p0}}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->isNight(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :light

    const v1, 0x{DARK_BUBBLE_COLOR:08x}
    invoke-virtual {{p1, v1}}, Landroid/graphics/Paint;->setColor(I)V
    const/16 v1, 0x{DARK_BUBBLE_ALPHA:02x}
    invoke-virtual {{p1, v1}}, Landroid/graphics/Paint;->setAlpha(I)V
    goto :return

    :light
    const v1, 0x{LIGHT_BUBBLE_COLOR:08x}
    invoke-virtual {{p1, v1}}, Landroid/graphics/Paint;->setColor(I)V
    const/16 v1, 0x{LIGHT_BUBBLE_ALPHA:02x}
    invoke-virtual {{p1, v1}}, Landroid/graphics/Paint;->setAlpha(I)V

    :return
    return-void
.end method'''

_HIGHLIGHT_BACKGROUND_CALL = (
    "    invoke-virtual {v10, v6}, Landroid/view/View;->setBackground"
    "(Landroid/graphics/drawable/Drawable;)V\n"
)
_HIGHLIGHT_DISABLE = _HIGHLIGHT_BACKGROUND_CALL + (
    "    # V15: disable the conventional circular-radius wireframe. The blur\n"
    "    # carrier below remains the sole visible floating-panel geometry.\n"
    "    const/4 v7, 0x4\n"
    "    invoke-virtual {v10, v7}, Landroid/view/View;->setVisibility(I)V\n"
)


def _find_helper(decompile_dir: Path) -> Path:
    root = Path(decompile_dir)
    for smali_root in sorted(root.glob("smali*")):
        candidate = smali_root / LOCAL_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    raise RuntimeError("V15 could not locate generated V13 local helper")


def _replace_method(text: str, method_header: str, replacement: str) -> str:
    start = text.find(method_header)
    if start < 0:
        raise RuntimeError(f"Could not locate method: {method_header}")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError(f"Unterminated method: {method_header}")
    end += len(".end method")
    return text[:start] + replacement + text[end:]


def _rewrite_v15_material(decompile_dir: Path) -> dict[str, object]:
    path = _find_helper(decompile_dir)
    text = path.read_text(encoding="utf-8")

    text = _replace_method(
        text,
        ".method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V",
        _BUBBLE_FILL_METHOD,
    )

    count = text.count(_HIGHLIGHT_BACKGROUND_CALL)
    if count != 1:
        raise RuntimeError(
            f"V15 expected exactly one floating-highlight background install, found {count}"
        )
    text = text.replace(_HIGHLIGHT_BACKGROUND_CALL, _HIGHLIGHT_DISABLE, 1)

    path.write_text(text, encoding="utf-8")
    return {
        "helper": str(path.relative_to(decompile_dir)),
        "bubble": {
            "day_color": f"#{LIGHT_BUBBLE_COLOR:08X}",
            "night_color": f"#{DARK_BUBBLE_COLOR:08X}",
            "day_alpha": LIGHT_BUBBLE_ALPHA,
            "night_alpha": DARK_BUBBLE_ALPHA,
            "local_blur_owner": False,
            "blur_source": "existing IME root FAST_KAWASE material",
        },
        "floating": {
            "decorative_highlight_visible": False,
            "blur_carrier_preserved": True,
            "corner_geometry": "single ColorOS carrier geometry; no competing GradientDrawable wireframe",
        },
    }


def _method_slice(text: str, header: str) -> str:
    start = text.find(header)
    if start < 0:
        raise RuntimeError(f"missing {header}")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError(f"unterminated {header}")
    return text[start : end + len(".end method")]


def _audit_v15(decompile_dir: Path) -> dict[str, object]:
    text = _find_helper(decompile_dir).read_text(encoding="utf-8")
    bubble = _method_slice(
        text,
        ".method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V",
    )
    install_bubble = _method_slice(
        text, ".method public static installBubble(Landroid/view/View;)V"
    )
    floating = _method_slice(
        text, ".method public static installFloating(Landroid/view/View;)V"
    )

    for token in (
        f"const v1, 0x{DARK_BUBBLE_COLOR:08x}",
        f"const/16 v1, 0x{DARK_BUBBLE_ALPHA:02x}",
        f"const v1, 0x{LIGHT_BUBBLE_COLOR:08x}",
        f"const/16 v1, 0x{LIGHT_BUBBLE_ALPHA:02x}",
        "->isNight(Landroid/view/View;)Z",
    ):
        if token not in bubble:
            raise RuntimeError(f"V15 bubble theme refinement missing: {token}")

    # V14 invariant must remain true: popup show/hide never mutates compositor
    # blur state and therefore cannot cause the V13 root-material jump.
    forbidden_bubble = (
        "ViewRootManager",
        "getBackgroundBlurDrawable",
        "createLocalBlur",
        "setBlurRadius",
        "setColor(I)V",
    )
    present = [item for item in forbidden_bubble if item in install_bubble]
    if present:
        raise RuntimeError(
            "V15 bubble reintroduced a local/compositor blur owner: " + ", ".join(present)
        )

    highlight_tag = floating.find('const-string v11, "WeTypeBlurHighlight_Float"')
    highlight_hidden = floating.find(
        "invoke-virtual {v10, v7}, Landroid/view/View;->setVisibility(I)V"
    )
    carrier = floating.find('const-string v5, "WeTypeBlurCarrier_Float"')
    create_blur = floating.find("->createLocalBlur(Landroid/view/View;IFFFF)")
    if min(highlight_tag, highlight_hidden, carrier, create_blur) < 0:
        raise RuntimeError("V15 floating geometry audit missing expected markers")
    if highlight_hidden < highlight_tag:
        raise RuntimeError("V15 highlight disable is not attached to the highlight view")

    return {
        "bubble_dark_mode_explicit_color": True,
        "bubble_dark_alpha": DARK_BUBBLE_ALPHA,
        "bubble_light_alpha": LIGHT_BUBBLE_ALPHA,
        "bubble_new_blur_regions": 0,
        "floating_highlight_drawn": False,
        "floating_coloros_carrier_preserved": True,
        "floating_extra_outline_overdraw": False,
        "global_layout_scan_added": False,
    }


def apply_coloros_v2_visual_profile_v15(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    result_v14 = base.apply_coloros_v2_visual_profile_v14(decompile_dir, patch_report)
    rewrite = _rewrite_v15_material(decompile_dir)
    audit = _audit_v15(decompile_dir)
    return {
        "strategy": (
            "V14 single-owner bubble blur reuse + explicit dark/light popup material + "
            "single visible ColorOS floating-corner geometry"
        ),
        "base_v14": result_v14,
        "visual_refinement": rewrite,
        "runtime_audit": audit,
        "performance_contract": {
            "docked_root_blur_owners": 1,
            "bubble_new_blur_regions": 0,
            "bubble_viewroot_manager_calls": 0,
            "floating_blur_carrier": 1,
            "floating_highlight_draw_calls": 0,
            "extra_frame_overdraw_removed": True,
        },
    }
