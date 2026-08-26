#!/usr/bin/env python3
"""Final V13 root-source and audit correction.

The proven root keyboard implementation constructs ViewRootManager from
`target.getRootView()` and then attaches the returned BackgroundBlurDrawable to
the target surface. WeType Tool likewise asks the already-attached source
View's ViewRootImpl for the drawable and later assigns that drawable to a
carrier. Apply the same root/target split to V13 local surfaces and add the
neutral local tint through ViewRootManager.setColor().

This wrapper also fixes the V13 static transaction audit: the previous audit
searched the whole helper and accidentally matched the stripBackgrounds method
definition instead of the call inside installFloating(). The corrected audit
slices that method and verifies control-flow/ordering there.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v13 as base
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v13.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v13", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V13 pass: {_P}")
    base = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(base)


_OLD_FACTORY = '''    new-instance v0, Lcom/oplus/view/ViewRootManager;\n    invoke-direct {v0, p0}, Lcom/oplus/view/ViewRootManager;-><init>(Landroid/view/View;)V\n    invoke-virtual {v0}, Lcom/oplus/view/ViewRootManager;->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;\n    move-result-object v1\n    if-eqz v1, :fail_try\n    invoke-virtual {v0, p1}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V\n'''

_NEW_FACTORY = '''    # Match the already-proven OplusKeyboardBlur root/target split.\n    invoke-virtual {p0}, Landroid/view/View;->getRootView()Landroid/view/View;\n    move-result-object v3\n    if-nez v3, :have_root\n    move-object v3, p0\n    :have_root\n    new-instance v0, Lcom/oplus/view/ViewRootManager;\n    invoke-direct {v0, v3}, Lcom/oplus/view/ViewRootManager;-><init>(Landroid/view/View;)V\n    invoke-virtual {v0}, Lcom/oplus/view/ViewRootManager;->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;\n    move-result-object v1\n    if-eqz v1, :fail_try\n    # Local surfaces use a restrained neutral tint. Root FAST_KAWASE/material\n    # parameters remain owned exclusively by OplusKeyboardBlur.\n    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->bubbleTint(Landroid/view/View;)I\n    move-result v2\n    invoke-virtual {v0, v2}, Lcom/oplus/view/ViewRootManager;->setColor(I)V\n    invoke-virtual {v0, p1}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V\n'''

if _OLD_FACTORY not in base.LOCAL_HELPER_SMALI:
    raise RuntimeError("V13 local factory shape changed; refusing an unverified rewrite")

LOCAL_HELPER_SMALI = base.LOCAL_HELPER_SMALI.replace(_OLD_FACTORY, _NEW_FACTORY, 1)

# Preserve public constants expected by tests/build metadata.
LOCAL_DESCRIPTOR = base.LOCAL_DESCRIPTOR
LOCAL_RELATIVE_PATH = base.LOCAL_RELATIVE_PATH
V13_KEY_PREVIEW_COLORS = base.V13_KEY_PREVIEW_COLORS
FLOAT_BASE_CLASS = base.FLOAT_BASE_CLASS
FLOATING_CONTENT_CLASS = base.FLOATING_CONTENT_CLASS
VOICE_CLASS = base.VOICE_CLASS


def _read_injected_helper(decompile_dir: Path) -> str:
    root = Path(decompile_dir)
    for smali_root in sorted(root.glob("smali*")):
        candidate = smali_root / LOCAL_RELATIVE_PATH
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise RuntimeError("V13 local helper missing")


def _method_slice(text: str, method_prefix: str) -> str:
    start = text.find(method_prefix)
    if start < 0:
        raise RuntimeError(f"V13 helper missing {method_prefix}")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError(f"V13 helper has unterminated {method_prefix}")
    return text[start : end + len(".end method")]


def _audit_v13_fixed(decompile_dir: Path) -> dict[str, object]:
    root = Path(decompile_dir)
    helper = _read_injected_helper(root)
    float_path = base.v12._find_class_file(root, FLOAT_BASE_CLASS)
    floating_path = base.v12._find_class_file(root, FLOATING_CONTENT_CLASS)
    if float_path is None or floating_path is None:
        raise RuntimeError("V13 target classes missing after patch")
    ftext = float_path.read_text(encoding="utf-8")
    fltext = floating_path.read_text(encoding="utf-8")

    forbidden = (
        "getViewRootImpl",
        "createBackgroundBlurDrawable",
        "Landroid/view/ViewRootImpl;",
        "->setBlurParams(",
        "OplusBlurParam",
    )
    present = [item for item in forbidden if item in helper]
    if present:
        raise RuntimeError(
            "V13 helper contains forbidden hidden/root-global paths: "
            + ", ".join(present)
        )
    required = (
        "Lcom/oplus/view/ViewRootManager;",
        "->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;",
        "->setBlurRadius(I)V",
        "->setColor(I)V",
        "Landroid/view/View;->getRootView()Landroid/view/View;",
        "WeTypeBlurCarrier_Float",
        "WeTypeBlurHighlight_Float",
        "IdentityHashMap",
        "floating blur unavailable; original backgrounds kept",
    )
    missing = [item for item in required if item not in helper]
    if missing:
        raise RuntimeError(
            "V13 helper missing required primitives: " + ", ".join(missing)
        )

    bubble_calls = ftext.count(
        f"{LOCAL_DESCRIPTOR}->installBubble(Landroid/view/View;)V"
    )
    fill_calls = ftext.count(
        f"{LOCAL_DESCRIPTOR}->applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V"
    )
    stroke_calls = ftext.count(
        f"{LOCAL_DESCRIPTOR}->restoreBubbleStroke(Landroid/graphics/Paint;)V"
    )
    floating_install = fltext.count(
        f"{LOCAL_DESCRIPTOR}->installFloating(Landroid/view/View;)V"
    )
    floating_restore = fltext.count(
        f"{LOCAL_DESCRIPTOR}->restoreFloating(Landroid/view/View;)V"
    )
    if (
        bubble_calls,
        fill_calls,
        stroke_calls,
        floating_install,
        floating_restore,
    ) != (1, 1, 1, 1, 1):
        raise RuntimeError(
            "V13 hook cardinality mismatch: "
            f"bubble={bubble_calls} fill={fill_calls} stroke={stroke_calls} "
            f"floating={floating_install}/{floating_restore}"
        )
    if "setAlpha(F)V" in fltext or "onWindowVisibilityChanged(I)V" in fltext:
        raise RuntimeError("V13 floating target gained a high-frequency lifecycle hook")

    install = _method_slice(
        helper, ".method public static installFloating(Landroid/view/View;)V"
    )
    null_branch = install.find("if-eqz v9, :rollback_carrier")
    set_bg = install.find(
        "invoke-virtual {v3, v9}, Landroid/view/View;->setBackground"
    )
    strip = install.find(
        "->stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V"
    )
    rollback_label = install.find(":rollback_carrier")
    if min(null_branch, set_bg, strip, rollback_label) < 0:
        raise RuntimeError("V13 floating transaction markers missing")
    # Textual order of the rollback label is irrelevant; the conditional branch
    # jumps over the mutating path. What matters is that success installs the
    # blur background before any original background is stripped.
    if not (null_branch < set_bg < strip):
        raise RuntimeError("V13 floating transaction ordering invariant failed")

    return {
        "bubble_post_N_hook": bubble_calls,
        "bubble_fail_closed_fill_hook": fill_calls,
        "floating_attach_detach_hooks": [floating_install, floating_restore],
        "local_viewroot_manager": True,
        "manager_source": "target.getRootView() with target fallback",
        "hidden_viewrootimpl_reflection": False,
        "local_oplus_blur_param_owner": False,
        "global_layout_scan_added": False,
        "background_strip_after_blur_success": True,
        "null_blur_branch_preserves_original_backgrounds": True,
    }


def apply_coloros_v2_visual_profile_v13(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    original_helper = base.LOCAL_HELPER_SMALI
    original_audit = base._audit_v13
    base.LOCAL_HELPER_SMALI = LOCAL_HELPER_SMALI
    base._audit_v13 = _audit_v13_fixed
    try:
        result = base.apply_coloros_v2_visual_profile_v13(decompile_dir, patch_report)
    finally:
        base.LOCAL_HELPER_SMALI = original_helper
        base._audit_v13 = original_audit

    result["root_source_correction"] = {
        "manager_source": "target.getRootView() with target fallback",
        "drawable_target": "bubble background or floating Tool-style carrier",
        "local_tint": "ViewRootManager.setColor neutral day/night tint",
        "parity": (
            "matches OplusKeyboardBlur's verified root/target split and WeType Tool's "
            "source-ViewRoot / separate-carrier ownership model"
        ),
    }
    result["runtime_audit"] = _audit_v13_fixed(decompile_dir)
    return result
