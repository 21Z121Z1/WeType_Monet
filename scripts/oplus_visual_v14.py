#!/usr/bin/env python3
"""V14: single-owner bubble material.

Real-device V13 feedback proved the local key-preview blur path works, but also
showed an undesirable jump in the docked keyboard material whenever the popup
appears/disappears. The cause is architectural: V13 registers a second
BackgroundBlurDrawable in the same IME composition tree. ColorOS then has to
re-submit/recompose the overlapping blur-region set.

V14 keeps every V13 hook point and all floating-keyboard behavior, but removes
*only* the key-preview local blur owner. The popup reuses the already-active IME
root FAST_KAWASE material underneath it and becomes a dense translucent
material tint clipped by WeType's own popup Outline/Path. No ViewRootManager,
BackgroundBlurDrawable, OplusBlurParam or compositor-region mutation occurs on
key press/release.

This is intentionally conservative:
- docked root: unchanged single OplusKeyboardBlur owner;
- key preview: tint/outline only, no second blur region;
- floating keyboard: V13 local carrier remains, because it can move outside the
  docked keyboard geometry and has a separate lifetime/topology;
- voice: unchanged V11 stable policy.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v13_final as base
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v13_final.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v13_final", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V13 final pass: {_P}")
    base = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(base)

LOCAL_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;"
LOCAL_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2LocalBlurV13.smali")

# Dense enough to prevent the pressed key glyph/keycap from visibly bleeding
# through the popup, while still letting the existing root blur influence the
# material tone. This is intentionally much denser than V13's 0x5a because V14
# no longer creates a popup-local blur region.
BUBBLE_REUSE_ALPHA = 0xD8


_BUBBLE_FILL_METHOD = f'''.method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V
    .locals 1
    if-eqz p1, :return
    const/16 v0, 0x{BUBBLE_REUSE_ALPHA:02x}
    invoke-virtual {{p1, v0}}, Landroid/graphics/Paint;->setAlpha(I)V
    :return
    return-void
.end method'''

_BUBBLE_INSTALL_METHOD = '''.method public static installBubble(Landroid/view/View;)V
    .locals 3
    if-eqz p0, :return
    :try_start
    # Reuse the already-active IME root blur. Do NOT create/register another
    # BackgroundBlurDrawable here: overlapping blur regions caused the V13
    # root-material jump on popup show/hide.
    const/4 v0, 0x1
    invoke-virtual {p0, v0}, Landroid/view/View;->setClipToOutline(Z)V
    sget-object v1, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->bubbleActive:Ljava/util/WeakHashMap;
    sget-object v2, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;
    invoke-virtual {v1, p0, v2}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    invoke-virtual {p0}, Landroid/view/View;->invalidate()V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    goto :return
    :catch
    move-exception v0
    const-string v1, "WeTypeOplusLocalV14"
    const-string v2, "installBubble root-blur reuse failed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    :return
    return-void
.end method'''


def _find_helper(decompile_dir: Path) -> Path:
    root = Path(decompile_dir)
    for smali_root in sorted(root.glob("smali*")):
        candidate = smali_root / LOCAL_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    raise RuntimeError("V14 could not locate V13 local helper")


def _replace_method(text: str, method_header: str, replacement: str) -> str:
    start = text.find(method_header)
    if start < 0:
        raise RuntimeError(f"Could not locate method: {method_header}")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError(f"Unterminated method: {method_header}")
    end += len(".end method")
    return text[:start] + replacement + text[end:]


def _rewrite_bubble_to_root_blur_reuse(decompile_dir: Path) -> dict[str, object]:
    path = _find_helper(decompile_dir)
    text = path.read_text(encoding="utf-8")
    text = _replace_method(
        text,
        ".method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V",
        _BUBBLE_FILL_METHOD,
    )
    text = _replace_method(
        text,
        ".method public static installBubble(Landroid/view/View;)V",
        _BUBBLE_INSTALL_METHOD,
    )
    path.write_text(text, encoding="utf-8")
    return {
        "helper": str(path.relative_to(decompile_dir)),
        "popup_local_blur_owner": False,
        "popup_blur_source": "existing IME root FAST_KAWASE material",
        "popup_fill_alpha": BUBBLE_REUSE_ALPHA,
        "popup_outline": "preserve WeType floatview.u ViewOutlineProvider/Path",
    }


def _method_slice(text: str, header: str) -> str:
    start = text.find(header)
    if start < 0:
        raise RuntimeError(f"missing {header}")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError(f"unterminated {header}")
    return text[start : end + len(".end method")]


def _audit_v14(decompile_dir: Path) -> dict[str, object]:
    text = _find_helper(decompile_dir).read_text(encoding="utf-8")
    bubble = _method_slice(
        text, ".method public static installBubble(Landroid/view/View;)V"
    )
    fill = _method_slice(
        text,
        ".method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V",
    )
    forbidden = (
        "ViewRootManager",
        "getBackgroundBlurDrawable",
        "createLocalBlur",
        "OplusBlurParam",
        "setBlurRadius",
        "setColor",
        "setBackground(Landroid/graphics/drawable/Drawable;)",
    )
    present = [item for item in forbidden if item in bubble]
    if present:
        raise RuntimeError(
            "V14 bubble still mutates compositor/local blur state: " + ", ".join(present)
        )
    required = (
        "setClipToOutline(Z)V",
        "bubbleActive:Ljava/util/WeakHashMap;",
        "invalidate()V",
    )
    missing = [item for item in required if item not in bubble]
    if missing:
        raise RuntimeError("V14 bubble reuse helper incomplete: " + ", ".join(missing))
    alpha_token = f"const/16 v0, 0x{BUBBLE_REUSE_ALPHA:02x}"
    if alpha_token not in fill:
        raise RuntimeError("V14 popup material alpha not installed")

    # Floating is deliberately retained as the V13 Tool-style carrier path.
    floating = _method_slice(
        text, ".method public static installFloating(Landroid/view/View;)V"
    )
    if "WeTypeBlurCarrier_Float" not in floating or "createLocalBlur" not in floating:
        raise RuntimeError("V14 unexpectedly lost V13 floating carrier behavior")

    return {
        "bubble_local_blur_calls": 0,
        "bubble_compositor_region_mutation": False,
        "bubble_root_blur_reuse": True,
        "bubble_fill_alpha": BUBBLE_REUSE_ALPHA,
        "floating_v13_carrier_preserved": True,
        "global_layout_scan_added": False,
        "per_key_viewroot_blur": False,
    }


def apply_coloros_v2_visual_profile_v14(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    result_v13 = base.apply_coloros_v2_visual_profile_v13(decompile_dir, patch_report)
    rewrite = _rewrite_bubble_to_root_blur_reuse(decompile_dir)
    audit = _audit_v14(decompile_dir)
    return {
        "strategy": (
            "single-owner docked material: reuse existing IME root blur for key preview; "
            "no popup-local BackgroundBlurDrawable"
        ),
        "base_v13": result_v13,
        "bubble": rewrite,
        "runtime_audit": audit,
        "performance_contract": {
            "docked_root_blur_owners": 1,
            "bubble_new_blur_regions": 0,
            "bubble_viewroot_manager_calls": 0,
            "bubble_show_hide_compositor_reconfigure": False,
            "floating_policy": "retain V13 carrier because floating geometry is independent",
        },
    }
