#!/usr/bin/env python3
"""V10: layered ColorOS material for key-preview bubbles and voice input.

V9 fixed full replacement-keyboard stacking/restoration. Device feedback still
shows two transient surfaces as plain semi-transparent overlays:

* key press / long-press bubbles are rooted in
  com.tencent.wetype.plugin.hld.floatview.u. That base FrameLayout already owns
  WeType's custom popup outline/path and runs skin initialization from
  onAttachedToWindow().
* voice-to-text is rooted in com.tencent.wetype.plugin.hld.voice.ImeVoiceView.
  It is a full replacement surface but was not part of the V9 overlay set, so
  the base self-draw keyboard can remain visible through its translucent layer.

V10 keeps the low-overhead event-driven architecture. It does not create a
ViewRootManager for every key and does not restore global-layout scanning.
Instead, one local BackgroundBlurDrawable is created only while a transient
float root or the voice root exists. The drawable is layered underneath the
surface's original background, preserving WeType's shape/tint while adding the
same ColorOS compositor blur depth used by the keyboard root.

The helper intentionally does NOT call OplusBlurParam.setBlurParams: FAST_KAWASE
material parameters remain owned by the already verified IME root controller.
This avoids turning a local transient layer into a second root-global material
owner. Local layers only configure their own blur radius/color/corner geometry.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

try:
    import oplus_visual_v9 as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v9.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v9", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V9 pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


FLOAT_BASE_CLASS = "com.tencent.wetype.plugin.hld.floatview.u"
VOICE_CLASS = "com.tencent.wetype.plugin.hld.voice.ImeVoiceView"

LAYER_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;"
LAYER_RELATIVE_PATH = Path(
    "com/tencent/wetype/monet/ColorOSV2LayerMaterialV10.smali"
)

# V7 made these opaque as a safe stop-gap before we had a real local blur
# layer. They now become material tint overlays over the BackgroundBlurDrawable.
LAYERED_KEY_PREVIEW_COLORS = {
    "ime_skin_key_float_view_upper_bg_color": "#70FFFFFF",
    "ime_skin_dark_key_float_view_upper_bg_color": "#702C2C2E",
    "ime_skin_key_float_view_long_click_bg_color": "#70FFFFFF",
    "ime_skin_dark_key_float_view_long_click_bg_color": "#702C2C2E",
    "ime_skin_key_float_view_click_color": "#22000000",
    "ime_skin_dark_key_float_view_click_color": "#2EFFFFFF",
}


LAYER_HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeOplusLayerV10"
.field private static final installed:Ljava/util/WeakHashMap;

.method static constructor <clinit>()V
    .locals 1
    new-instance v0, Ljava/util/WeakHashMap;
    invoke-direct {v0}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v0, Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;->installed:Ljava/util/WeakHashMap;
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

.method private static getTint(Landroid/view/View;I)I
    .locals 2
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;->isNight(Landroid/view/View;)Z
    move-result v0
    const/4 v1, 0x1
    if-ne p1, v1, :voice
    if-eqz v0, :float_light
    const v0, 0x38000000
    return v0
    :float_light
    const v0, 0x30ffffff
    return v0

    :voice
    if-eqz v0, :voice_light
    const v0, 0x40000000
    return v0
    :voice_light
    const v0, 0x38ffffff
    return v0
.end method

.method public static applyFloat(Landroid/view/View;)V
    .locals 1
    const/4 v0, 0x1
    invoke-static {p0, v0}, Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;->applyLayer(Landroid/view/View;I)V
    return-void
.end method

.method public static applyVoice(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :return
    const/4 v0, 0x2
    invoke-static {p0, v0}, Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;->applyLayer(Landroid/view/View;I)V
    :return
    return-void
.end method

.method private static applyLayer(Landroid/view/View;I)V
    .locals 11
    if-eqz p0, :return
    invoke-virtual {p0}, Landroid/view/View;->isAttachedToWindow()Z
    move-result v0
    if-eqz v0, :return

    :try_start
    sget-object v0, Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;->installed:Ljava/util/WeakHashMap;
    invoke-virtual {v0, p0}, Ljava/util/WeakHashMap;->get(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v1
    invoke-virtual {p0}, Landroid/view/View;->getBackground()Landroid/graphics/drawable/Drawable;
    move-result-object v2
    if-eqz v1, :new_layer
    if-ne v1, v2, :new_layer
    goto :return

    :new_layer
    new-instance v3, Lcom/oplus/view/ViewRootManager;
    invoke-direct {v3, p0}, Lcom/oplus/view/ViewRootManager;-><init>(Landroid/view/View;)V
    invoke-virtual {v3}, Lcom/oplus/view/ViewRootManager;->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;
    move-result-object v4
    if-eqz v4, :return

    invoke-static {p0, p1}, Lcom/tencent/wetype/monet/ColorOSV2LayerMaterialV10;->getTint(Landroid/view/View;I)I
    move-result v5
    invoke-virtual {v3, v5}, Lcom/oplus/view/ViewRootManager;->setColor(I)V

    const/4 v6, 0x1
    if-ne p1, v6, :voice_geometry
    const/16 v6, 0x64
    invoke-virtual {v3, v6}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V
    invoke-virtual {p0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v6
    invoke-virtual {v6}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v6
    iget v7, v6, Landroid/util/DisplayMetrics;->density:F
    const/high16 v8, 0x41800000    # 16.0f
    mul-float/2addr v8, v7
    invoke-virtual {v3, v8, v8, v8, v8}, Lcom/oplus/view/ViewRootManager;->setCornerRadius(FFFF)V
    goto :configured

    :voice_geometry
    const/16 v6, 0x96
    invoke-virtual {v3, v6}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V
    invoke-virtual {p0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v6
    invoke-virtual {v6}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v6
    iget v7, v6, Landroid/util/DisplayMetrics;->density:F
    const/high16 v8, 0x41e00000    # 28.0f
    mul-float/2addr v8, v7
    const/4 v7, 0x0
    invoke-virtual {v3, v8, v8, v7, v7}, Lcom/oplus/view/ViewRootManager;->setCornerRadius(FFFF)V

    :configured
    const/16 v6, 0xff
    invoke-virtual {v4, v6}, Landroid/graphics/drawable/Drawable;->setAlpha(I)V

    if-eqz v2, :blur_only
    const/4 v6, 0x2
    new-array v10, v6, [Landroid/graphics/drawable/Drawable;
    const/4 v6, 0x0
    aput-object v4, v10, v6
    const/4 v6, 0x1
    aput-object v2, v10, v6
    new-instance v9, Landroid/graphics/drawable/LayerDrawable;
    invoke-direct {v9, v10}, Landroid/graphics/drawable/LayerDrawable;-><init>([Landroid/graphics/drawable/Drawable;)V
    goto :install

    :blur_only
    move-object v9, v4

    :install
    invoke-virtual {p0, v9}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V
    invoke-virtual {v0, p0, v9}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;
    invoke-virtual {p0}, Landroid/view/View;->invalidate()V
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch
    goto :return

    :catch
    move-exception v0
    const-string v1, "WeTypeOplusLayerV10"
    const-string v2, "local layered material failed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I

    :return
    return-void
.end method
'''


def _find_class_file(decompile_dir: Path, class_name: str) -> Path | None:
    relative = Path(class_name.replace(".", "/") + ".smali")
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / relative
        if candidate.is_file():
            return candidate
    return None


def _method_block(content: str, name: str, signature: str) -> tuple[int, int] | None:
    pattern = re.compile(
        rf"(?m)^\.method[^\n]*\s{re.escape(name)}{re.escape(signature)}\s*$"
    )
    match = pattern.search(content)
    if not match:
        return None
    end = re.search(r"(?m)^\.end method\s*$", content[match.end() :])
    if not end:
        raise RuntimeError(f"Malformed smali method {name}{signature}")
    return match.start(), match.end() + end.end()


def _super_descriptor(content: str) -> str:
    match = re.search(r"(?m)^\.super\s+(L[^;]+;)\s*$", content)
    if not match:
        raise RuntimeError("Could not resolve class superclass")
    return match.group(1)


def _patch_returns(block: str, helper_method: str) -> tuple[str, int]:
    call = (
        f"    invoke-static {{p0}}, {LAYER_DESCRIPTOR}->{helper_method}"
        "(Landroid/view/View;)V\n"
    )
    if call.strip() in block:
        return block, 0
    count = len(re.findall(r"(?m)^\s*return-void\s*$", block))
    if count == 0:
        raise RuntimeError("Target lifecycle method has no return-void")
    patched = re.sub(
        r"(?m)^(?P<indent>\s*)return-void\s*$",
        lambda m: call + f"{m.group('indent')}return-void",
        block,
    )
    return patched, count


def _patch_existing_method(
    content: str, name: str, signature: str, helper_method: str
) -> tuple[str, str]:
    located = _method_block(content, name, signature)
    if located is None:
        return content, "missing"
    start, end = located
    block, count = _patch_returns(content[start:end], helper_method)
    if count:
        content = content[:start] + block + content[end:]
        return content, "existing_method_hooked"
    return content, "already_hooked"


def _add_visibility_override(
    content: str, super_desc: str, helper_method: str
) -> tuple[str, str]:
    located = _method_block(
        content, "onVisibilityChanged", "(Landroid/view/View;I)V"
    )
    if located is not None:
        return _patch_existing_method(
            content,
            "onVisibilityChanged",
            "(Landroid/view/View;I)V",
            helper_method,
        )
    method = (
        "\n.method protected onVisibilityChanged(Landroid/view/View;I)V\n"
        "    .locals 0\n"
        f"    invoke-super {{p0, p1, p2}}, {super_desc}->onVisibilityChanged(Landroid/view/View;I)V\n"
        f"    invoke-static {{p0}}, {LAYER_DESCRIPTOR}->{helper_method}(Landroid/view/View;)V\n"
        "    return-void\n"
        ".end method\n"
    )
    return content.rstrip() + "\n" + method, "override_added"


def _patch_float_root(decompile_dir: Path) -> dict[str, object]:
    path = _find_class_file(decompile_dir, FLOAT_BASE_CLASS)
    if path is None:
        raise RuntimeError(f"Missing WeType float-view base: {FLOAT_BASE_CLASS}")
    content = path.read_text(encoding="utf-8")
    super_desc = _super_descriptor(content)
    content, attach = _patch_existing_method(
        content, "onAttachedToWindow", "()V", "applyFloat"
    )
    if attach == "missing":
        raise RuntimeError("floatview.u unexpectedly has no onAttachedToWindow()")
    content, visibility = _add_visibility_override(
        content, super_desc, "applyFloat"
    )
    path.write_text(content, encoding="utf-8")
    return {
        "class": FLOAT_BASE_CLASS,
        "file": str(path.relative_to(decompile_dir)),
        "attach": attach,
        "visibility": visibility,
        "shape_policy": "preserve WeType custom ViewOutlineProvider/Path; layer blur below original background",
    }


def _patch_voice_root(decompile_dir: Path) -> dict[str, object]:
    path = _find_class_file(decompile_dir, VOICE_CLASS)
    if path is None:
        raise RuntimeError(f"Missing WeType voice root: {VOICE_CLASS}")
    content = path.read_text(encoding="utf-8")
    content, attach = _patch_existing_method(
        content, "onAttachedToWindow", "()V", "applyVoice"
    )
    content, visibility = _patch_existing_method(
        content,
        "onVisibilityChanged",
        "(Landroid/view/View;I)V",
        "applyVoice",
    )
    if attach == "missing" or visibility == "missing":
        raise RuntimeError(
            "ImeVoiceView lifecycle shape changed: expected attach + visibility methods"
        )
    path.write_text(content, encoding="utf-8")
    return {
        "class": VOICE_CLASS,
        "file": str(path.relative_to(decompile_dir)),
        "attach": attach,
        "visibility": visibility,
        "overlay_policy": "full replacement surface; V9 hides base self-draw keyboard while visible",
    }


def _find_v9_helper(decompile_dir: Path, filename: str) -> Path:
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / "com/tencent/wetype/monet" / filename
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"Could not locate generated V9 helper {filename}")


def _inject_layer_helper(decompile_dir: Path) -> str:
    v9_helper = _find_v9_helper(decompile_dir, "ColorOSV2OverlayHierarchyV9.smali")
    smali_root = next(
        p for p in v9_helper.parents if p.parent == Path(decompile_dir) and p.name.startswith("smali")
    )
    path = smali_root / LAYER_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LAYER_HELPER_SMALI, encoding="utf-8")
    return str(path.relative_to(decompile_dir))


def _add_voice_to_candidate_helper(decompile_dir: Path) -> str:
    path = _find_v9_helper(decompile_dir, "ColorOSV2PanelHierarchyV7.smali")
    content = path.read_text(encoding="utf-8")
    located = _method_block(content, "isOwnChromeClass", "(Ljava/lang/String;)Z")
    if located is None:
        raise RuntimeError("Could not locate V7 candidate ownership predicate")
    start, end = located
    block = content[start:end]
    if VOICE_CLASS in block:
        return str(path.relative_to(decompile_dir))
    marker = re.search(r"(?m)^(?P<indent>\s*)const/4 v0, 0x0\s*$", block)
    if not marker:
        raise RuntimeError("Could not locate false-return branch in V7 candidate predicate")
    indent = marker.group("indent")
    insert = (
        f'{indent}const-string v0, "{VOICE_CLASS}"\n'
        f"{indent}invoke-virtual {{p0, v0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n"
        f"{indent}move-result v0\n"
        f"{indent}if-nez v0, :yes\n"
    )
    block = block[: marker.start()] + insert + block[marker.start() :]
    path.write_text(content[:start] + block + content[end:], encoding="utf-8")
    return str(path.relative_to(decompile_dir))


def _audit_v10(decompile_dir: Path) -> dict[str, int]:
    float_path = _find_class_file(decompile_dir, FLOAT_BASE_CLASS)
    voice_path = _find_class_file(decompile_dir, VOICE_CLASS)
    if float_path is None or voice_path is None:
        raise RuntimeError("V10 audit lost float/voice roots")
    float_text = float_path.read_text(encoding="utf-8")
    voice_text = voice_path.read_text(encoding="utf-8")
    helper_path = _find_v9_helper(decompile_dir, "ColorOSV2LayerMaterialV10.smali")
    helper = helper_path.read_text(encoding="utf-8")
    overlay = _find_v9_helper(
        decompile_dir, "ColorOSV2OverlayHierarchyV9.smali"
    ).read_text(encoding="utf-8")
    candidate = _find_v9_helper(
        decompile_dir, "ColorOSV2PanelHierarchyV7.smali"
    ).read_text(encoding="utf-8")

    float_calls = float_text.count(
        f"{LAYER_DESCRIPTOR}->applyFloat(Landroid/view/View;)V"
    )
    voice_calls = voice_text.count(
        f"{LAYER_DESCRIPTOR}->applyVoice(Landroid/view/View;)V"
    )
    if float_calls < 2:
        raise RuntimeError(f"V10 float hook coverage too small: {float_calls}")
    if voice_calls < 2:
        raise RuntimeError(f"V10 voice hook coverage too small: {voice_calls}")
    if "OplusBlurParam;->setBlurParams" in helper or "->setBlurParams(" in helper:
        raise RuntimeError("V10 local helper must not own root-global OplusBlurParam")
    if VOICE_CLASS not in overlay:
        raise RuntimeError("Voice root missing from V9 full-overlay suppression set")
    if VOICE_CLASS not in candidate:
        raise RuntimeError("Voice root missing from candidate/toolbar ownership predicate")

    return {
        "float_layer_hook_sites": float_calls,
        "voice_layer_hook_sites": voice_calls,
        "local_viewroot_manager_sites": helper.count("Lcom/oplus/view/ViewRootManager;"),
        "local_set_blur_params_sites": helper.count("->setBlurParams("),
    }


def apply_coloros_v2_visual_profile_v10(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)

    # Make voice a first-class full replacement panel while V8/V9 generate
    # their lifecycle/overlay helpers. Restore Python module globals afterward;
    # generated smali keeps the proven mapping.
    original_panels = base.PANEL_CLASSES
    original_own_chrome = base.V7.OWN_CHROME_PANEL_CLASSES
    original_preview = base.V7.KEY_PREVIEW_COLORS
    original_extra = base.V7.EXTRA_STATE_COLORS

    extended_panels = tuple(dict.fromkeys((*original_panels, VOICE_CLASS)))
    extended_own_chrome = tuple(
        dict.fromkeys((*original_own_chrome, VOICE_CLASS))
    )
    base.PANEL_CLASSES = extended_panels
    base.V7.OWN_CHROME_PANEL_CLASSES = extended_own_chrome
    base.V7.KEY_PREVIEW_COLORS = dict(LAYERED_KEY_PREVIEW_COLORS)
    base.V7.EXTRA_STATE_COLORS = {
        **base.V7.PRESSED_STATE_COLORS,
        **LAYERED_KEY_PREVIEW_COLORS,
    }
    try:
        visual_v9 = base.apply_coloros_v2_visual_profile_v9(
            decompile_dir, patch_report
        )
    finally:
        base.PANEL_CLASSES = original_panels
        base.V7.OWN_CHROME_PANEL_CLASSES = original_own_chrome
        base.V7.KEY_PREVIEW_COLORS = original_preview
        base.V7.EXTRA_STATE_COLORS = original_extra

    helper = _inject_layer_helper(decompile_dir)
    candidate = _add_voice_to_candidate_helper(decompile_dir)
    float_report = _patch_float_root(decompile_dir)
    voice_report = _patch_voice_root(decompile_dir)
    audit = _audit_v10(decompile_dir)

    return {
        "strategy": (
            "V9 lifecycle-complete overlay state + transient local ColorOS BackgroundBlurDrawable "
            "layers for floatview.u key bubbles and ImeVoiceView"
        ),
        "base_v9": visual_v9,
        "layer_helper": helper,
        "key_preview": {
            "class": FLOAT_BASE_CLASS,
            "resource_tints": dict(LAYERED_KEY_PREVIEW_COLORS),
            "hook": float_report,
            "blur_radius": 100,
            "corner_radius_dp": 16,
        },
        "voice": {
            "class": VOICE_CLASS,
            "hook": voice_report,
            "candidate_helper": candidate,
            "blur_radius": 150,
            "top_corner_radius_dp": 28,
            "base_keyboard_suppressed": True,
        },
        "performance_contract": {
            "root_material_owner": "unchanged OplusKeyboardBlur",
            "local_blur_instances": "transient float root + visible voice root only",
            "per_key_viewroot_blur": False,
            "global_layout_scan": False,
            "local_oplus_blur_param_owner": False,
        },
        "runtime_audit": audit,
    }
