#!/usr/bin/env python3
"""V13: ColorOS local blur using the verified Oplus ViewRootManager path.

V12 copied WeType Tool's hidden-framework reflection path verbatim. That path is
appropriate inside its LSPosed/Xposed module process, but real-device feedback
from the repacked standalone WeType APK showed the exact fail-open symptom:
bubble/floating surfaces became translucent while no BackgroundBlurDrawable
was produced. V13 keeps the *hook points and carrier hierarchy* proven by
WeType Tool, while replacing only the privileged hidden-API factory with the
ColorOS ViewRootManager path already verified on the same device for an
ordinary application.

Important invariants:
* no ViewRootImpl/getViewRootImpl/createBackgroundBlurDrawable reflection;
* no local OplusBlurParam/setBlurParams ownership;
* bubble install occurs only after floatview.u.v() finishes addView ->
  setBackgroundColor(0) -> N();
* bubble paint is translucent only after a local blur drawable was actually
  installed. Failure is opaque, never "transparent without blur";
* floating background stripping is transactional: it happens only after the
  carrier owns a non-null ColorOS blur drawable. A failed install removes the
  carrier/highlight and preserves every original background;
* floating still uses WeType Tool's carrier/highlight sibling topology and
  attach/detach lifetime; no setAlpha/window-visibility/global-layout loop;
* voice remains V11's stable single-root material implementation.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

try:
    import oplus_visual_v12 as v12
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v12.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v12", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V12 pass: {_P}")
    v12 = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(v12)

# V12 itself is NOT executed with its original helper. We reuse only its exact
# current-WeType hook-point patchers and replace all runtime local-blur pieces.
base = v12.base

FLOAT_BASE_CLASS = v12.FLOAT_BASE_CLASS
FLOATING_CONTENT_CLASS = v12.FLOATING_CONTENT_CLASS
VOICE_CLASS = v12.VOICE_CLASS
BUBBLE_METHOD_SIGNATURE = v12.BUBBLE_METHOD_SIGNATURE

LOCAL_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;"
LOCAL_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2LocalBlurV13.smali")

# Keep V11's opaque resources. The self-draw bubble fill is lowered at runtime
# only when ColorOSV2LocalBlurV13.hasBubbleBlur(view) is true.
V13_KEY_PREVIEW_COLORS = {
    "ime_skin_key_float_view_upper_bg_color": "#FFFFFFFF",
    "ime_skin_dark_key_float_view_upper_bg_color": "#FF2C2C2E",
    "ime_skin_key_float_view_long_click_bg_color": "#FFFFFFFF",
    "ime_skin_dark_key_float_view_long_click_bg_color": "#FF2C2C2E",
    "ime_skin_key_float_view_click_color": "#22000000",
    "ime_skin_dark_key_float_view_click_color": "#2EFFFFFF",
}

# Bubble: custom outline/path owns geometry, so the BackgroundBlurDrawable is
# left rectangular and clipped by the existing ViewOutlineProvider. Floating:
# 14 dp all corners matches the decoded Oplus floating-keyboard geometry.
BUBBLE_FILL_ALPHA = 0x5A
FLOATING_CORNER_DP = 14.0


LOCAL_HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeOplusLocalV13"
.field private static final bubbleActive:Ljava/util/WeakHashMap;
.field private static final floatingStates:Ljava/util/WeakHashMap;

.method static constructor <clinit>()V
    .locals 2
    new-instance v0, Ljava/util/WeakHashMap;
    invoke-direct {v0}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v0, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->bubbleActive:Ljava/util/WeakHashMap;
    new-instance v1, Ljava/util/WeakHashMap;
    invoke-direct {v1}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v1, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->floatingStates:Ljava/util/WeakHashMap;
    return-void
.end method

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method private static isNight(Landroid/view/View;)Z
    .locals 2
    invoke-virtual {p0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
    move-result-object v0
    iget v0, v0, Landroid/content/res/Configuration;->uiMode:I
    and-int/lit8 v0, v0, 0x30
    const/16 v1, 0x20
    if-ne v0, v1, :light
    const/4 v0, 0x1
    return v0
    :light
    const/4 v0, 0x0
    return v0
.end method

.method private static bubbleTint(Landroid/view/View;)I
    .locals 1
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->isNight(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :light
    const v0, 0x302c2c2e
    return v0
    :light
    const v0, 0x28ffffff
    return v0
.end method

.method private static floatingTint(Landroid/view/View;)I
    .locals 1
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->isNight(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :light
    const v0, 0x38000000
    return v0
    :light
    const v0, 0x30ffffff
    return v0
.end method

.method private static dp(Landroid/view/View;F)F
    .locals 1
    invoke-virtual {p0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v0
    iget v0, v0, Landroid/util/DisplayMetrics;->density:F
    mul-float/2addr p1, v0
    return p1
.end method

# The only local blur factory in V13. It uses ColorOS's public-to-app private
# extension path that the probe and main IME root already proved usable without
# platform signature. No hidden ViewRootImpl reflection and no setBlurParams.
.method private static createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;
    .locals 4
    if-eqz p0, :fail
    invoke-virtual {p0}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v0
    if-eqz v0, :fail
    :try_start
    new-instance v0, Lcom/oplus/view/ViewRootManager;
    invoke-direct {v0, p0}, Lcom/oplus/view/ViewRootManager;-><init>(Landroid/view/View;)V
    invoke-virtual {v0}, Lcom/oplus/view/ViewRootManager;->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;
    move-result-object v1
    if-eqz v1, :fail_try
    invoke-virtual {v0, p1}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V
    invoke-virtual {v0, p2, p3, p4, p5}, Lcom/oplus/view/ViewRootManager;->setCornerRadius(FFFF)V
    const/16 v2, 0xff
    invoke-virtual {v1, v2}, Landroid/graphics/drawable/Drawable;->setAlpha(I)V
    return-object v1
    :fail_try
    const/4 v1, 0x0
    return-object v1
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    :catch
    move-exception v0
    const-string v1, "WeTypeOplusLocalV13"
    const-string v2, "createLocalBlur failed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    :fail
    const/4 v0, 0x0
    return-object v0
.end method

.method public static hasBubbleBlur(Landroid/view/View;)Z
    .locals 2
    if-eqz p0, :no
    sget-object v0, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->bubbleActive:Ljava/util/WeakHashMap;
    invoke-virtual {v0, p0}, Ljava/util/WeakHashMap;->containsKey(Ljava/lang/Object;)Z
    move-result v1
    return v1
    :no
    const/4 v0, 0x0
    return v0
.end method

.method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V
    .locals 1
    if-eqz p1, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->hasBubbleBlur(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :opaque
    const/16 v0, 0x5a
    invoke-virtual {p1, v0}, Landroid/graphics/Paint;->setAlpha(I)V
    return-void
    :opaque
    const/16 v0, 0xff
    invoke-virtual {p1, v0}, Landroid/graphics/Paint;->setAlpha(I)V
    :return
    return-void
.end method

.method public static restoreBubbleStroke(Landroid/graphics/Paint;)V
    .locals 1
    if-eqz p0, :return
    const/16 v0, 0xff
    invoke-virtual {p0, v0}, Landroid/graphics/Paint;->setAlpha(I)V
    :return
    return-void
.end method

.method public static installBubble(Landroid/view/View;)V
    .locals 7
    if-eqz p0, :return
    sget-object v0, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->bubbleActive:Ljava/util/WeakHashMap;
    invoke-virtual {v0, p0}, Ljava/util/WeakHashMap;->remove(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v1
    :try_start
    const/16 v1, 0x64
    const/4 v2, 0x0
    const/4 v3, 0x0
    const/4 v4, 0x0
    const/4 v5, 0x0
    invoke-static {p0, v1, v2, v3, v4, v5}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;
    move-result-object v6
    if-eqz v6, :fallback
    invoke-virtual {p0, v6}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V
    const/4 v1, 0x1
    invoke-virtual {p0, v1}, Landroid/view/View;->setClipToOutline(Z)V
    sget-object v2, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;
    invoke-virtual {v0, p0, v2}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    invoke-virtual {p0}, Landroid/view/View;->invalidate()V
    return-void
    :fallback
    const/4 v1, 0x0
    invoke-virtual {p0, v1}, Landroid/view/View;->setBackgroundColor(I)V
    invoke-virtual {p0}, Landroid/view/View;->invalidate()V
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    :catch
    move-exception v0
    const-string v1, "WeTypeOplusLocalV13"
    const-string v2, "installBubble failed closed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    :return
    return-void
.end method

# Only clear ViewGroup backgrounds. Key/text/icon leaf drawables stay intact.
.method private static stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V
    .locals 6
    if-eqz p0, :return
    instance-of v0, p0, Landroid/view/ViewGroup;
    if-eqz v0, :return
    invoke-virtual {p0}, Landroid/view/View;->getTag()Ljava/lang/Object;
    move-result-object v0
    instance-of v1, v0, Ljava/lang/String;
    if-eqz v1, :strip
    check-cast v0, Ljava/lang/String;
    const-string v1, "WeTypeBlurCarrier_Float"
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v2
    if-nez v2, :return
    const-string v1, "WeTypeBlurHighlight_Float"
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v2
    if-nez v2, :return
    :strip
    invoke-virtual {p0}, Landroid/view/View;->getBackground()Landroid/graphics/drawable/Drawable;
    move-result-object v0
    if-eqz v0, :children
    invoke-virtual {p1, p0, v0}, Ljava/util/IdentityHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    const/4 v1, 0x0
    invoke-virtual {p0, v1}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V
    :children
    check-cast p0, Landroid/view/ViewGroup;
    invoke-virtual {p0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v1
    const/4 v2, 0x0
    :loop
    if-ge v2, v1, :return
    invoke-virtual {p0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v3
    invoke-static {v3, p1}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :return
    return-void
.end method

.method private static restoreBackgrounds(Ljava/util/IdentityHashMap;)V
    .locals 5
    if-eqz p0, :return
    invoke-virtual {p0}, Ljava/util/IdentityHashMap;->entrySet()Ljava/util/Set;
    move-result-object v0
    invoke-interface {v0}, Ljava/util/Set;->iterator()Ljava/util/Iterator;
    move-result-object v1
    :loop
    invoke-interface {v1}, Ljava/util/Iterator;->hasNext()Z
    move-result v2
    if-eqz v2, :done
    invoke-interface {v1}, Ljava/util/Iterator;->next()Ljava/lang/Object;
    move-result-object v2
    check-cast v2, Ljava/util/Map$Entry;
    invoke-interface {v2}, Ljava/util/Map$Entry;->getKey()Ljava/lang/Object;
    move-result-object v3
    check-cast v3, Landroid/view/View;
    invoke-interface {v2}, Ljava/util/Map$Entry;->getValue()Ljava/lang/Object;
    move-result-object v4
    check-cast v4, Landroid/graphics/drawable/Drawable;
    invoke-virtual {v3, v4}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V
    goto :loop
    :done
    invoke-virtual {p0}, Ljava/util/IdentityHashMap;->clear()V
    :return
    return-void
.end method

.method private static removeIfParented(Landroid/view/View;)V
    .locals 2
    if-eqz p0, :return
    invoke-virtual {p0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    instance-of v1, v0, Landroid/view/ViewGroup;
    if-eqz v1, :return
    check-cast v0, Landroid/view/ViewGroup;
    invoke-virtual {v0, p0}, Landroid/view/ViewGroup;->removeView(Landroid/view/View;)V
    :return
    return-void
.end method

.method public static installFloating(Landroid/view/View;)V
    .locals 14
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->restoreFloating(Landroid/view/View;)V
    invoke-virtual {p0}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v0
    if-eqz v0, :return
    :try_start
    move-object v0, p0
    check-cast v0, Lcom/tencent/wetype/plugin/hld/float/e;
    invoke-virtual {v0}, Lcom/tencent/wetype/plugin/hld/float/e;->getRootView()Lcom/tencent/wetype/plugin/hld/view/ImeRadiusConstraintLayout;
    move-result-object v1
    if-eqz v1, :return_try
    invoke-virtual {v1}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v2
    instance-of v3, v2, Landroid/view/ViewGroup;
    if-eqz v3, :return_try
    check-cast v2, Landroid/view/ViewGroup;

    # Tool-parity sibling carrier/highlight topology.
    new-instance v3, Landroid/view/View;
    invoke-virtual {p0}, Landroid/view/View;->getContext()Landroid/content/Context;
    move-result-object v4
    invoke-direct {v3, v4}, Landroid/view/View;-><init>(Landroid/content/Context;)V
    const-string v5, "WeTypeBlurCarrier_Float"
    invoke-virtual {v3, v5}, Landroid/view/View;->setTag(Ljava/lang/Object;)V
    const/4 v5, 0x0
    invoke-virtual {v3, v5}, Landroid/view/View;->setClickable(Z)V
    invoke-virtual {v3, v5}, Landroid/view/View;->setFocusable(Z)V
    const/4 v6, 0x2
    invoke-virtual {v3, v6}, Landroid/view/View;->setImportantForAccessibility(I)V
    invoke-virtual {v1}, Landroid/view/View;->getLayoutParams()Landroid/view/ViewGroup$LayoutParams;
    move-result-object v7
    invoke-virtual {v2, v3, v5, v7}, Landroid/view/ViewGroup;->addView(Landroid/view/View;ILandroid/view/ViewGroup$LayoutParams;)V

    # IMPORTANT: source the drawable from the already-attached floating root,
    # exactly like Tool does. Do not ask the newly-created carrier to establish
    # its own ViewRoot and do not strip anything until this succeeds.
    const/16 v7, 0x96
    const/high16 v8, 0x41600000    # 14.0f
    invoke-static {p0, v8}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->dp(Landroid/view/View;F)F
    move-result v8
    invoke-static {p0, v7, v8, v8, v8, v8}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;IFFFF)Landroid/graphics/drawable/Drawable;
    move-result-object v9
    if-eqz v9, :rollback_carrier
    invoke-virtual {v3, v9}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    new-instance v10, Landroid/view/View;
    invoke-direct {v10, v4}, Landroid/view/View;-><init>(Landroid/content/Context;)V
    const-string v11, "WeTypeBlurHighlight_Float"
    invoke-virtual {v10, v11}, Landroid/view/View;->setTag(Ljava/lang/Object;)V
    invoke-virtual {v10, v5}, Landroid/view/View;->setClickable(Z)V
    invoke-virtual {v10, v5}, Landroid/view/View;->setFocusable(Z)V
    invoke-virtual {v10, v6}, Landroid/view/View;->setImportantForAccessibility(I)V
    invoke-virtual {v1}, Landroid/view/View;->getLayoutParams()Landroid/view/ViewGroup$LayoutParams;
    move-result-object v6
    invoke-virtual {v2, v10, v6}, Landroid/view/ViewGroup;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V

    # Light 1dp outline only; no second blur owner.
    new-instance v6, Landroid/graphics/drawable/GradientDrawable;
    invoke-direct {v6}, Landroid/graphics/drawable/GradientDrawable;-><init>()V
    const/4 v7, 0x0
    invoke-virtual {v6, v7}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V
    const/high16 v7, 0x3f800000    # 1.0f
    invoke-static {p0, v7}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->dp(Landroid/view/View;F)F
    move-result v7
    float-to-int v7, v7
    const v8, 0x24ffffff
    invoke-virtual {v6, v7, v8}, Landroid/graphics/drawable/GradientDrawable;->setStroke(II)V
    const/high16 v7, 0x41600000    # 14.0f
    invoke-static {p0, v7}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->dp(Landroid/view/View;F)F
    move-result v7
    invoke-virtual {v6, v7}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V
    invoke-virtual {v10, v6}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # Blur confirmed. Now and only now remove opaque structural backgrounds.
    new-instance v11, Ljava/util/IdentityHashMap;
    invoke-direct {v11}, Ljava/util/IdentityHashMap;-><init>()V
    invoke-static {v1, v11}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V
    invoke-virtual {v0}, Lcom/tencent/wetype/plugin/hld/float/e;->getContent()Lcom/tencent/wetype/plugin/hld/view/ImeRadiusLinearLayout;
    move-result-object v12
    if-eqz v12, :state
    invoke-static {v12, v11}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V

    :state
    const/4 v12, 0x4
    new-array v12, v12, [Ljava/lang/Object;
    const/4 v13, 0x0
    aput-object v2, v12, v13
    const/4 v13, 0x1
    aput-object v3, v12, v13
    const/4 v13, 0x2
    aput-object v10, v12, v13
    const/4 v13, 0x3
    aput-object v11, v12, v13
    sget-object v13, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->floatingStates:Ljava/util/WeakHashMap;
    invoke-virtual {v13, p0, v12}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    invoke-virtual {p0}, Landroid/view/View;->invalidate()V
    return-void

    :rollback_carrier
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->removeIfParented(Landroid/view/View;)V
    const-string v4, "WeTypeOplusLocalV13"
    const-string v5, "floating blur unavailable; original backgrounds kept"
    invoke-static {v4, v5}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    return-void
    :return_try
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    :catch
    move-exception v0
    const-string v1, "WeTypeOplusLocalV13"
    const-string v2, "installFloating failed; restoring"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->restoreFloating(Landroid/view/View;)V
    :return
    return-void
.end method

.method public static restoreFloating(Landroid/view/View;)V
    .locals 8
    if-eqz p0, :return
    :try_start
    sget-object v0, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->floatingStates:Ljava/util/WeakHashMap;
    invoke-virtual {v0, p0}, Ljava/util/WeakHashMap;->remove(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v1
    if-eqz v1, :return_try
    check-cast v1, [Ljava/lang/Object;
    const/4 v2, 0x3
    aget-object v3, v1, v2
    check-cast v3, Ljava/util/IdentityHashMap;
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->restoreBackgrounds(Ljava/util/IdentityHashMap;)V
    const/4 v2, 0x1
    aget-object v3, v1, v2
    check-cast v3, Landroid/view/View;
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->removeIfParented(Landroid/view/View;)V
    const/4 v2, 0x2
    aget-object v3, v1, v2
    check-cast v3, Landroid/view/View;
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->removeIfParented(Landroid/view/View;)V
    :return_try
    return-void
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    :catch
    move-exception v0
    const-string v1, "WeTypeOplusLocalV13"
    const-string v2, "restoreFloating failed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    :return
    return-void
.end method
'''


def _patch_bubble_fill_fail_closed(decompile_dir: Path) -> dict[str, object]:
    path = v12._find_class_file(decompile_dir, FLOAT_BASE_CLASS)
    if path is None:
        raise RuntimeError(f"Missing WeType float-view base: {FLOAT_BASE_CLASS}")
    content = path.read_text(encoding="utf-8")
    located = v12._method_block(content, "onDraw", "(Landroid/graphics/Canvas;)V")
    if located is None:
        raise RuntimeError("floatview.u.onDraw(Canvas) shape changed")
    start, end = located
    block = content[start:end]

    fill_anchor = re.compile(
        r"(sget v4, Lcom/tencent/wetype/plugin/hld/o;->ime_color_12:I.*?"
        r"invoke-virtual \{v1, v2\}, Landroid/graphics/Paint;->setColor\(I\)V\n)",
        re.DOTALL,
    )
    fill_matches = list(fill_anchor.finditer(block))
    if len(fill_matches) != 1:
        raise RuntimeError(f"Expected one ime_color_12 fill site, got {len(fill_matches)}")
    fill_call = (
        "    # WeTypeOplusV13 bubble fill fail-closed\n"
        f"    invoke-static {{p0, v1}}, {LOCAL_DESCRIPTOR}->applyBubbleFill"
        "(Landroid/view/View;Landroid/graphics/Paint;)V\n"
    )
    match = fill_matches[0]
    block = block[: match.end()] + fill_call + block[match.end() :]

    stroke_anchor = re.compile(
        r"(sget v3, Lcom/tencent/wetype/plugin/hld/o;->ime_color_09:I.*?"
        r"invoke-virtual \{v1, v2\}, Landroid/graphics/Paint;->setColor\(I\)V\n)",
        re.DOTALL,
    )
    stroke_matches = list(stroke_anchor.finditer(block))
    if len(stroke_matches) != 1:
        raise RuntimeError(f"Expected one ime_color_09 stroke site, got {len(stroke_matches)}")
    stroke_call = (
        "    # WeTypeOplusV13 bubble stroke opaque\n"
        f"    invoke-static {{v1}}, {LOCAL_DESCRIPTOR}->restoreBubbleStroke"
        "(Landroid/graphics/Paint;)V\n"
    )
    sm = stroke_matches[0]
    block = block[: sm.end()] + stroke_call + block[sm.end() :]
    path.write_text(content[:start] + block + content[end:], encoding="utf-8")
    return {
        "file": str(path.relative_to(decompile_dir)),
        "fill_policy": "alpha 0x5A only when local ColorOS blur installed; otherwise 0xFF",
        "stroke_policy": "always alpha 0xFF",
    }


def _audit_v13(decompile_dir: Path) -> dict[str, object]:
    root = Path(decompile_dir)
    helper = None
    for smali_root in sorted(root.glob("smali*")):
        candidate = smali_root / LOCAL_RELATIVE_PATH
        if candidate.is_file():
            helper = candidate.read_text(encoding="utf-8")
            break
    if helper is None:
        raise RuntimeError("V13 local helper missing")
    float_path = v12._find_class_file(root, FLOAT_BASE_CLASS)
    floating_path = v12._find_class_file(root, FLOATING_CONTENT_CLASS)
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
        raise RuntimeError("V13 helper contains forbidden hidden/root-global paths: " + ", ".join(present))
    required = (
        "Lcom/oplus/view/ViewRootManager;",
        "->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;",
        "->setBlurRadius(I)V",
        "WeTypeBlurCarrier_Float",
        "WeTypeBlurHighlight_Float",
        "IdentityHashMap",
        "floating blur unavailable; original backgrounds kept",
    )
    missing = [item for item in required if item not in helper]
    if missing:
        raise RuntimeError("V13 helper missing required primitives: " + ", ".join(missing))

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
    if (bubble_calls, fill_calls, stroke_calls, floating_install, floating_restore) != (1, 1, 1, 1, 1):
        raise RuntimeError(
            "V13 hook cardinality mismatch: "
            f"bubble={bubble_calls} fill={fill_calls} stroke={stroke_calls} "
            f"floating={floating_install}/{floating_restore}"
        )
    if "setAlpha(F)V" in fltext or "onWindowVisibilityChanged(I)V" in fltext:
        raise RuntimeError("V13 floating target gained a high-frequency lifecycle hook")

    # Ordering contract is encoded in helper text itself: successful non-null
    # blur is installed onto carrier before stripBackgrounds is invoked.
    set_bg = helper.find("invoke-virtual {v3, v9}, Landroid/view/View;->setBackground")
    strip = helper.find("->stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V")
    rollback = helper.find(":rollback_carrier")
    if min(set_bg, strip, rollback) < 0 or not (set_bg < strip and rollback < strip):
        raise RuntimeError("V13 floating transaction ordering invariant failed")

    return {
        "bubble_post_N_hook": bubble_calls,
        "bubble_fail_closed_fill_hook": fill_calls,
        "floating_attach_detach_hooks": [floating_install, floating_restore],
        "local_viewroot_manager": True,
        "hidden_viewrootimpl_reflection": False,
        "local_oplus_blur_param_owner": False,
        "global_layout_scan_added": False,
        "background_strip_after_blur_success": True,
    }


def apply_coloros_v2_visual_profile_v13(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)

    # Reuse V12's proven exact HLD creation/lifecycle hook patchers, but swap
    # every runtime local-blur primitive before invoking the pipeline.
    old_descriptor = v12.LOCAL_DESCRIPTOR
    old_relative = v12.LOCAL_RELATIVE_PATH
    old_helper = v12.LOCAL_HELPER_SMALI
    old_preview = v12.V12_KEY_PREVIEW_COLORS
    old_fill = v12._patch_bubble_fill_alpha
    old_audit = v12._audit_v12

    v12.LOCAL_DESCRIPTOR = LOCAL_DESCRIPTOR
    v12.LOCAL_RELATIVE_PATH = LOCAL_RELATIVE_PATH
    v12.LOCAL_HELPER_SMALI = LOCAL_HELPER_SMALI
    v12.V12_KEY_PREVIEW_COLORS = dict(V13_KEY_PREVIEW_COLORS)
    v12._patch_bubble_fill_alpha = _patch_bubble_fill_fail_closed
    v12._audit_v12 = _audit_v13
    try:
        result = v12.apply_coloros_v2_visual_profile_v12(decompile_dir, patch_report)
    finally:
        v12.LOCAL_DESCRIPTOR = old_descriptor
        v12.LOCAL_RELATIVE_PATH = old_relative
        v12.LOCAL_HELPER_SMALI = old_helper
        v12.V12_KEY_PREVIEW_COLORS = old_preview
        v12._patch_bubble_fill_alpha = old_fill
        v12._audit_v12 = old_audit

    result["strategy"] = (
        "V11 stable root material + WeType Tool exact bubble/floating hook surfaces + "
        "ColorOS ViewRootManager local BackgroundBlurDrawable (no hidden ViewRootImpl reflection)"
    )
    result["key_preview"]["resource_tints"] = dict(V13_KEY_PREVIEW_COLORS)
    result["key_preview"]["fill_alpha"] = (
        "0x5A only after successful ColorOS local blur; opaque fallback"
    )
    result["floating"]["corner_dp"] = FLOATING_CORNER_DP
    result["performance_contract"] = {
        "root_material_owner": "unchanged OplusKeyboardBlur / OplusBlurParam",
        "local_blur_factory": "ColorOS ViewRootManager on already-attached source view",
        "local_blur_sites": "bubble creation and floating attach only",
        "per_key_viewroot_blur": False,
        "global_layout_scan": False,
        "high_frequency_visibility_or_alpha_hooks": False,
        "background_stripping": "transactional; only after non-null blur drawable",
        "local_setBlurParams": False,
        "voice_local_blur": False,
    }
    result["runtime_audit"] = _audit_v13(decompile_dir)
    result["v12_failure_correction"] = {
        "observed": "translucent bubble/floating surfaces without blur on standalone ColorOS APK",
        "cause_model": (
            "WeType Tool's hidden ViewRootImpl reflection runs under Xposed/LSPosed privileges; "
            "the standalone repack must use the already-proven Oplus ViewRootManager API instead"
        ),
        "fail_closed": True,
    }
    return result
