#!/usr/bin/env python3
"""V13 final wrapper: normalize metadata and keep injected smali assemblable.

Two real-build-only problems were exposed after the static V13 tests passed:

1. V12's result does not guarantee top-level ``key_preview``/``floating``
   metadata blocks, while V13 annotates them.
2. ``createLocalBlur(View, int, float, float, float, float)`` has six Dalvik
   argument registers. The normal ``invoke-static {..}`` encoding accepts at
   most five registers. apktool therefore correctly rejected the generated
   helper even though the Python/static call-site tests passed.

Keep V13's runtime design unchanged, but marshal those two six-argument calls
into contiguous locals and use ``invoke-static/range``. This is a bytecode
encoding correction, not a material/lifecycle change.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v13_fix as impl
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v13_fix.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v13_fix", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V13 fix: {_P}")
    impl = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(impl)


_BUBBLE_INVOKE_OLD = '''    const/16 v1, 0x64\n    const/4 v2, 0x0\n    const/4 v3, 0x0\n    const/4 v4, 0x0\n    const/4 v5, 0x0\n    invoke-static {p0, v1, v2, v3, v4, v5}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;\n    move-result-object v6\n'''

_BUBBLE_INVOKE_NEW = '''    # invoke-static has a five-register ceiling. Marshal the six parameters\n    # into one contiguous local range for the /range encoding.\n    move-object v1, p0\n    const/16 v2, 0x64\n    const/4 v3, 0x0\n    const/4 v4, 0x0\n    const/4 v5, 0x0\n    const/4 v6, 0x0\n    invoke-static/range {v1 .. v6}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;\n    move-result-object v6\n'''

_FLOATING_INVOKE_OLD = '''    const/16 v7, 0x96\n    const/high16 v8, 0x41600000    # 14.0f\n    invoke-static {p0, v8}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->dp(Landroid/view/View;F)F\n    move-result v8\n    invoke-static {p0, v7, v8, v8, v8, v8}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;\n    move-result-object v9\n'''

_FLOATING_INVOKE_NEW = '''    # Same six-parameter factory call: use v8..v13 as a contiguous range.\n    move-object v8, p0\n    const/16 v9, 0x96\n    const/high16 v10, 0x41600000    # 14.0f\n    invoke-static {p0, v10}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->dp(Landroid/view/View;F)F\n    move-result v10\n    move v11, v10\n    move v12, v10\n    move v13, v10\n    invoke-static/range {v8 .. v13}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;\n    move-result-object v9\n'''


def _make_local_helper_asm_safe(text: str) -> str:
    """Rewrite exactly the two known six-register invokes into /range form."""
    if text.count(_BUBBLE_INVOKE_OLD) != 1:
        raise RuntimeError(
            "V13 bubble local-blur invoke shape changed; refusing an unchecked smali rewrite"
        )
    if text.count(_FLOATING_INVOKE_OLD) != 1:
        raise RuntimeError(
            "V13 floating local-blur invoke shape changed; refusing an unchecked smali rewrite"
        )

    text = text.replace(_BUBBLE_INVOKE_OLD, _BUBBLE_INVOKE_NEW, 1)
    text = text.replace(_FLOATING_INVOKE_OLD, _FLOATING_INVOKE_NEW, 1)

    # Guard against reintroducing the exact apktool failure that motivated this
    # wrapper. createLocalBlur has six arguments and must only be called /range.
    bad_call = "invoke-static {"
    for line in text.splitlines():
        if "->createLocalBlur(Landroid/view/View;IFFFF)" in line:
            if bad_call in line or "invoke-static/range" not in line:
                raise RuntimeError(f"non-range six-register createLocalBlur invoke remains: {line}")
    return text


ASM_SAFE_LOCAL_HELPER_SMALI = _make_local_helper_asm_safe(impl.LOCAL_HELPER_SMALI)


def apply_coloros_v2_visual_profile_v13(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    base13 = impl.base
    original_v12_apply = base13.v12.apply_coloros_v2_visual_profile_v12
    original_local_helper = impl.LOCAL_HELPER_SMALI

    def _normalized_v12(*args, **kwargs):
        result = original_v12_apply(*args, **kwargs)
        if not isinstance(result, dict):
            raise RuntimeError("V12 visual pass returned non-dict metadata")
        result.setdefault("key_preview", {})
        result.setdefault("floating", {})
        return result

    base13.v12.apply_coloros_v2_visual_profile_v12 = _normalized_v12
    impl.LOCAL_HELPER_SMALI = ASM_SAFE_LOCAL_HELPER_SMALI
    try:
        result = impl.apply_coloros_v2_visual_profile_v13(
            decompile_dir, patch_report
        )
    finally:
        impl.LOCAL_HELPER_SMALI = original_local_helper
        base13.v12.apply_coloros_v2_visual_profile_v12 = original_v12_apply

    result["metadata_shape_normalized"] = True
    result["smali_assembly_correction"] = {
        "six_register_factory_calls": 2,
        "encoding": "invoke-static/range",
        "bubble_range": "v1..v6",
        "floating_range": "v8..v13",
        "runtime_semantics_changed": False,
    }
    return result
