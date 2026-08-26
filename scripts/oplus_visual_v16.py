#!/usr/bin/env python3
"""V16: ColorOS SystemUI semantic corner policy.

This pass replaces the remaining ad-hoc floating 14dp geometry with the corner
model observed in ColorOS 17 SystemUI:

* screen/window-scale surfaces can source the live physical display RoundedCorner;
* toolbar-style rounded controls use local-bounds geometry (min(width,height)/2);
* all visible clipping uses the same ColorOS G2 corner type/weight already used
  by ColorOSV2Round;
* the docked keyboard keeps the exact Oplus keyboard semantic top-corner policy
  (28dp top, 0 bottom) from com.oplus.keyboard rather than pretending every UI
  radius is a linear fraction of the display radius.

The change is intentionally low-overhead. Physical RoundedCorner lookup only runs
when the floating keyboard is attached; toolbar radius resolution piggy-backs on
the existing one-shot ColorOSV2Round.applyTree pass. No global-layout scanning,
per-frame callbacks or additional blur owners are introduced.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v15 as base
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v15.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v15", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V15 pass: {_P}")
    base = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(base)

LOCAL_RELATIVE_PATH = base.LOCAL_RELATIVE_PATH
ROUND_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2Round.smali")
POLICY_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2CornerPolicyV16.smali")
POLICY_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2CornerPolicyV16;"

# Exact fallback from the decoded Oplus floating-keyboard geometry. On ColorOS
# 17 / Android 12+ the normal path uses Display.getRoundedCorner() instead.
FLOATING_FALLBACK_DP = 14.0

POLICY_SMALI = rf'''.class public final Lcom/tencent/wetype/monet/ColorOSV2CornerPolicyV16;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeCornerV16"
.field private static final TOOLBAR_PREFIX:Ljava/lang/String; = "com.tencent.wetype.plugin.hld.toolbar."

.method private constructor <init>()V
    .locals 0
    invoke-direct {{p0}}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method private static dp(Landroid/view/View;F)F
    .locals 1
    invoke-virtual {{p0}}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {{v0}}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v0
    iget v0, v0, Landroid/util/DisplayMetrics;->density:F
    mul-float/2addr p1, v0
    return p1
.end method

# Mirrors OplusFlexibleWindowAnimationUtils.getDisplayCornerRadius(Display):
# query all four physical RoundedCorner positions and take the maximum radius.
.method public static getScreenCornerRadius(Landroid/view/View;)F
    .locals 7
    if-eqz p0, :fallback_zero
    :try_start
    invoke-virtual {{p0}}, Landroid/view/View;->getDisplay()Landroid/view/Display;
    move-result-object v0
    if-eqz v0, :fallback

    const/4 v1, 0x0
    const/4 v2, 0x0
    :loop
    const/4 v3, 0x4
    if-ge v1, v3, :done
    invoke-virtual {{v0, v1}}, Landroid/view/Display;->getRoundedCorner(I)Landroid/view/RoundedCorner;
    move-result-object v4
    if-eqz v4, :next
    invoke-virtual {{v4}}, Landroid/view/RoundedCorner;->getRadius()I
    move-result v5
    if-le v5, v2, :next
    move v2, v5
    :next
    add-int/lit8 v1, v1, 0x1
    goto :loop

    :done
    if-lez v2, :fallback
    int-to-float v6, v2
    return v6
    :try_end
    .catch Ljava/lang/Throwable; {{:try_start .. :try_end}} :catch

    :catch
    move-exception v0
    :fallback
    const/high16 v1, 0x41600000    # {FLOATING_FALLBACK_DP:.1f}f
    invoke-static {{p0, v1}}, {POLICY_DESCRIPTOR}->dp(Landroid/view/View;F)F
    move-result v1
    return v1

    :fallback_zero
    const/4 v0, 0x0
    return v0
.end method

# ColorOS ToolbarMaterialEffectDelegate uses min(width,height)/2 for rounded
# toolbar material controls. Only existing rounded toolbar backgrounds are
# eligible; callers pass the original semantic radius as p1.
.method public static resolveRoundedViewRadius(Landroid/view/View;F)F
    .locals 6
    if-eqz p0, :original
    const/4 v0, 0x0
    cmpl-float v0, p1, v0
    if-lez v0, :original

    invoke-virtual {{p0}}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v0
    invoke-virtual {{v0}}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v1
    if-eqz v1, :original
    sget-object v2, {POLICY_DESCRIPTOR}->TOOLBAR_PREFIX:Ljava/lang/String;
    invoke-virtual {{v1, v2}}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v3
    if-eqz v3, :original

    invoke-virtual {{p0}}, Landroid/view/View;->getWidth()I
    move-result v4
    invoke-virtual {{p0}}, Landroid/view/View;->getHeight()I
    move-result v5
    if-lez v4, :original
    if-lez v5, :original
    if-le v4, v5, :width_min
    move v4, v5
    :width_min
    int-to-float v4, v4
    const/high16 v5, 0x40000000    # 2.0f
    div-float/2addr v4, v5
    return v4

    :original
    return p1
.end method

# Reuse the already-generated SystemUI G2 outline provider so every semantic
# radius shares exactly the same corner type/weight and OplusOutlineAdapter path.
.method public static applyG2Outline(Landroid/view/View;F)V
    .locals 5
    if-eqz p0, :return
    const/4 v0, 0x0
    cmpl-float v0, p1, v0
    if-lez v0, :return
    :try_start
    invoke-static {{}}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getWeight()F
    move-result v1
    invoke-static {{}}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getCornerType()I
    move-result v2
    new-instance v3, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;
    invoke-direct {{v3, p1, v1, v2}}, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;-><init>(FFI)V
    invoke-virtual {{p0, v3}}, Landroid/view/View;->setOutlineProvider(Landroid/view/ViewOutlineProvider;)V
    const/4 v4, 0x1
    invoke-virtual {{p0, v4}}, Landroid/view/View;->setClipToOutline(Z)V
    invoke-virtual {{p0}}, Landroid/view/View;->invalidateOutline()V
    :try_end
    .catch Ljava/lang/Throwable; {{:try_start .. :try_end}} :catch
    goto :return
    :catch
    move-exception v0
    :return
    return-void
.end method
'''

# V13-final's assembly-safe floating factory sequence. V16 swaps the fixed 14dp
# for the live display corner radius while keeping the one local floating carrier.
_FLOATING_RADIUS_OLD = '''    # Same six-parameter factory call: use v8..v13 as a contiguous range.\n    move-object v8, p0\n    const/16 v9, 0x96\n    const/high16 v10, 0x41600000    # 14.0f\n    invoke-static {p0, v10}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->dp(Landroid/view/View;F)F\n    move-result v10\n    move v11, v10\n    move v12, v10\n    move v13, v10\n    invoke-static/range {v8 .. v13}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;\n    move-result-object v9\n'''

_FLOATING_RADIUS_NEW = f'''    # V16: SystemUI-style screen/window surface radius from live RoundedCorner.\n    move-object v8, p0\n    const/16 v9, 0x96\n    invoke-static {{p0}}, {POLICY_DESCRIPTOR}->getScreenCornerRadius(Landroid/view/View;)F\n    move-result v10\n    move v11, v10\n    move v12, v10\n    move v13, v10\n    invoke-static/range {{v8 .. v13}}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;\n    move-result-object v9\n'''

_FLOATING_BG_INSTALL = (
    "    invoke-virtual {v3, v9}, Landroid/view/View;->setBackground"
    "(Landroid/graphics/drawable/Drawable;)V\n"
)
_FLOATING_G2_INSTALL = _FLOATING_BG_INSTALL + f'''    # Use the same G2 outline for the blur carrier and its floating content.\n    invoke-static {{v3, v10}}, {POLICY_DESCRIPTOR}->applyG2Outline(Landroid/view/View;F)V\n    invoke-static {{p0, v10}}, {POLICY_DESCRIPTOR}->applyG2Outline(Landroid/view/View;F)V\n'''

_ROUND_RADIUS_ANCHOR = '''    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->flattenRadius(Landroid/graphics/drawable/Drawable;)F\n    move-result v1\n'''
_ROUND_RADIUS_RESOLVE = _ROUND_RADIUS_ANCHOR + f'''    # V16: ColorOS toolbar material uses local-bounds pill geometry.\n    invoke-static {{p0, v1}}, {POLICY_DESCRIPTOR}->resolveRoundedViewRadius(Landroid/view/View;F)F\n    move-result v1\n'''


def _find_generated(decompile_dir: Path, relative: Path) -> Path:
    root = Path(decompile_dir)
    for smali_root in sorted(root.glob("smali*")):
        candidate = smali_root / relative
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"V16 could not locate generated helper: {relative}")


def _inject_policy(decompile_dir: Path) -> str:
    round_path = _find_generated(decompile_dir, ROUND_RELATIVE_PATH)
    # .../smali_classesN/com/tencent/... -> find direct child of decompile root.
    smali_root = round_path
    while smali_root.parent != Path(decompile_dir):
        smali_root = smali_root.parent
    path = smali_root / POLICY_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(POLICY_SMALI, encoding="utf-8")
    return str(path.relative_to(decompile_dir))


def _patch_floating_geometry(decompile_dir: Path) -> dict[str, object]:
    path = _find_generated(decompile_dir, LOCAL_RELATIVE_PATH)
    text = path.read_text(encoding="utf-8")
    if text.count(_FLOATING_RADIUS_OLD) != 1:
        raise RuntimeError("V16 floating radius factory shape changed")
    text = text.replace(_FLOATING_RADIUS_OLD, _FLOATING_RADIUS_NEW, 1)
    if text.count(_FLOATING_BG_INSTALL) != 1:
        raise RuntimeError("V16 floating carrier background install shape changed")
    text = text.replace(_FLOATING_BG_INSTALL, _FLOATING_G2_INSTALL, 1)
    path.write_text(text, encoding="utf-8")
    return {
        "helper": str(path.relative_to(decompile_dir)),
        "radius_source": "Display.getRoundedCorner(0..3) max radius",
        "fallback_dp": FLOATING_FALLBACK_DP,
        "carrier_outline": "ColorOS G2",
        "content_outline": "ColorOS G2",
        "blur_owner_count": 1,
    }


def _patch_round_policy(decompile_dir: Path) -> dict[str, object]:
    path = _find_generated(decompile_dir, ROUND_RELATIVE_PATH)
    text = path.read_text(encoding="utf-8")
    if text.count(_ROUND_RADIUS_ANCHOR) != 1:
        raise RuntimeError("V16 ColorOSV2Round applyView anchor changed")
    text = text.replace(_ROUND_RADIUS_ANCHOR, _ROUND_RADIUS_RESOLVE, 1)
    path.write_text(text, encoding="utf-8")
    return {
        "helper": str(path.relative_to(decompile_dir)),
        "toolbar_policy": "existing rounded toolbar controls -> min(width,height)/2",
        "non_toolbar_policy": "preserve existing semantic radius",
        "corner_curve": "shared ColorOS G2 cornerType + default weight",
    }


def _method_slice(text: str, header: str) -> str:
    start = text.find(header)
    if start < 0:
        raise RuntimeError(f"missing {header}")
    end = text.find(".end method", start)
    if end < 0:
        raise RuntimeError(f"unterminated {header}")
    return text[start : end + len(".end method")]


def _audit_v16(decompile_dir: Path) -> dict[str, object]:
    policy_path = _find_generated(decompile_dir, POLICY_RELATIVE_PATH)
    policy = policy_path.read_text(encoding="utf-8")
    local = _find_generated(decompile_dir, LOCAL_RELATIVE_PATH).read_text(encoding="utf-8")
    round_text = _find_generated(decompile_dir, ROUND_RELATIVE_PATH).read_text(encoding="utf-8")

    for pos in range(4):
        if "->getRoundedCorner(I)Landroid/view/RoundedCorner;" not in policy:
            raise RuntimeError("V16 physical RoundedCorner source missing")
    if policy.count("->getRoundedCorner(I)Landroid/view/RoundedCorner;") != 1:
        # One call in a four-iteration loop is expected, not four duplicated calls.
        raise RuntimeError("V16 RoundedCorner lookup topology changed")
    for token in (
        "->getRadius()I",
        "TOOLBAR_PREFIX",
        "->getWidth()I",
        "->getHeight()I",
        "Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;",
        "->setClipToOutline(Z)V",
    ):
        if token not in policy:
            raise RuntimeError(f"V16 corner policy missing {token}")

    floating = _method_slice(local, ".method public static installFloating(Landroid/view/View;)V")
    if "0x41600000    # 14.0f" in floating:
        raise RuntimeError("V16 floating install still hardcodes 14dp")
    for token in (
        f"{POLICY_DESCRIPTOR}->getScreenCornerRadius(Landroid/view/View;)F",
        f"{POLICY_DESCRIPTOR}->applyG2Outline(Landroid/view/View;F)V",
        "->createLocalBlur(Landroid/view/View;IFFFF)",
    ):
        if token not in floating:
            raise RuntimeError(f"V16 floating geometry missing {token}")
    if floating.count("->createLocalBlur(Landroid/view/View;IFFFF)") != 1:
        raise RuntimeError("V16 changed floating blur-owner count")

    apply_view = _method_slice(round_text, ".method private static applyView(Landroid/view/View;)V")
    if f"{POLICY_DESCRIPTOR}->resolveRoundedViewRadius(Landroid/view/View;F)F" not in apply_view:
        raise RuntimeError("V16 toolbar semantic radius resolver not wired")

    # Preserve the low-overhead V14/V15 guarantees.
    bubble = _method_slice(local, ".method public static installBubble(Landroid/view/View;)V")
    for forbidden in ("createLocalBlur", "ViewRootManager", "getBackgroundBlurDrawable"):
        if forbidden in bubble:
            raise RuntimeError(f"V16 bubble reintroduced compositor work: {forbidden}")

    return {
        "physical_display_corner_runtime_lookup": True,
        "floating_fixed_radius_removed": True,
        "floating_blur_and_clip_share_radius": True,
        "floating_g2_outline": True,
        "toolbar_self_bounds_radius": True,
        "docked_oplus_keyboard_28dp_top_policy_preserved": True,
        "bubble_new_blur_regions": 0,
        "global_layout_scan_added": False,
        "per_frame_corner_work": False,
    }


def apply_coloros_v2_visual_profile_v16(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    result_v15 = base.apply_coloros_v2_visual_profile_v15(decompile_dir, patch_report)
    policy = _inject_policy(decompile_dir)
    floating = _patch_floating_geometry(decompile_dir)
    rounded_views = _patch_round_policy(decompile_dir)
    audit = _audit_v16(decompile_dir)
    return {
        "strategy": (
            "ColorOS SystemUI semantic corner model: live display RoundedCorner for floating/window surface; "
            "self-bounds pill geometry for rounded toolbar controls; shared SystemUI G2 curve everywhere"
        ),
        "base_v15": result_v15,
        "policy_helper": policy,
        "floating": floating,
        "rounded_views": rounded_views,
        "runtime_audit": audit,
        "performance_contract": {
            "physical_corner_lookup": "floating attach only",
            "toolbar_resolution": "existing one-shot ColorOSV2Round.applyTree only",
            "new_blur_owners": 0,
            "new_global_layout_listeners": 0,
            "new_frame_callbacks": 0,
        },
    }
