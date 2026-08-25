#!/usr/bin/env python3
"""ColorOS 17 G2/V2 smooth corners + system-font pass for WeType.

This pass complements the root FAST_KAWASE material installed by oplus_blur_v2.
It replaces keyboard-side explicit Canvas/Path round-rect drawing with the
ColorOS framework's G2 implementation, applies a G2 smooth outline to rounded
View backgrounds that are inflated from resources, and removes WeType's bundled
keyboard typefaces in favor of the device's default system family.

SystemUI 17 evidence used by this pass (com.android.systemui 179902):
- OplusSmoothRoundedManager.getG2CornerType()
- OplusSmoothRoundedManager.getDefaultG2Weight()
- OplusCanvas.drawSmoothRoundRect(..., weight)
- OplusPathAdapter(Path, cornerType).addSmoothRoundRect(..., weight)
- OplusOutlineAdapter(Outline, cornerType).setSmoothRoundRect(..., radius, weight)

The transform is deliberately scoped to IME-facing HLD packages for static
Canvas/Path/typeface rewrites. Runtime tree adaptation is attached to the real
IME root so XML-inflated keyboard/panel children are covered as they appear.
"""

from __future__ import annotations

import re
from pathlib import Path

ROUND_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2Round;"
ROUND_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2Round.smali")
OUTLINE_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;"
OUTLINE_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2Round$OutlineProvider.smali")
LAYOUT_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;"
LAYOUT_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener.smali")
FONT_DESCRIPTOR = "Lcom/tencent/wetype/monet/SystemFontBridge;"
FONT_RELATIVE_PATH = Path("com/tencent/wetype/monet/SystemFontBridge.smali")

IME_VISUAL_SCOPES = (
    "/com/tencent/wetype/plugin/hld/keyboard/",
    "/com/tencent/wetype/plugin/hld/candidate/",
    "/com/tencent/wetype/plugin/hld/toolbar/",
    "/com/tencent/wetype/plugin/hld/oldsymbol/",
    "/com/tencent/wetype/plugin/hld/sticker/",
    "/com/tencent/wetype/plugin/hld/ai/",
)

ROUND_CALLS = {
    "Landroid/graphics/Canvas;->drawRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V":
        f"{ROUND_DESCRIPTOR}->drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V",
    "Landroid/graphics/Canvas;->drawRoundRect(FFFFFFLandroid/graphics/Paint;)V":
        f"{ROUND_DESCRIPTOR}->drawRoundRect(Landroid/graphics/Canvas;FFFFFFLandroid/graphics/Paint;)V",
    "Landroid/graphics/Path;->addRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V":
        f"{ROUND_DESCRIPTOR}->addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V",
    "Landroid/graphics/Path;->addRoundRect(Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;)V":
        f"{ROUND_DESCRIPTOR}->addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;)V",
    "Landroid/graphics/Path;->addRoundRect(FFFF[FLandroid/graphics/Path$Direction;)V":
        f"{ROUND_DESCRIPTOR}->addRoundRect(Landroid/graphics/Path;FFFF[FLandroid/graphics/Path$Direction;)V",
}

ROUND_HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2Round;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeOplusRoundV2"
.field private static final installed:Ljava/util/WeakHashMap;

.method static constructor <clinit>()V
    .locals 1
    new-instance v0, Ljava/util/WeakHashMap;
    invoke-direct {v0}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v0, Lcom/tencent/wetype/monet/ColorOSV2Round;->installed:Ljava/util/WeakHashMap;
    return-void
.end method

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static getCornerType()I
    .locals 2
    :try_start
    invoke-static {}, Lcom/oplus/view/OplusSmoothRoundedManager;->getG2CornerType()I
    move-result v0
    return v0
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    :catch
    move-exception v0
    const/4 v1, 0x1
    return v1
.end method

.method public static getWeight()F
    .locals 2
    :try_start
    invoke-static {}, Lcom/oplus/view/OplusSmoothRoundedManager;->getDefaultG2Weight()F
    move-result v0
    const/4 v1, 0x0
    cmpl-float v1, v0, v1
    if-lez v1, :fallback
    return v0
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    :catch
    move-exception v1
    :fallback
    const/high16 v0, 0x40400000    # 3.0f
    return v0
.end method

.method public static drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V
    .locals 7
    :try_start
    new-instance v0, Lcom/oplus/graphics/OplusCanvas;
    invoke-direct {v0, p0}, Lcom/oplus/graphics/OplusCanvas;-><init>(Landroid/graphics/Canvas;)V
    move-object v1, p1
    move v2, p2
    move v3, p3
    move-object v4, p4
    invoke-static {}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getWeight()F
    move-result v5
    invoke-virtual/range {v0 .. v5}, Lcom/oplus/graphics/OplusCanvas;->drawSmoothRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Paint;F)V
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :fallback
    :fallback
    move-exception v0
    invoke-virtual {p0, p1, p2, p3, p4}, Landroid/graphics/Canvas;->drawRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V
    return-void
.end method

.method public static drawRoundRect(Landroid/graphics/Canvas;FFFFFFLandroid/graphics/Paint;)V
    .locals 2
    new-instance v0, Landroid/graphics/RectF;
    invoke-direct {v0, p1, p2, p3, p4}, Landroid/graphics/RectF;-><init>(FFFF)V
    invoke-static {p0, v0, p5, p6, p7}, Lcom/tencent/wetype/monet/ColorOSV2Round;->drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V
    return-void
.end method

.method public static addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V
    .locals 4
    :try_start
    invoke-static {}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getCornerType()I
    move-result v0
    new-instance v1, Lcom/oplus/graphics/OplusPathAdapter;
    invoke-direct {v1, p0, v0}, Lcom/oplus/graphics/OplusPathAdapter;-><init>(Landroid/graphics/Path;I)V
    invoke-virtual {v1, p1, p2, p3, p4}, Lcom/oplus/graphics/OplusPathAdapter;->addSmoothRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :fallback
    :fallback
    move-exception v0
    invoke-virtual {p0, p1, p2, p3, p4}, Landroid/graphics/Path;->addRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Path$Direction;)V
    return-void
.end method

.method public static addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;)V
    .locals 4
    :try_start
    invoke-static {}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getCornerType()I
    move-result v0
    new-instance v1, Lcom/oplus/graphics/OplusPathAdapter;
    invoke-direct {v1, p0, v0}, Lcom/oplus/graphics/OplusPathAdapter;-><init>(Landroid/graphics/Path;I)V
    invoke-static {}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getWeight()F
    move-result v2
    invoke-virtual {v1, p1, p2, p3, v2}, Lcom/oplus/graphics/OplusPathAdapter;->addSmoothRoundRect(Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;F)V
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :fallback
    :fallback
    move-exception v0
    invoke-virtual {p0, p1, p2, p3}, Landroid/graphics/Path;->addRoundRect(Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;)V
    return-void
.end method

.method public static addRoundRect(Landroid/graphics/Path;FFFF[FLandroid/graphics/Path$Direction;)V
    .locals 2
    new-instance v0, Landroid/graphics/RectF;
    invoke-direct {v0, p1, p2, p3, p4}, Landroid/graphics/RectF;-><init>(FFFF)V
    invoke-static {p0, v0, p5, p6}, Lcom/tencent/wetype/monet/ColorOSV2Round;->addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;)V
    return-void
.end method

.method private static uniformRadius(Landroid/graphics/drawable/GradientDrawable;)F
    .locals 8
    invoke-virtual {p0}, Landroid/graphics/drawable/GradientDrawable;->getCornerRadius()F
    move-result v0
    const/4 v1, 0x0
    cmpl-float v2, v0, v1
    if-lez v2, :array
    invoke-virtual {p0, v1}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V
    return v0

    :array
    invoke-virtual {p0}, Landroid/graphics/drawable/GradientDrawable;->getCornerRadii()[F
    move-result-object v3
    if-eqz v3, :none
    array-length v4, v3
    const/4 v5, 0x2
    if-lt v4, v5, :none
    const/4 v5, 0x0
    aget v0, v3, v5
    cmpl-float v6, v0, v1
    if-lez v6, :none
    const/4 v5, 0x1
    :loop
    if-ge v5, v4, :uniform
    aget v6, v3, v5
    sub-float/2addr v6, v0
    invoke-static {v6}, Ljava/lang/Math;->abs(F)F
    move-result v6
    const/high16 v7, 0x3e800000    # 0.25f
    cmpl-float v6, v6, v7
    if-gtz v6, :none
    add-int/lit8 v5, v5, 0x1
    goto :loop

    :uniform
    new-array v5, v4, [F
    invoke-virtual {p0, v5}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadii([F)V
    return v0

    :none
    return v1
.end method

.method private static flattenRadius(Landroid/graphics/drawable/Drawable;)F
    .locals 8
    if-eqz p0, :none

    instance-of v0, p0, Landroid/graphics/drawable/GradientDrawable;
    if-eqz v0, :state
    check-cast p0, Landroid/graphics/drawable/GradientDrawable;
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->uniformRadius(Landroid/graphics/drawable/GradientDrawable;)F
    move-result v0
    return v0

    :state
    instance-of v0, p0, Landroid/graphics/drawable/StateListDrawable;
    if-eqz v0, :layer
    check-cast p0, Landroid/graphics/drawable/StateListDrawable;
    invoke-virtual {p0}, Landroid/graphics/drawable/StateListDrawable;->getStateCount()I
    move-result v1
    const/4 v2, 0x0
    const/4 v3, 0x0
    :state_loop
    if-ge v2, v1, :return_max
    invoke-virtual {p0, v2}, Landroid/graphics/drawable/StateListDrawable;->getStateDrawable(I)Landroid/graphics/drawable/Drawable;
    move-result-object v4
    invoke-static {v4}, Lcom/tencent/wetype/monet/ColorOSV2Round;->flattenRadius(Landroid/graphics/drawable/Drawable;)F
    move-result v5
    cmpl-float v6, v5, v3
    if-lez v6, :state_next
    move v3, v5
    :state_next
    add-int/lit8 v2, v2, 0x1
    goto :state_loop

    :layer
    instance-of v0, p0, Landroid/graphics/drawable/LayerDrawable;
    if-eqz v0, :inset
    check-cast p0, Landroid/graphics/drawable/LayerDrawable;
    invoke-virtual {p0}, Landroid/graphics/drawable/LayerDrawable;->getNumberOfLayers()I
    move-result v1
    const/4 v2, 0x0
    const/4 v3, 0x0
    :layer_loop
    if-ge v2, v1, :return_max
    invoke-virtual {p0, v2}, Landroid/graphics/drawable/LayerDrawable;->getDrawable(I)Landroid/graphics/drawable/Drawable;
    move-result-object v4
    invoke-static {v4}, Lcom/tencent/wetype/monet/ColorOSV2Round;->flattenRadius(Landroid/graphics/drawable/Drawable;)F
    move-result v5
    cmpl-float v6, v5, v3
    if-lez v6, :layer_next
    move v3, v5
    :layer_next
    add-int/lit8 v2, v2, 0x1
    goto :layer_loop

    :inset
    instance-of v0, p0, Landroid/graphics/drawable/InsetDrawable;
    if-eqz v0, :scale
    check-cast p0, Landroid/graphics/drawable/InsetDrawable;
    invoke-virtual {p0}, Landroid/graphics/drawable/InsetDrawable;->getDrawable()Landroid/graphics/drawable/Drawable;
    move-result-object v0
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->flattenRadius(Landroid/graphics/drawable/Drawable;)F
    move-result v0
    return v0

    :scale
    instance-of v0, p0, Landroid/graphics/drawable/ScaleDrawable;
    if-eqz v0, :none
    check-cast p0, Landroid/graphics/drawable/ScaleDrawable;
    invoke-virtual {p0}, Landroid/graphics/drawable/ScaleDrawable;->getDrawable()Landroid/graphics/drawable/Drawable;
    move-result-object v0
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->flattenRadius(Landroid/graphics/drawable/Drawable;)F
    move-result v0
    return v0

    :return_max
    return v3

    :none
    const/4 v0, 0x0
    return v0
.end method

.method private static applyView(Landroid/view/View;)V
    .locals 7
    invoke-virtual {p0}, Landroid/view/View;->getBackground()Landroid/graphics/drawable/Drawable;
    move-result-object v0
    if-eqz v0, :return
    :try_start
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->flattenRadius(Landroid/graphics/drawable/Drawable;)F
    move-result v1
    const/4 v2, 0x0
    cmpl-float v2, v1, v2
    if-lez v2, :return
    invoke-static {}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getWeight()F
    move-result v3
    invoke-static {}, Lcom/tencent/wetype/monet/ColorOSV2Round;->getCornerType()I
    move-result v4
    new-instance v5, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;
    invoke-direct {v5, v1, v3, v4}, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;-><init>(FFI)V
    invoke-virtual {p0, v5}, Landroid/view/View;->setOutlineProvider(Landroid/view/ViewOutlineProvider;)V
    const/4 v6, 0x1
    invoke-virtual {p0, v6}, Landroid/view/View;->setClipToOutline(Z)V
    invoke-virtual {p0}, Landroid/view/View;->invalidateOutline()V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    goto :return
    :catch
    move-exception v0
    :return
    return-void
.end method

.method public static applyTree(Landroid/view/View;)V
    .locals 4
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyView(Landroid/view/View;)V
    invoke-static {p0}, Lcom/tencent/wetype/monet/SystemFontBridge;->applyView(Landroid/view/View;)V
    instance-of v0, p0, Landroid/view/ViewGroup;
    if-eqz v0, :return
    check-cast p0, Landroid/view/ViewGroup;
    invoke-virtual {p0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v0
    const/4 v1, 0x0
    :loop
    if-ge v1, v0, :return
    invoke-virtual {p0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v2
    invoke-static {v2}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyTree(Landroid/view/View;)V
    add-int/lit8 v1, v1, 0x1
    goto :loop
    :return
    return-void
.end method

.method public static install(Landroid/view/View;)V
    .locals 4
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyTree(Landroid/view/View;)V
    sget-object v0, Lcom/tencent/wetype/monet/ColorOSV2Round;->installed:Ljava/util/WeakHashMap;
    invoke-virtual {v0, p0}, Ljava/util/WeakHashMap;->containsKey(Ljava/lang/Object;)Z
    move-result v1
    if-nez v1, :return
    sget-object v1, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;
    invoke-virtual {v0, p0, v1}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    invoke-virtual {p0}, Landroid/view/View;->getViewTreeObserver()Landroid/view/ViewTreeObserver;
    move-result-object v2
    new-instance v3, Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;
    invoke-direct {v3, p0}, Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;-><init>(Landroid/view/View;)V
    invoke-virtual {v2, v3}, Landroid/view/ViewTreeObserver;->addOnGlobalLayoutListener(Landroid/view/ViewTreeObserver$OnGlobalLayoutListener;)V
    const-string v0, "WeTypeOplusRoundV2"
    const-string v1, "installed ColorOS G2/V2 smooth-corner tree adapter"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    :return
    return-void
.end method
'''

OUTLINE_PROVIDER_SMALI = r'''.class final Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;
.super Landroid/view/ViewOutlineProvider;

.field private final radius:F
.field private final weight:F
.field private final cornerType:I

.method constructor <init>(FFI)V
    .locals 0
    invoke-direct {p0}, Landroid/view/ViewOutlineProvider;-><init>()V
    iput p1, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;->radius:F
    iput p2, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;->weight:F
    iput p3, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;->cornerType:I
    return-void
.end method

.method public getOutline(Landroid/view/View;Landroid/graphics/Outline;)V
    .locals 8
    invoke-virtual {p1}, Landroid/view/View;->getWidth()I
    move-result v0
    invoke-virtual {p1}, Landroid/view/View;->getHeight()I
    move-result v1
    if-lez v0, :return
    if-lez v1, :return
    iget v2, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;->radius:F
    iget v3, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;->weight:F
    iget v4, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$OutlineProvider;->cornerType:I
    :try_start
    new-instance v5, Lcom/oplus/graphics/OplusOutlineAdapter;
    invoke-direct {v5, p2, v4}, Lcom/oplus/graphics/OplusOutlineAdapter;-><init>(Landroid/graphics/Outline;I)V
    new-instance v6, Landroid/graphics/Rect;
    const/4 v7, 0x0
    invoke-direct {v6, v7, v7, v0, v1}, Landroid/graphics/Rect;-><init>(IIII)V
    invoke-virtual {v5, v6, v2, v3}, Lcom/oplus/graphics/OplusOutlineAdapter;->setSmoothRoundRect(Landroid/graphics/Rect;FF)V
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :fallback
    :fallback
    move-exception v5
    new-instance v6, Landroid/graphics/Rect;
    const/4 v7, 0x0
    invoke-direct {v6, v7, v7, v0, v1}, Landroid/graphics/Rect;-><init>(IIII)V
    invoke-virtual {p2, v6, v2}, Landroid/graphics/Outline;->setRoundRect(Landroid/graphics/Rect;F)V
    :return
    return-void
.end method
'''

GLOBAL_LAYOUT_SMALI = r'''.class final Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;
.super Ljava/lang/Object;
.implements Landroid/view/ViewTreeObserver$OnGlobalLayoutListener;

.field private final root:Landroid/view/View;

.method constructor <init>(Landroid/view/View;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;->root:Landroid/view/View;
    return-void
.end method

.method public onGlobalLayout()V
    .locals 1
    iget-object v0, p0, Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;->root:Landroid/view/View;
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyTree(Landroid/view/View;)V
    return-void
.end method
'''

SYSTEM_FONT_SMALI = r'''.class public final Lcom/tencent/wetype/monet/SystemFontBridge;
.super Ljava/lang/Object;

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static getDefault()Landroid/graphics/Typeface;
    .locals 1
    sget-object v0, Landroid/graphics/Typeface;->DEFAULT:Landroid/graphics/Typeface;
    return-object v0
.end method

.method public static applyView(Landroid/view/View;)V
    .locals 4
    instance-of v0, p0, Landroid/widget/TextView;
    if-eqz v0, :return
    check-cast p0, Landroid/widget/TextView;
    invoke-virtual {p0}, Landroid/widget/TextView;->getTypeface()Landroid/graphics/Typeface;
    move-result-object v1
    const/4 v2, 0x0
    if-eqz v1, :have_style
    invoke-virtual {v1}, Landroid/graphics/Typeface;->getStyle()I
    move-result v2
    :have_style
    invoke-static {v2}, Landroid/graphics/Typeface;->defaultFromStyle(I)Landroid/graphics/Typeface;
    move-result-object v3
    invoke-virtual {p0, v3}, Landroid/widget/TextView;->setTypeface(Landroid/graphics/Typeface;)V
    :return
    return-void
.end method
'''


def _iter_smali_roots(decompile_dir: Path) -> list[Path]:
    return sorted(
        [p for p in Path(decompile_dir).iterdir() if p.is_dir() and p.name.startswith("smali")],
        key=lambda p: (p.name != "smali", p.name),
    )


def _is_visual_scope(path: Path) -> bool:
    normalized = "/" + path.as_posix().lstrip("/")
    return any(scope in normalized for scope in IME_VISUAL_SCOPES)


def _patch_round_invocations(content: str) -> tuple[str, int]:
    count = 0
    for old, new in ROUND_CALLS.items():
        pattern = re.compile(
            r"(?m)^(?P<indent>\s*)invoke-virtual(?P<range>/range)?\s+(?P<regs>\{[^\n]+\}),\s*"
            + re.escape(old)
            + r"\s*$"
        )

        def repl(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            suffix = match.group("range") or ""
            return (
                f"{match.group('indent')}invoke-static{suffix} "
                f"{match.group('regs')}, {new}"
            )

        content = pattern.sub(repl, content)
    return content, count


_FONT_FACTORY_PATTERN = re.compile(
    r"(?m)^(?P<indent>\s*)invoke-static(?:/range)?\s+\{[^\n]+\},\s*"
    r"Landroid/graphics/Typeface;->createFrom(?:Asset|File)\([^\n]+\)Landroid/graphics/Typeface;\s*\n"
    r"(?P=indent)move-result-object\s+(?P<dest>[vp]\d+)\s*$"
)

_WX_FONT_PATTERN = re.compile(
    r"(?m)^(?P<indent>\s*)invoke-static(?:/range)?\s+\{[^\n]+\},\s*"
    r"Lcom/tencent/wetype/plugin/hld/utils/WxImeUtil;->t0\(Ljava/lang/String;\)Landroid/graphics/Typeface;\s*\n"
    r"(?P=indent)move-result-object\s+(?P<dest>[vp]\d+)\s*$"
)


def _patch_font_factories(content: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return (
            f"{match.group('indent')}sget-object {match.group('dest')}, "
            "Landroid/graphics/Typeface;->DEFAULT:Landroid/graphics/Typeface;"
        )

    content = _FONT_FACTORY_PATTERN.sub(repl, content)
    content = _WX_FONT_PATTERN.sub(repl, content)
    return content, count


def patch_keyboard_smali(decompile_dir: Path) -> dict[str, object]:
    changed_files: list[str] = []
    round_calls = 0
    font_factories = 0

    for root in _iter_smali_roots(decompile_dir):
        for path in root.rglob("*.smali"):
            if not _is_visual_scope(path):
                continue
            content = path.read_text(encoding="utf-8")
            patched, round_count = _patch_round_invocations(content)
            patched, font_count = _patch_font_factories(patched)
            if patched != content:
                path.write_text(patched, encoding="utf-8")
                changed_files.append(str(path.relative_to(decompile_dir)))
            round_calls += round_count
            font_factories += font_count

    if round_calls == 0:
        raise RuntimeError("No keyboard/candidate round-rect draw calls were converted to ColorOS G2/V2")
    if font_factories == 0:
        raise RuntimeError("No keyboard bundled-font factories were replaced with the system default")

    return {
        "round_calls_rewritten": round_calls,
        "bundled_font_factories_rewritten": font_factories,
        "changed_files": sorted(changed_files),
    }


def _helper_root(decompile_dir: Path, patch_report: dict[str, object]) -> Path:
    smali = patch_report.get("smali")
    if not isinstance(smali, dict):
        raise RuntimeError("Oplus patch report has no smali section")
    helper = smali.get("helper_file")
    if not isinstance(helper, str) or not helper:
        raise RuntimeError("Oplus patch report has no helper_file")
    helper_path = Path(decompile_dir) / helper
    for parent in helper_path.parents:
        if parent.parent == Path(decompile_dir) and parent.name.startswith("smali"):
            return parent
    raise RuntimeError(f"Could not resolve smali root for {helper_path}")


def _patch_apply_runnable(decompile_dir: Path, patch_report: dict[str, object]) -> str:
    smali = patch_report.get("smali")
    assert isinstance(smali, dict)
    helper = smali.get("helper_file")
    assert isinstance(helper, str)
    helper_path = Path(decompile_dir) / helper
    runnable = helper_path.with_name("OplusKeyboardBlur$ApplyRunnable.smali")
    if not runnable.is_file():
        raise RuntimeError(f"Missing v2 apply runnable: {runnable}")
    content = runnable.read_text(encoding="utf-8")
    call = (
        "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;"
        "->install(Landroid/view/View;)V\n"
    )
    if call.strip() not in content:
        anchor = (
            "    invoke-static {v0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;"
            "->applyNow(Landroid/view/View;)V\n"
        )
        if anchor not in content:
            raise RuntimeError("Could not find OplusKeyboardBlur.applyNow() call in v2 runnable")
        content = content.replace(anchor, anchor + call, 1)
        runnable.write_text(content, encoding="utf-8")
    return str(runnable.relative_to(decompile_dir))


def apply_coloros_v2_visual_profile(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)

    # Rewrite existing app code first so our own fallback drawRoundRect calls
    # are not accidentally transformed into recursive helper calls.
    patch_result = patch_keyboard_smali(decompile_dir)

    root = _helper_root(decompile_dir, patch_report)
    files = {
        ROUND_RELATIVE_PATH: ROUND_HELPER_SMALI,
        OUTLINE_RELATIVE_PATH: OUTLINE_PROVIDER_SMALI,
        LAYOUT_RELATIVE_PATH: GLOBAL_LAYOUT_SMALI,
        FONT_RELATIVE_PATH: SYSTEM_FONT_SMALI,
    }
    injected: list[str] = []
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        injected.append(str(path.relative_to(decompile_dir)))

    runnable = _patch_apply_runnable(decompile_dir, patch_report)

    return {
        "strategy": "ColorOS 17 SystemUI G2/V2 smooth corners + default system font",
        "system_apis": [
            "OplusSmoothRoundedManager.getG2CornerType",
            "OplusSmoothRoundedManager.getDefaultG2Weight",
            "OplusCanvas.drawSmoothRoundRect",
            "OplusPathAdapter.addSmoothRoundRect",
            "OplusOutlineAdapter.setSmoothRoundRect",
        ],
        "runtime_background_policy": (
            "uniform rounded GradientDrawable/StateList/Layer/Inset/Scale backgrounds are flattened "
            "and clipped by a ColorOS G2/V2 OplusOutlineAdapter; asymmetric corners are preserved"
        ),
        "font_policy": (
            "IME tree TextViews use Typeface.defaultFromStyle; keyboard/symbol createFromAsset/createFromFile "
            "factories are replaced with Typeface.DEFAULT"
        ),
        "smali_rewrites": patch_result,
        "injected_helpers": injected,
        "runnable": runnable,
    }
