#!/usr/bin/env python3
"""V6 visual fixes for the ColorOS keyboard experiment.

Device feedback from the V5 APK exposed four independent issues:

1. G2/V2 smooth corners were active, but WeType's original key radius was too
   small.  V6 keeps the ColorOS G2 renderer and raises only keyboard-key radii
   toward the Breeno/ColorOS key geometry (24% of the key's short side, never
   smaller than the app's original radius).
2. V4 restored WeType shadow resources that are actually rendered as a hard
   bottom strip.  V4 now keeps those resources transparent; this pass records
   the corrected policy in the V6 report.
3. V5's runtime outline adapter zeroed GradientDrawable radii before clipping.
   That turned circular toolbar backgrounds into visible squares whenever the
   outline was not the sole painter.  V6 preserves the original drawable shape
   and uses the ColorOS outline only as the clipping boundary.
4. WeType keeps the base self-draw keyboard mounted under its emoji overlay.
   With the root made transparent for compositor blur, the QWERTY keyboard was
   therefore visible underneath the emoji page.  V6 detects the real emoji
   board and temporarily suppresses only the base self-draw keyboard roots,
   restoring their exact previous alpha when the emoji board closes.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

try:
    import oplus_visual_v5b as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v5b.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v5b", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V5b pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


KEY_HELPER_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2KeyRoundV6;"
KEY_HELPER_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2KeyRoundV6.smali")
HIERARCHY_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;"
HIERARCHY_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2HierarchyV6.smali")

# A standard ColorOS keyboard key is materially rounder than WeType's stock
# geometry.  Using a ratio rather than dp keeps the patch density-independent.
# For a ~48 dp high / ~42 dp wide key this resolves to roughly 10 dp.
KEY_RADIUS_RATIO = 0.24


KEY_HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2KeyRoundV6;
.super Ljava/lang/Object;

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method private static targetRadius(Landroid/graphics/RectF;FF)F
    .locals 3
    invoke-virtual {p0}, Landroid/graphics/RectF;->width()F
    move-result v0
    invoke-virtual {p0}, Landroid/graphics/RectF;->height()F
    move-result v1
    invoke-static {v0, v1}, Ljava/lang/Math;->min(FF)F
    move-result v0
    const v1, 0x3e75c28f    # 0.24f
    mul-float/2addr v0, v1
    invoke-static {p1, p2}, Ljava/lang/Math;->max(FF)F
    move-result v1
    invoke-static {v0, v1}, Ljava/lang/Math;->max(FF)F
    move-result v0
    const/4 v2, 0x0
    cmpl-float v2, v0, v2
    if-lez v2, :fallback
    return v0
    :fallback
    return p1
.end method

.method public static drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V
    .locals 1
    invoke-static {p1, p2, p3}, Lcom/tencent/wetype/monet/ColorOSV2KeyRoundV6;->targetRadius(Landroid/graphics/RectF;FF)F
    move-result v0
    invoke-static {p0, p1, v0, v0, p4}, Lcom/tencent/wetype/monet/ColorOSV2Round;->drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V
    return-void
.end method

.method public static drawRoundRect(Landroid/graphics/Canvas;FFFFFFLandroid/graphics/Paint;)V
    .locals 2
    new-instance v0, Landroid/graphics/RectF;
    invoke-direct {v0, p1, p2, p3, p4}, Landroid/graphics/RectF;-><init>(FFFF)V
    invoke-static {v0, p5, p6}, Lcom/tencent/wetype/monet/ColorOSV2KeyRoundV6;->targetRadius(Landroid/graphics/RectF;FF)F
    move-result v1
    invoke-static {p0, v0, v1, v1, p7}, Lcom/tencent/wetype/monet/ColorOSV2Round;->drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V
    return-void
.end method

.method public static addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V
    .locals 1
    invoke-static {p1, p2, p3}, Lcom/tencent/wetype/monet/ColorOSV2KeyRoundV6;->targetRadius(Landroid/graphics/RectF;FF)F
    move-result v0
    invoke-static {p0, p1, v0, v0, p4}, Lcom/tencent/wetype/monet/ColorOSV2Round;->addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V
    return-void
.end method
'''


HIERARCHY_HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;
.super Ljava/lang/Object;

.field private static final suppressedAlpha:Ljava/util/WeakHashMap;

.method static constructor <clinit>()V
    .locals 1
    new-instance v0, Ljava/util/WeakHashMap;
    invoke-direct {v0}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v0, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->suppressedAlpha:Ljava/util/WeakHashMap;
    return-void
.end method

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method private static isEmojiBoard(Landroid/view/View;)Z
    .locals 5
    if-eqz p0, :false
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :false
    invoke-virtual {p0}, Landroid/view/View;->getWidth()I
    move-result v0
    if-lez v0, :false
    invoke-virtual {p0}, Landroid/view/View;->getHeight()I
    move-result v0
    if-lez v0, :false
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v1
    invoke-virtual {v1}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v2
    const-string v3, "com.tencent.wetype.plugin.hld.emoji.ImeEmojiBoardView"
    invoke-virtual {v2, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-nez v4, :true
    const-string v3, "com.tencent.wetype.plugin.hld.emoji.ImeEmojiShowBoardView"
    invoke-virtual {v2, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-nez v4, :true
    :false
    const/4 v0, 0x0
    return v0
    :true
    const/4 v0, 0x1
    return v0
.end method

.method private static hasVisibleEmojiBoard(Landroid/view/View;)Z
    .locals 5
    if-eqz p0, :false
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->isEmojiBoard(Landroid/view/View;)Z
    move-result v0
    if-nez v0, :true
    instance-of v0, p0, Landroid/view/ViewGroup;
    if-eqz v0, :false
    check-cast p0, Landroid/view/ViewGroup;
    invoke-virtual {p0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v1
    const/4 v2, 0x0
    :loop
    if-ge v2, v1, :false
    invoke-virtual {p0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v3
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->hasVisibleEmojiBoard(Landroid/view/View;)Z
    move-result v4
    if-nez v4, :true
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :true
    const/4 v0, 0x1
    return v0
    :false
    const/4 v0, 0x0
    return v0
.end method

.method private static isBaseSelfDrawKeyboard(Landroid/view/View;)Z
    .locals 5
    if-eqz p0, :false
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v1
    const-string v2, "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S"
    invoke-virtual {v1, v2}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v3
    if-eqz v3, :false
    const-string v2, "Keyboard"
    invoke-virtual {v1, v2}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v3
    if-eqz v3, :false
    const-string v2, "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S11EmojiKeyboard"
    invoke-virtual {v1, v2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-nez v4, :false
    const-string v2, "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S5SymbolKeyboard"
    invoke-virtual {v1, v2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-nez v4, :false
    const/4 v0, 0x1
    return v0
    :false
    const/4 v0, 0x0
    return v0
.end method

.method private static updateKeyboardTree(Landroid/view/View;Z)V
    .locals 7
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->isBaseSelfDrawKeyboard(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :children
    sget-object v1, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->suppressedAlpha:Ljava/util/WeakHashMap;
    if-eqz p1, :restore
    invoke-virtual {v1, p0}, Ljava/util/WeakHashMap;->containsKey(Ljava/lang/Object;)Z
    move-result v2
    if-nez v2, :force_hidden
    invoke-virtual {p0}, Landroid/view/View;->getAlpha()F
    move-result v3
    invoke-static {v3}, Ljava/lang/Float;->valueOf(F)Ljava/lang/Float;
    move-result-object v4
    invoke-virtual {v1, p0, v4}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    :force_hidden
    const/4 v5, 0x0
    invoke-virtual {p0, v5}, Landroid/view/View;->setAlpha(F)V
    goto :children

    :restore
    invoke-virtual {v1, p0}, Ljava/util/WeakHashMap;->remove(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v2
    if-eqz v2, :children
    check-cast v2, Ljava/lang/Float;
    invoke-virtual {v2}, Ljava/lang/Float;->floatValue()F
    move-result v3
    invoke-virtual {p0, v3}, Landroid/view/View;->setAlpha(F)V

    :children
    instance-of v0, p0, Landroid/view/ViewGroup;
    if-eqz v0, :return
    check-cast p0, Landroid/view/ViewGroup;
    invoke-virtual {p0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v1
    const/4 v2, 0x0
    :loop
    if-ge v2, v1, :return
    invoke-virtual {p0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v3
    invoke-static {v3, p1}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->updateKeyboardTree(Landroid/view/View;Z)V
    add-int/lit8 v2, v2, 0x1
    goto :loop

    :return
    return-void
.end method

.method public static apply(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->hasVisibleEmojiBoard(Landroid/view/View;)Z
    move-result v0
    invoke-static {p0, v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->updateKeyboardTree(Landroid/view/View;Z)V
    :return
    return-void
.end method
'''


def _smali_root_from_visual_result(
    decompile_dir: Path, visual_result: dict[str, object]
) -> Path:
    injected = visual_result.get("injected_helpers")
    if not isinstance(injected, list) or not injected:
        raise RuntimeError("V5 result did not expose injected helper paths")
    first = Path(decompile_dir) / str(injected[0])
    for parent in first.parents:
        if parent.parent == Path(decompile_dir) and parent.name.startswith("smali"):
            return parent
    raise RuntimeError(f"Could not resolve smali root from {first}")


def _patch_key_round_calls(decompile_dir: Path) -> dict[str, object]:
    root = Path(decompile_dir)
    changed_files: list[str] = []
    count = 0
    pattern = re.compile(
        r"Lcom/tencent/wetype/monet/ColorOSV2Round;->"
        r"(?P<method>drawRoundRect|addRoundRect)"
        r"(?P<sig>\([^\n]+)"
    )

    for smali_root in sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith("smali")]
    ):
        scope = smali_root / "com/tencent/wetype/plugin/hld/keyboard/selfdraw"
        if not scope.is_dir():
            continue
        for path in scope.rglob("*.smali"):
            content = path.read_text(encoding="utf-8")

            def repl(match: re.Match[str]) -> str:
                nonlocal count
                sig = match.group("sig")
                # Per-corner [F radii carry intentional asymmetric geometry;
                # leave those on the base V5 helper rather than flattening them.
                if "[F" in sig:
                    return match.group(0)
                count += 1
                return (
                    f"{KEY_HELPER_DESCRIPTOR}->{match.group('method')}"
                    f"{sig}"
                )

            patched = pattern.sub(repl, content)
            if patched != content:
                path.write_text(patched, encoding="utf-8")
                changed_files.append(str(path.relative_to(root)))

    if count == 0:
        raise RuntimeError("V6 found no self-draw key round-rect calls to retarget")
    return {"calls": count, "files": sorted(changed_files)}


def _preserve_runtime_drawable_geometry(
    decompile_dir: Path, visual_result: dict[str, object]
) -> str:
    root = Path(decompile_dir)
    injected = visual_result.get("injected_helpers")
    assert isinstance(injected, list)
    helper_rel = next(
        (str(p) for p in injected if str(p).endswith("ColorOSV2Round.smali")), None
    )
    if helper_rel is None:
        raise RuntimeError("Could not locate ColorOSV2Round helper")
    helper = root / helper_rel
    content = helper.read_text(encoding="utf-8")

    mutations = (
        "    invoke-virtual {p0, v1}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V\n",
        "    invoke-virtual {p0, v5}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadii([F)V\n",
    )
    removed = 0
    for mutation in mutations:
        if mutation in content:
            content = content.replace(
                mutation,
                "    # V6: preserve original drawable radius; the ColorOS outline is clip-only.\n",
                1,
            )
            removed += 1
    if removed != 2:
        raise RuntimeError(
            f"Expected to remove both V5 GradientDrawable flattening mutations, removed={removed}"
        )
    helper.write_text(content, encoding="utf-8")
    return helper_rel


def _inject_v6_helpers(
    decompile_dir: Path, visual_result: dict[str, object]
) -> list[str]:
    root = _smali_root_from_visual_result(Path(decompile_dir), visual_result)
    files = {
        KEY_HELPER_RELATIVE_PATH: KEY_HELPER_SMALI,
        HIERARCHY_RELATIVE_PATH: HIERARCHY_HELPER_SMALI,
    }
    written: list[str] = []
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(path.relative_to(decompile_dir)))
    return written


def _patch_hierarchy_hooks(
    decompile_dir: Path, visual_result: dict[str, object]
) -> dict[str, str]:
    root = Path(decompile_dir)
    injected = visual_result.get("injected_helpers")
    assert isinstance(injected, list)
    listener_rel = next(
        (str(p) for p in injected if str(p).endswith("ColorOSV2Round$GlobalLayoutListener.smali")),
        None,
    )
    if listener_rel is None:
        raise RuntimeError("Could not locate V5 global-layout listener")
    listener = root / listener_rel
    content = listener.read_text(encoding="utf-8")
    anchor = (
        "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;"
        "->applyTree(Landroid/view/View;)V\n"
    )
    hierarchy_call = (
        "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;"
        "->apply(Landroid/view/View;)V\n"
    )
    if hierarchy_call.strip() not in content:
        if anchor not in content:
            raise RuntimeError("Could not locate V5 applyTree call in global-layout listener")
        content = content.replace(anchor, anchor + hierarchy_call, 1)
        listener.write_text(content, encoding="utf-8")

    runnable_rel = str(visual_result.get("runnable") or "")
    if not runnable_rel:
        raise RuntimeError("V5 result did not expose apply runnable")
    runnable = root / runnable_rel
    rtext = runnable.read_text(encoding="utf-8")
    install_anchor = (
        "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;"
        "->install(Landroid/view/View;)V\n"
    )
    if hierarchy_call.strip() not in rtext:
        if install_anchor not in rtext:
            raise RuntimeError("Could not locate V5 ColorOSV2Round.install call in apply runnable")
        rtext = rtext.replace(install_anchor, install_anchor + hierarchy_call, 1)
        runnable.write_text(rtext, encoding="utf-8")

    return {
        "global_layout_listener": listener_rel,
        "apply_runnable": runnable_rel,
    }


def apply_coloros_v2_visual_profile_v6(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    visual_v5 = base.apply_coloros_v2_visual_profile(decompile_dir, patch_report)

    # Retarget key paint geometry before injecting the V6 helper itself, so the
    # helper's fallback call back into ColorOSV2Round cannot be rewritten.
    key_round = _patch_key_round_calls(decompile_dir)
    preserved_helper = _preserve_runtime_drawable_geometry(decompile_dir, visual_v5)
    injected = _inject_v6_helpers(decompile_dir, visual_v5)
    hooks = _patch_hierarchy_hooks(decompile_dir, visual_v5)

    return {
        "strategy": (
            "V5 ColorOS G2/V2 renderer + Breeno-like key radius + preserved circular chrome + "
            "emoji/base-keyboard hierarchy suppression"
        ),
        "base_v5": visual_v5,
        "key_radius": {
            "ratio_of_short_side": KEY_RADIUS_RATIO,
            "policy": "max(original radius, short-side * 0.24)",
            "rewrites": key_round,
        },
        "runtime_drawable_geometry": {
            "helper": preserved_helper,
            "policy": (
                "do not zero GradientDrawable radii; retain circle/pill geometry and use "
                "OplusOutlineAdapter only as the smooth clipping boundary"
            ),
        },
        "emoji_hierarchy": {
            "overlay_roots": [
                "com.tencent.wetype.plugin.hld.emoji.ImeEmojiBoardView",
                "com.tencent.wetype.plugin.hld.emoji.ImeEmojiShowBoardView",
            ],
            "suppressed_base_keyboard_scope": (
                "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S*Keyboard except "
                "S11EmojiKeyboard/S5SymbolKeyboard"
            ),
            "restore_policy": "WeakHashMap<View, Float> restores exact prior alpha",
            "hooks": hooks,
        },
        "v4_shadow_policy": "all WeType key shadow tokens remain transparent",
        "injected_helpers": injected,
    }
