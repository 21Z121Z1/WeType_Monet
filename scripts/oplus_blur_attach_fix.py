#!/usr/bin/env python3
"""Make the injected Oplus blur helper attachment-safe.

ViewRootManager needs a live ViewRootImpl. onCreateInputView() runs before the
returned IME view is attached, so invoking the private path immediately would
usually yield a null BackgroundBlurDrawable. This transform keeps the simple
injection point but defers the actual private API call until View attachment.
"""

from __future__ import annotations

from pathlib import Path

HELPER_DESCRIPTOR = "Lcom/tencent/wetype/monet/OplusKeyboardBlur;"
LISTENER_DESCRIPTOR = "Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;"
LISTENER_RELATIVE_PATH = Path("com/tencent/wetype/monet/OplusKeyboardBlur$AttachListener.smali")
ORIGINAL_METHOD = ".method public static apply(Landroid/view/View;)V"
RENAMED_METHOD = ".method public static applyNow(Landroid/view/View;)V"

APPLY_WRAPPER = r'''.method public static apply(Landroid/view/View;)V
    .locals 2

    if-eqz p0, :return

    invoke-virtual {p0}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v0
    if-eqz v0, :defer

    invoke-static {p0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->applyNow(Landroid/view/View;)V
    goto :return

    :defer
    new-instance v0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;
    invoke-direct {v0, p0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur$AttachListener;-><init>(Landroid/view/View;)V
    invoke-virtual {p0, v0}, Landroid/view/View;->addOnAttachStateChangeListener(Landroid/view/View$OnAttachStateChangeListener;)V

    const-string v0, "WeTypeOplusBlur"
    const-string v1, "Waiting for IME view attachment before applying ColorOS private blur"
    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

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
    invoke-static {v0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->applyNow(Landroid/view/View;)V
    return-void
.end method

.method public onViewDetachedFromWindow(Landroid/view/View;)V
    .locals 0
    return-void
.end method
'''


def make_attachment_safe(decompile_dir: Path, patch_report: dict[str, object]) -> dict[str, str]:
    decompile_dir = Path(decompile_dir)
    smali_report = patch_report.get("smali")
    if not isinstance(smali_report, dict):
        raise RuntimeError("Oplus patch report has no smali section")
    relative = smali_report.get("helper_file")
    if not isinstance(relative, str) or not relative:
        raise RuntimeError("Oplus patch report has no helper_file")

    helper_path = decompile_dir / relative
    content = helper_path.read_text(encoding="utf-8")
    if "->applyNow(Landroid/view/View;)V" in content and LISTENER_DESCRIPTOR in content:
        raise RuntimeError("Unexpected already-transformed helper content")
    if content.count(ORIGINAL_METHOD) != 1:
        raise RuntimeError("Expected exactly one OplusKeyboardBlur.apply(View) method")

    content = content.replace(ORIGINAL_METHOD, RENAMED_METHOD, 1)
    marker = RENAMED_METHOD
    marker_index = content.index(marker)
    content = content[:marker_index] + APPLY_WRAPPER + content[marker_index:]
    helper_path.write_text(content, encoding="utf-8")

    smali_root = helper_path.parents[4]
    if smali_root.parent != decompile_dir or not smali_root.name.startswith("smali"):
        raise RuntimeError(f"Could not resolve smali root from helper: {helper_path}")
    listener_path = smali_root / LISTENER_RELATIVE_PATH
    listener_path.parent.mkdir(parents=True, exist_ok=True)
    if listener_path.exists() and listener_path.read_text(encoding="utf-8") != LISTENER_SMALI:
        raise RuntimeError(f"Refusing to overwrite unexpected listener class: {listener_path}")
    listener_path.write_text(LISTENER_SMALI, encoding="utf-8")

    return {
        "strategy": "View.OnAttachStateChangeListener",
        "helper_file": str(helper_path.relative_to(decompile_dir)),
        "listener_file": str(listener_path.relative_to(decompile_dir)),
    }
