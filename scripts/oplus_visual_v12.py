#!/usr/bin/env python3
"""V12: WeType-Tool-parity local blur for key bubbles and floating keyboard.

V12 keeps V11's stable voice policy and single IME-root FAST_KAWASE owner, but
replaces the failed V10 local ViewRootManager experiment with the mechanism
used by WeType Tool v1.3.2: obtain the *existing* ViewRootImpl through
View.getViewRootImpl(), ask it for createBackgroundBlurDrawable(), and configure
that drawable reflectively.

Two runtime paths are patched only at stable creation/lifecycle boundaries:

* floatview.u.v(...): install the key-preview blur after addView(),
  setBackgroundColor(0), and N(). This ordering is essential because the old
  attach hook was overwritten by v() itself. The existing WeType
  ViewOutlineProvider/path is preserved and clipToOutline is enabled. The
  popup's own path fill is made translucent at the exact ime_color_12 paint
  site so it no longer occludes the compositor blur.
* float.e (FloatingKeyboardContentView): on attach, create Tool-style
  WeTypeBlurCarrier_Float / WeTypeBlurHighlight_Float siblings behind/above the
  floating root, clear only WeType-owned backgrounds with an IdentityHashMap,
  and restore all of them on detach. No alpha/visibility hot-loop hooks are
  introduced.

The full WeType Tool artifact contains no ImeVoiceView/voice-blur hook surface,
so V12 deliberately does not add a second voice-local blur owner. Voice stays
on V11's stable root material and lightweight overlay suppression.
"""

from __future__ import annotations

import base64
import importlib.util
import re
import zlib
from pathlib import Path

try:
    import oplus_visual_v11 as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v11.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v11", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V11 pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


FLOAT_BASE_CLASS = "com.tencent.wetype.plugin.hld.floatview.u"
FLOATING_CONTENT_CLASS = "com.tencent.wetype.plugin.hld.float.e"
VOICE_CLASS = base.VOICE_CLASS

LOCAL_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV12;"
LOCAL_RELATIVE_PATH = Path("com/tencent/wetype/monet/ColorOSV2LocalBlurV12.smali")

# V11 intentionally returned to opaque preview resources after V10 failed.
# V12 has a real post-construction blur owner, so these become restrained glass
# tints again. The actual floatview.u path fill is separately reduced below.
V12_KEY_PREVIEW_COLORS = {
    "ime_skin_key_float_view_upper_bg_color": "#5AFFFFFF",
    "ime_skin_dark_key_float_view_upper_bg_color": "#5A2C2C2E",
    "ime_skin_key_float_view_long_click_bg_color": "#5AFFFFFF",
    "ime_skin_dark_key_float_view_long_click_bg_color": "#5A2C2C2E",
    "ime_skin_key_float_view_click_color": "#22000000",
    "ime_skin_dark_key_float_view_click_color": "#2EFFFFFF",
}

BUBBLE_METHOD_SIGNATURE = (
    "(Landroid/graphics/Rect;Landroid/view/ViewGroup;Ljava/util/List;ZLwc/l;Lwc/a;)V"
)
BUBBLE_FILL_ALPHA = 0x48


# Compressed only to keep the patch script reviewable; decoded bytes are
# deterministic and unit/audit checks inspect the resulting smali.
_LOCAL_HELPER_ZLIB_B64 = "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"
LOCAL_HELPER_SMALI = zlib.decompress(base64.b64decode(_LOCAL_HELPER_ZLIB_B64)).decode("utf-8")


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


def _find_generated_helper(decompile_dir: Path, filename: str) -> Path:
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / "com/tencent/wetype/monet" / filename
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"Could not locate generated helper: {filename}")


def _inject_local_helper(decompile_dir: Path) -> str:
    anchor = _find_generated_helper(decompile_dir, "ColorOSV2OverlayHierarchyV9.smali")
    root = Path(decompile_dir)
    smali_root = next(
        p for p in anchor.parents if p.parent == root and p.name.startswith("smali")
    )
    path = smali_root / LOCAL_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LOCAL_HELPER_SMALI, encoding="utf-8")
    return str(path.relative_to(root))


def _patch_bubble_creation(decompile_dir: Path) -> dict[str, object]:
    path = _find_class_file(decompile_dir, FLOAT_BASE_CLASS)
    if path is None:
        raise RuntimeError(f"Missing WeType float-view base: {FLOAT_BASE_CLASS}")
    content = path.read_text(encoding="utf-8")
    located = _method_block(content, "v", BUBBLE_METHOD_SIGNATURE)
    if located is None:
        raise RuntimeError("floatview.u.v(...) creation method shape changed")
    start, end = located
    block = content[start:end]
    call = (
        f"    invoke-static {{p0}}, {LOCAL_DESCRIPTOR}->installBubble"
        "(Landroid/view/View;)V\n"
    )
    if call.strip() in block:
        return {
            "file": str(path.relative_to(decompile_dir)),
            "creation_hook": "already_hooked",
        }

    set_bg = block.find("Landroid/view/View;->setBackgroundColor(I)V")
    anchor_text = (
        "    invoke-virtual {p0}, Lcom/tencent/wetype/plugin/hld/floatview/u;->N()V\n"
    )
    anchor = block.find(anchor_text)
    if set_bg < 0 or anchor < 0 or set_bg > anchor:
        raise RuntimeError(
            "floatview.u.v() no longer has setBackgroundColor(0) -> N() ordering"
        )
    if block.count(anchor_text) != 1:
        raise RuntimeError("floatview.u.v() has ambiguous N() creation anchor")
    insert_at = anchor + len(anchor_text)
    block = block[:insert_at] + call + block[insert_at:]
    path.write_text(content[:start] + block + content[end:], encoding="utf-8")
    return {
        "file": str(path.relative_to(decompile_dir)),
        "creation_hook": "inserted_after_N",
        "ordering": "addView -> setBackgroundColor(0) -> N() -> installBubble",
    }


def _patch_bubble_fill_alpha(decompile_dir: Path) -> dict[str, object]:
    path = _find_class_file(decompile_dir, FLOAT_BASE_CLASS)
    if path is None:
        raise RuntimeError(f"Missing WeType float-view base: {FLOAT_BASE_CLASS}")
    content = path.read_text(encoding="utf-8")
    located = _method_block(content, "onDraw", "(Landroid/graphics/Canvas;)V")
    if located is None:
        raise RuntimeError("floatview.u.onDraw(Canvas) missing")
    start, end = located
    block = content[start:end]
    marker = "# WeTypeOplusV12 bubble fill alpha"
    if marker in block:
        return {
            "file": str(path.relative_to(decompile_dir)),
            "fill_alpha": "already_patched",
            "alpha": BUBBLE_FILL_ALPHA,
        }
    semantic = "Lcom/tencent/wetype/plugin/hld/o;->ime_color_12:I"
    semantic_pos = block.find(semantic)
    if semantic_pos < 0:
        raise RuntimeError("floatview.u.onDraw no longer paints ime_color_12 fill")
    set_color = "    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setColor(I)V\n"
    set_pos = block.find(set_color, semantic_pos)
    if set_pos < 0:
        raise RuntimeError("Could not locate ime_color_12 Paint.setColor site")
    insert_at = set_pos + len(set_color)
    alpha_patch = (
        f"    {marker}\n"
        f"    const/16 v2, 0x{BUBBLE_FILL_ALPHA:x}\n"
        "    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setAlpha(I)V\n"
    )
    block = block[:insert_at] + alpha_patch + block[insert_at:]

    # floatview.u reuses one Paint for fill and stroke. setColor() does not
    # reset Paint alpha, so restore 255 at the exact ime_color_09 stroke site;
    # otherwise V12 would accidentally fade the outline as well.
    stroke_semantic = "Lcom/tencent/wetype/plugin/hld/o;->ime_color_09:I"
    stroke_pos = block.find(stroke_semantic, insert_at + len(alpha_patch))
    if stroke_pos < 0:
        raise RuntimeError("floatview.u.onDraw no longer paints ime_color_09 stroke")
    stroke_set_pos = block.find(set_color, stroke_pos)
    if stroke_set_pos < 0:
        raise RuntimeError("Could not locate ime_color_09 Paint.setColor site")
    stroke_insert = stroke_set_pos + len(set_color)
    stroke_reset = (
        "    # WeTypeOplusV12 bubble stroke alpha restore\n"
        "    const/16 v2, 0xff\n"
        "    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setAlpha(I)V\n"
    )
    block = block[:stroke_insert] + stroke_reset + block[stroke_insert:]
    path.write_text(content[:start] + block + content[end:], encoding="utf-8")
    return {
        "file": str(path.relative_to(decompile_dir)),
        "fill_alpha": "patched_exact_ime_color_12_site",
        "stroke_alpha": "restored_exact_ime_color_09_site",
        "alpha": BUBBLE_FILL_ALPHA,
    }


def _patch_floating_lifecycle(decompile_dir: Path) -> dict[str, object]:
    path = _find_class_file(decompile_dir, FLOATING_CONTENT_CLASS)
    if path is None:
        raise RuntimeError(
            f"Missing Tool-mapped FloatingKeyboardContentView: {FLOATING_CONTENT_CLASS}"
        )
    content = path.read_text(encoding="utf-8")

    attach = _method_block(content, "onAttachedToWindow", "()V")
    detach = _method_block(content, "onDetachedFromWindow", "()V")
    if attach is None or detach is None:
        raise RuntimeError("FloatingKeyboardContentView lifecycle shape changed")

    # Patch detach first so offsets for attach are not invalidated.
    dstart, dend = detach
    dblock = content[dstart:dend]
    restore_call = (
        f"    invoke-static {{p0}}, {LOCAL_DESCRIPTOR}->restoreFloating"
        "(Landroid/view/View;)V\n"
    )
    detach_state = "already_hooked"
    if restore_call.strip() not in dblock:
        directive = re.search(r"(?m)^\s*\.(?:locals|registers)\s+\d+\s*$", dblock)
        if not directive:
            raise RuntimeError("Floating detach method has no locals/registers directive")
        insert_at = directive.end()
        dblock = dblock[:insert_at] + "\n" + restore_call.rstrip("\n") + dblock[insert_at:]
        content = content[:dstart] + dblock + content[dend:]
        detach_state = "inserted_before_detach_work"

    attach = _method_block(content, "onAttachedToWindow", "()V")
    assert attach is not None
    astart, aend = attach
    ablock = content[astart:aend]
    install_call = (
        f"    invoke-static {{p0}}, {LOCAL_DESCRIPTOR}->installFloating"
        "(Landroid/view/View;)V\n"
    )
    attach_state = "already_hooked"
    if install_call.strip() not in ablock:
        returns = list(re.finditer(r"(?m)^(?P<indent>\s*)return-void\s*$", ablock))
        if len(returns) != 1:
            raise RuntimeError(
                f"Floating onAttachedToWindow expected one return, found {len(returns)}"
            )
        match = returns[0]
        ablock = ablock[: match.start()] + install_call + ablock[match.start() :]
        content = content[:astart] + ablock + content[aend:]
        attach_state = "inserted_after_app_attach_work"

    path.write_text(content, encoding="utf-8")
    return {
        "class": FLOATING_CONTENT_CLASS,
        "file": str(path.relative_to(decompile_dir)),
        "attach": attach_state,
        "detach": detach_state,
        "accessors": ["getRootView", "getContent"],
    }


def _audit_v12(decompile_dir: Path) -> dict[str, int | bool]:
    root = Path(decompile_dir)
    helper_path = _find_generated_helper(root, "ColorOSV2LocalBlurV12.smali")
    helper = helper_path.read_text(encoding="utf-8")
    float_path = _find_class_file(root, FLOAT_BASE_CLASS)
    floating_path = _find_class_file(root, FLOATING_CONTENT_CLASS)
    voice_path = _find_class_file(root, VOICE_CLASS)
    if float_path is None or floating_path is None or voice_path is None:
        raise RuntimeError("V12 audit lost a required runtime class")
    float_text = float_path.read_text(encoding="utf-8")
    floating_text = floating_path.read_text(encoding="utf-8")
    voice_text = voice_path.read_text(encoding="utf-8")

    required = (
        "getViewRootImpl",
        "createBackgroundBlurDrawable",
        "setBlurRadius",
        "setCornerRadius",
        "WeTypeBlurCarrier_Float",
        "WeTypeBlurHighlight_Float",
        "Ljava/util/IdentityHashMap;",
        "restoreBackgrounds",
    )
    missing = [token for token in required if token not in helper]
    if missing:
        raise RuntimeError("V12 helper missing Tool-parity primitives: " + ", ".join(missing))
    if "Lcom/oplus/view/ViewRootManager;" in helper:
        raise RuntimeError("V12 local helper regressed to ViewRootManager")

    bubble_calls = float_text.count(
        f"{LOCAL_DESCRIPTOR}->installBubble(Landroid/view/View;)V"
    )
    if bubble_calls != 1:
        raise RuntimeError(f"Expected exactly one post-N bubble hook, got {bubble_calls}")
    fill_hooks = float_text.count("# WeTypeOplusV12 bubble fill alpha")
    if fill_hooks != 1:
        raise RuntimeError(f"Expected exactly one bubble fill-alpha hook, got {fill_hooks}")
    stroke_resets = float_text.count("# WeTypeOplusV12 bubble stroke alpha restore")
    if stroke_resets != 1:
        raise RuntimeError(f"Expected exactly one bubble stroke-alpha restore, got {stroke_resets}")
    floating_install = floating_text.count(
        f"{LOCAL_DESCRIPTOR}->installFloating(Landroid/view/View;)V"
    )
    floating_restore = floating_text.count(
        f"{LOCAL_DESCRIPTOR}->restoreFloating(Landroid/view/View;)V"
    )
    if floating_install != 1 or floating_restore != 1:
        raise RuntimeError(
            f"Floating lifecycle coverage mismatch: install={floating_install}, restore={floating_restore}"
        )

    # Voice remains exactly V11: no local V12 blur, and no V10 helper.
    if "ColorOSV2LocalBlurV12" in voice_text:
        raise RuntimeError("Voice unexpectedly gained a V12 local blur owner")
    if "ColorOSV2LayerMaterialV10" in voice_text:
        raise RuntimeError("V10 voice helper leaked back into runtime")

    all_viewroot_sites = 0
    root_owner_sites = 0
    v10_sites = 0
    for smali_root in sorted(root.glob("smali*")):
        for path in smali_root.rglob("*.smali"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            all_viewroot_sites += text.count("Lcom/oplus/view/ViewRootManager;")
            v10_sites += text.count("ColorOSV2LayerMaterialV10")
        owner = smali_root / "com/tencent/wetype/monet/OplusKeyboardBlur.smali"
        if owner.is_file():
            root_owner_sites += owner.read_text(encoding="utf-8").count(
                "Lcom/oplus/view/ViewRootManager;"
            )
    if v10_sites:
        raise RuntimeError(f"V10 local helper leaked into V12 ({v10_sites} refs)")
    if all_viewroot_sites != root_owner_sites:
        raise RuntimeError(
            "Unexpected non-root ViewRootManager owner: "
            f"all={all_viewroot_sites}, root={root_owner_sites}"
        )

    return {
        "bubble_hook_sites": bubble_calls,
        "bubble_fill_alpha_hooks": fill_hooks,
        "bubble_stroke_alpha_resets": stroke_resets,
        "floating_install_hooks": floating_install,
        "floating_restore_hooks": floating_restore,
        "local_viewroot_manager_sites": all_viewroot_sites - root_owner_sites,
        "root_viewroot_manager_sites": root_owner_sites,
        "uses_viewrootimpl_factory": "createBackgroundBlurDrawable" in helper,
        "voice_local_blur": False,
    }


def apply_coloros_v2_visual_profile_v12(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)

    # Run the stable V11 pipeline, but now that the real post-creation bubble
    # blur exists, allow the key-preview skin resources to act as glass tints
    # rather than opaque emergency fallbacks.
    v7 = base.base.V7
    original_preview = v7.KEY_PREVIEW_COLORS
    original_extra = v7.EXTRA_STATE_COLORS
    v7.KEY_PREVIEW_COLORS = dict(V12_KEY_PREVIEW_COLORS)
    v7.EXTRA_STATE_COLORS = {
        **v7.PRESSED_STATE_COLORS,
        **V12_KEY_PREVIEW_COLORS,
    }
    try:
        visual_v11 = base.apply_coloros_v2_visual_profile_v11(
            decompile_dir, patch_report
        )
    finally:
        v7.KEY_PREVIEW_COLORS = original_preview
        v7.EXTRA_STATE_COLORS = original_extra

    helper = _inject_local_helper(decompile_dir)
    bubble_creation = _patch_bubble_creation(decompile_dir)
    bubble_fill = _patch_bubble_fill_alpha(decompile_dir)
    floating = _patch_floating_lifecycle(decompile_dir)
    audit = _audit_v12(decompile_dir)

    return {
        "strategy": (
            "V11 stable root FAST_KAWASE/voice policy + WeType-Tool ViewRootImpl "
            "BackgroundBlurDrawable factory for post-created key bubbles and a reversible "
            "floating-keyboard carrier/highlight stack"
        ),
        "base_v11": visual_v11,
        "local_helper": helper,
        "key_preview": {
            "class": FLOAT_BASE_CLASS,
            "creation": bubble_creation,
            "fill": bubble_fill,
            "resource_tints": dict(V12_KEY_PREVIEW_COLORS),
            "blur_radius": 100,
            "corner_policy": "existing WeType outline/path + clipToOutline; 16dp blur fallback geometry",
        },
        "floating_keyboard": {
            "class": FLOATING_CONTENT_CLASS,
            "lifecycle": floating,
            "blur_radius": 150,
            "corner_radius_dp": 28,
            "carrier_tag": "WeTypeBlurCarrier_Float",
            "highlight_tag": "WeTypeBlurHighlight_Float",
            "background_restore": "IdentityHashMap, restored on detach",
        },
        "voice": {
            "class": VOICE_CLASS,
            "policy": (
                "unchanged V11 single-root blur; full Tool v1.3.2 audit has no "
                "ImeVoiceView/voice-blur local hook"
            ),
            "local_blur": False,
        },
        "performance_contract": {
            "root_material_owner": "OplusKeyboardBlur only",
            "local_blur_factory": "existing ViewRootImpl.createBackgroundBlurDrawable via reflection",
            "local_viewroot_manager": False,
            "bubble_hook_frequency": "one post-construction v() edge",
            "floating_hooks": "attach/detach only",
            "voice_alpha_or_window_hooks": False,
            "global_layout_scan": False,
        },
        "runtime_audit": audit,
    }
