#!/usr/bin/env python3
"""Upgrade the generated WeType blur helper to the ColorOS 17 keyboard path.

Evidence used by this transform:
- PMA110 / ColorOS 17 probe: ViewRootManager, BackgroundBlurDrawable,
  OplusBlurParam, FAST_KAWASE, smooth-corner and COUI material calls all work
  from an ordinary third-party UID.
- com.oplus.keyboard 15.17.238 DEX: its blur-param factory calls
  setBlurType(2), resolves `bgKeyboardBlur`, builds [1,1,1,1] plus normalized
  RGBA, then calls setMaterialParams(1, factors, rgba),
  setSmoothCornerType(1), setSmoothCornerWeight(3.0f). The keyboard blur
  controller uses top corners ~=28dp, bottom corners 0 and radius 150.

The first WeType experiment could be visually overwritten by its own skin
initialisation. v2 therefore applies to the attached input root using the live
ViewRootImpl and re-asserts the material after short delays.
"""

from __future__ import annotations

from pathlib import Path

HELPER_DESCRIPTOR = "Lcom/tencent/wetype/monet/OplusKeyboardBlur;"
LISTENER_DESCRIPTOR = "Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;"
RUNNABLE_DESCRIPTOR = "Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;"
LISTENER_RELATIVE_PATH = Path("com/tencent/wetype/monet/OplusKeyboardBlur$AttachListener.smali")
RUNNABLE_RELATIVE_PATH = Path("com/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable.smali")

# Fallbacks only. The original ColorOS keyboard resolves bgKeyboardBlur through
# its own theme engine. These values preserve the same material-parameter shape
# and can be tuned after device comparison without changing the call chain.
DARK_TINT = "0x66000000"
LIGHT_TINT = "0x4dffffff"

HELPER_SMALI = rf'''.class public final Lcom/tencent/wetype/monet/OplusKeyboardBlur;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeOplusBlur"

.method private constructor <init>()V
    .locals 0
    invoke-direct {{p0}}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static apply(Landroid/view/View;)V
    .locals 2
    if-eqz p0, :return

    invoke-virtual {{p0}}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v0
    if-eqz v0, :defer

    invoke-static {{p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->schedule(Landroid/view/View;)V
    goto :return

    :defer
    new-instance v0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;
    invoke-direct {{v0, p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;-><init>(Landroid/view/View;)V
    invoke-virtual {{p0, v0}}, Landroid/view/View;->addOnAttachStateChangeListener(Landroid/view/View$OnAttachStateChangeListener;)V

    const-string v0, "WeTypeOplusBlur"
    const-string v1, "waiting for IME attachment (v2)"
    invoke-static {{v0, v1}}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :return
    return-void
.end method

.method public static schedule(Landroid/view/View;)V
    .locals 4
    if-eqz p0, :return

    new-instance v0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;
    invoke-direct {{v0, p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;-><init>(Landroid/view/View;)V
    invoke-virtual {{p0, v0}}, Landroid/view/View;->post(Ljava/lang/Runnable;)Z

    new-instance v0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;
    invoke-direct {{v0, p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;-><init>(Landroid/view/View;)V
    const-wide/16 v1, 0xfa
    invoke-virtual {{p0, v0, v1, v2}}, Landroid/view/View;->postDelayed(Ljava/lang/Runnable;J)Z

    new-instance v0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;
    invoke-direct {{v0, p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;-><init>(Landroid/view/View;)V
    const-wide/16 v1, 0x2bc
    invoke-virtual {{p0, v0, v1, v2}}, Landroid/view/View;->postDelayed(Ljava/lang/Runnable;J)Z

    const-string v0, "WeTypeOplusBlur"
    const-string v3, "scheduled v2 material apply at 0/250/700ms"
    invoke-static {{v0, v3}}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :return
    return-void
.end method

.method private static isNight(Landroid/view/View;)Z
    .locals 2
    invoke-virtual {{p0}}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {{v0}}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
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

.method private static getTint(Landroid/view/View;)I
    .locals 1
    invoke-static {{p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->isNight(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :light
    const v0, {DARK_TINT}
    return v0
    :light
    const v0, {LIGHT_TINT}
    return v0
.end method

.method private static configureMaterial(Lcom/oplus/graphics/OplusBlurParam;I)V
    .locals 10

    const/4 v0, 0x4
    new-array v1, v0, [F
    fill-array-data v1, :factors

    invoke-static {{p1}}, Landroid/graphics/Color;->red(I)I
    move-result v2
    int-to-float v2, v2
    invoke-static {{p1}}, Landroid/graphics/Color;->green(I)I
    move-result v3
    int-to-float v3, v3
    invoke-static {{p1}}, Landroid/graphics/Color;->blue(I)I
    move-result v4
    int-to-float v4, v4
    invoke-static {{p1}}, Landroid/graphics/Color;->alpha(I)I
    move-result v5
    int-to-float v5, v5

    const/high16 v6, 0x437f0000    # 255.0f
    div-float/2addr v2, v6
    div-float/2addr v3, v6
    div-float/2addr v4, v6
    div-float/2addr v5, v6

    new-array v7, v0, [F
    const/4 v8, 0x0
    aput v2, v7, v8
    const/4 v8, 0x1
    aput v3, v7, v8
    const/4 v8, 0x2
    aput v4, v7, v8
    const/4 v8, 0x3
    aput v5, v7, v8

    # Exact material-param selector used by com.oplus.keyboard 15.17.238.
    const/4 v9, 0x1
    invoke-virtual {{p0, v9, v1, v7}}, Lcom/oplus/graphics/OplusBlurParam;->setMaterialParams(I[F[F)V
    return-void

    :factors
    .array-data 4
        0x3f800000
        0x3f800000
        0x3f800000
        0x3f800000
    .end array-data
.end method

.method public static applyNow(Landroid/view/View;)V
    .locals 10
    if-eqz p0, :return

    invoke-virtual {{p0}}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v0
    if-eqz v0, :return

    :try_start
    # Use the actual decor/root to obtain the live ViewRootImpl, but keep the
    # blur drawable on the input view itself. This is the same root/target split
    # supported by COUIBackgroundBlurBuilder.
    invoke-virtual {{p0}}, Landroid/view/View;->getRootView()Landroid/view/View;
    move-result-object v0
    if-nez v0, :have_root
    move-object v0, p0
    :have_root

    new-instance v1, Lcom/oplus/view/ViewRootManager;
    invoke-direct {{v1, v0}}, Lcom/oplus/view/ViewRootManager;-><init>(Landroid/view/View;)V

    invoke-virtual {{v1}}, Lcom/oplus/view/ViewRootManager;->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;
    move-result-object v2
    if-eqz v2, :no_drawable

    # Bind once before configuration so a live target always owns the drawable;
    # bind again after configuration to survive skin/background replacement.
    invoke-virtual {{p0, v2}}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    new-instance v3, Lcom/oplus/graphics/OplusBlurParam;
    invoke-direct {{v3}}, Lcom/oplus/graphics/OplusBlurParam;-><init>()V

    const/4 v4, 0x2
    invoke-virtual {{v3, v4}}, Lcom/oplus/graphics/OplusBlurParam;->setBlurType(I)V

    invoke-static {{p0}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->getTint(Landroid/view/View;)I
    move-result v5
    invoke-static {{v3, v5}}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->configureMaterial(Lcom/oplus/graphics/OplusBlurParam;I)V

    const/4 v4, 0x1
    invoke-virtual {{v3, v4}}, Lcom/oplus/graphics/OplusBlurParam;->setSmoothCornerType(I)V
    const/high16 v6, 0x40400000    # 3.0f
    invoke-virtual {{v3, v6}}, Lcom/oplus/graphics/OplusBlurParam;->setSmoothCornerWeight(F)V

    invoke-virtual {{v1, v3}}, Lcom/oplus/view/ViewRootManager;->setBlurParams(Lcom/oplus/graphics/OplusBlurParam;)V

    invoke-virtual {{p0}}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v7
    invoke-virtual {{v7}}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v7
    iget v8, v7, Landroid/util/DisplayMetrics;->density:F
    const/high16 v9, 0x41e00000    # 28.0f
    mul-float/2addr v9, v8
    const/4 v8, 0x0
    invoke-virtual {{v1, v9, v9, v8, v8}}, Lcom/oplus/view/ViewRootManager;->setCornerRadius(FFFF)V

    const/16 v4, 0x96
    invoke-virtual {{v1, v4}}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V

    const/16 v4, 0xff
    invoke-virtual {{v2, v4}}, Landroid/graphics/drawable/Drawable;->setAlpha(I)V
    invoke-virtual {{p0, v2}}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V
    invoke-virtual {{p0}}, Landroid/view/View;->invalidate()V

    const-string v0, "WeTypeOplusBlur"
    const-string v4, "v2 applied: FAST_KAWASE + material tint + smooth corner + radius150"
    invoke-static {{v0, v4}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    goto :done

    :no_drawable
    const-string v0, "WeTypeOplusBlur"
    const-string v4, "v2 attached root returned null BackgroundBlurDrawable"
    invoke-static {{v0, v4}}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    :done
    :try_end
    .catch Ljava/lang/Throwable; {{:try_start .. :try_end}} :catch
    goto :return

    :catch
    move-exception v0
    const-string v1, "WeTypeOplusBlur"
    const-string v2, "ColorOS keyboard material v2 failed"
    invoke-static {{v1, v2, v0}}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I

    :return
    return-void
.end method
'''

LISTENER_SMALI = r'''.class final Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;
.super Ljava/lang/Object;
.implements Landroid/view/View$OnAttachStateChangeListener;

.field private final target:Landroid/view/View;

.method constructor <init>(Landroid/view/View;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;->target:Landroid/view/View;
    return-void
.end method

.method public onViewAttachedToWindow(Landroid/view/View;)V
    .locals 1
    invoke-virtual {p1, p0}, Landroid/view/View;->removeOnAttachStateChangeListener(Landroid/view/View$OnAttachStateChangeListener;)V
    iget-object v0, p0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;->target:Landroid/view/View;
    invoke-static {v0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->schedule(Landroid/view/View;)V
    return-void
.end method

.method public onViewDetachedFromWindow(Landroid/view/View;)V
    .locals 0
    return-void
.end method
'''

RUNNABLE_SMALI = r'''.class final Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;

.field private final target:Landroid/view/View;

.method constructor <init>(Landroid/view/View;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;->target:Landroid/view/View;
    return-void
.end method

.method public run()V
    .locals 1
    iget-object v0, p0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;->target:Landroid/view/View;
    invoke-static {v0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->applyNow(Landroid/view/View;)V
    return-void
.end method
'''


def upgrade_to_keyboard_material_v2(decompile_dir: Path, patch_report: dict[str, object]) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    smali_report = patch_report.get("smali")
    if not isinstance(smali_report, dict):
        raise RuntimeError("Oplus patch report has no smali section")
    relative = smali_report.get("helper_file")
    if not isinstance(relative, str) or not relative:
        raise RuntimeError("Oplus patch report has no helper_file")

    helper_path = decompile_dir / relative
    if not helper_path.is_file():
        raise RuntimeError(f"Generated Oplus helper missing: {helper_path}")

    smali_root = helper_path.parents[4]
    if smali_root.parent != decompile_dir or not smali_root.name.startswith("smali"):
        raise RuntimeError(f"Could not resolve smali root from helper: {helper_path}")

    listener_path = smali_root / LISTENER_RELATIVE_PATH
    runnable_path = smali_root / RUNNABLE_RELATIVE_PATH
    listener_path.parent.mkdir(parents=True, exist_ok=True)
    runnable_path.parent.mkdir(parents=True, exist_ok=True)

    helper_path.write_text(HELPER_SMALI, encoding="utf-8")
    listener_path.write_text(LISTENER_SMALI, encoding="utf-8")
    runnable_path.write_text(RUNNABLE_SMALI, encoding="utf-8")

    return {
        "strategy": "ViewRootManager(rootView) + BackgroundBlurDrawable(target) + delayed reassert",
        "blur_type": 2,
        "material_params": "setMaterialParams(1, [1,1,1,1], normalized RGBA tint)",
        "smooth_corner_type": 1,
        "smooth_corner_weight": 3.0,
        "blur_radius": 150,
        "corner_radius": "top 28dp / bottom 0dp",
        "dark_tint": DARK_TINT,
        "light_tint": LIGHT_TINT,
        "helper_file": str(helper_path.relative_to(decompile_dir)),
        "listener_file": str(listener_path.relative_to(decompile_dir)),
        "runnable_file": str(runnable_path.relative_to(decompile_dir)),
    }
