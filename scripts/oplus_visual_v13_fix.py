#!/usr/bin/env python3
"""Final V13 root-source correction.

The proven root keyboard implementation constructs ViewRootManager from
`target.getRootView()` and then attaches the returned BackgroundBlurDrawable to
the target surface. WeType Tool likewise asks the already-attached source
View's ViewRootImpl for the drawable and later assigns that drawable to a
carrier. Apply the same root/target split to V13 local surfaces and add the
neutral local tint through ViewRootManager.setColor().
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


def apply_coloros_v2_visual_profile_v13(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    original = base.LOCAL_HELPER_SMALI
    base.LOCAL_HELPER_SMALI = LOCAL_HELPER_SMALI
    try:
        result = base.apply_coloros_v2_visual_profile_v13(decompile_dir, patch_report)
    finally:
        base.LOCAL_HELPER_SMALI = original

    result["root_source_correction"] = {
        "manager_source": "target.getRootView() with target fallback",
        "drawable_target": "bubble background or floating Tool-style carrier",
        "local_tint": "ViewRootManager.setColor neutral day/night tint",
        "parity": (
            "matches OplusKeyboardBlur's verified root/target split and WeType Tool's "
            "source-ViewRoot / separate-carrier ownership model"
        ),
    }
    return result
