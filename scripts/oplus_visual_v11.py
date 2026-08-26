#!/usr/bin/env python3
"""V11 hotfix: restore stable voice rendering and key-preview opacity.

Device feedback on V10 exposed a serious regression: entering ImeVoiceView could
flash the previous keyboard several times and then hang. The failure mechanism
is consistent with two V10 design mistakes that should not exist in an IME hot
path:

1. ImeVoiceView was added to V9's generic effective-visibility hooks. That adds
   a setAlpha callback. Voice transitions animate alpha, so a per-frame alpha
   stream can enqueue repeated whole-root reconciliation work.
2. V10 then installed a second BackgroundBlurDrawable on ImeVoiceView itself.
   The local helper wrapped the current background in a LayerDrawable whenever
   WeType replaced that background. A dynamic voice surface can therefore grow
   nested drawable layers and repeatedly touch ViewRootManager during the same
   transition.

V11 removes both hazards. The already verified IME-root FAST_KAWASE material is
sufficient for voice: while voice is visible we only suppress the underlying
self-draw keyboard and candidate chrome, allowing the existing root blur to be
the one compositor owner. Voice gets only attach/detach/direct setVisibility
hooks; no alpha, window-visibility, global-layout, or local ViewRootManager hook.

V10 also deliberately made key-preview resources translucent (#70 alpha) while
trying the unsupported local bubble blur. That is reverted. V7's opaque preview
surface is restored so the key bubble cannot leak the app behind it. Actual
bubble-level blur must wait for the real self-draw bubble painter/config hook;
we do not fake it by attaching blur to the wrong float container again.
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


VOICE_CLASS = "com.tencent.wetype.plugin.hld.voice.ImeVoiceView"
LIFECYCLE_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;"


def _find_class_file(decompile_dir: Path, class_name: str) -> Path | None:
    relative = Path(class_name.replace(".", "/") + ".smali")
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / relative
        if candidate.is_file():
            return candidate
    return None


def _find_generated_helper(decompile_dir: Path, filename: str) -> Path:
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / "com/tencent/wetype/monet" / filename
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"Could not locate generated helper: {filename}")


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
        raise RuntimeError("Could not resolve direct superclass")
    return match.group(1)


def _insert_class_predicate(
    path: Path, method_name: str, class_name: str
) -> str:
    content = path.read_text(encoding="utf-8")
    located = _method_block(content, method_name, "(Ljava/lang/String;)Z")
    if located is None:
        raise RuntimeError(f"Could not locate {method_name} predicate in {path}")
    start, end = located
    block = content[start:end]
    if class_name in block:
        return "already_present"

    marker = re.search(r"(?m)^(?P<indent>\s*)const/4 v0, 0x0\s*$", block)
    if not marker:
        raise RuntimeError(f"Could not locate false return in {method_name}")
    indent = marker.group("indent")
    insert = (
        f'{indent}const-string v0, "{class_name}"\n'
        f"{indent}invoke-virtual {{p0, v0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n"
        f"{indent}move-result v0\n"
        f"{indent}if-nez v0, :yes\n"
    )
    block = block[: marker.start()] + insert + block[marker.start() :]
    path.write_text(content[:start] + block + content[end:], encoding="utf-8")
    return "inserted"


def _hook_returns(block: str, callback: str, before_return: bool = True) -> tuple[str, int]:
    call = (
        f"    invoke-static {{p0}}, {LIFECYCLE_DESCRIPTOR}->{callback}"
        "(Landroid/view/View;)V\n"
    )
    if call.strip() in block:
        return block, 0
    count = len(re.findall(r"(?m)^\s*return-void\s*$", block))
    if count == 0:
        raise RuntimeError("Lifecycle method has no return-void")
    patched = re.sub(
        r"(?m)^(?P<indent>\s*)return-void\s*$",
        lambda m: call + f"{m.group('indent')}return-void",
        block,
    )
    return patched, count


def _patch_existing(
    content: str, name: str, signature: str, callback: str
) -> tuple[str, str]:
    located = _method_block(content, name, signature)
    if located is None:
        return content, "missing"
    start, end = located
    block, count = _hook_returns(content[start:end], callback)
    if count:
        content = content[:start] + block + content[end:]
        return content, "existing_method_hooked"
    return content, "already_hooked"


def _append_override(
    content: str,
    super_desc: str,
    name: str,
    signature: str,
    callback: str,
    callback_before_super: bool,
) -> str:
    if name == "setVisibility":
        super_call = f"    invoke-super {{p0, p1}}, {super_desc}->{name}{signature}\n"
    else:
        super_call = f"    invoke-super {{p0}}, {super_desc}->{name}{signature}\n"
    callback_call = (
        f"    invoke-static {{p0}}, {LIFECYCLE_DESCRIPTOR}->{callback}"
        "(Landroid/view/View;)V\n"
    )
    body = callback_call + super_call if callback_before_super else super_call + callback_call
    visibility = "public" if name == "setVisibility" else "protected"
    return (
        content.rstrip()
        + f"\n\n.method {visibility} {name}{signature}\n"
        + "    .locals 0\n"
        + body
        + "    return-void\n"
        + ".end method\n"
    )


def _patch_voice_lifecycle(decompile_dir: Path) -> dict[str, object]:
    path = _find_class_file(decompile_dir, VOICE_CLASS)
    if path is None:
        raise RuntimeError(f"Missing WeType voice root: {VOICE_CLASS}")
    content = path.read_text(encoding="utf-8")
    super_desc = _super_descriptor(content)
    ops: dict[str, str] = {}

    # Attach: preserve app initialization first, then adapt/reconcile once.
    content, state = _patch_existing(
        content, "onAttachedToWindow", "()V", "onPanelAttached"
    )
    if state == "missing":
        content = _append_override(
            content,
            super_desc,
            "onAttachedToWindow",
            "()V",
            "onPanelAttached",
            False,
        )
        state = "override_added"
    ops["onAttachedToWindow"] = state

    # Detach: capture the root before super detaches it.
    located = _method_block(content, "onDetachedFromWindow", "()V")
    if located is None:
        content = _append_override(
            content,
            super_desc,
            "onDetachedFromWindow",
            "()V",
            "onPanelDetached",
            True,
        )
        ops["onDetachedFromWindow"] = "override_added"
    else:
        start, end = located
        block = content[start:end]
        call = (
            f"    invoke-static {{p0}}, {LIFECYCLE_DESCRIPTOR}->onPanelDetached"
            "(Landroid/view/View;)V\n"
        )
        if call.strip() not in block:
            # Put the callback immediately after .locals/.registers, before any
            # app/super detach work can destroy getRootView().
            m = re.search(r"(?m)^\s*\.(?:locals|registers)\s+\d+\s*$", block)
            if not m:
                raise RuntimeError("Voice detach method has no locals/registers directive")
            insert_at = m.end()
            block = block[:insert_at] + "\n" + call.rstrip("\n") + block[insert_at:]
            content = content[:start] + block + content[end:]
            ops["onDetachedFromWindow"] = "existing_method_hooked"
        else:
            ops["onDetachedFromWindow"] = "already_hooked"

    # Direct visibility transitions only. Do NOT hook setAlpha,
    # onVisibilityChanged or onWindowVisibilityChanged; voice animation may
    # touch those every frame.
    content, state = _patch_existing(
        content, "setVisibility", "(I)V", "onPanelVisibilityChanged"
    )
    if state == "missing":
        content = _append_override(
            content,
            super_desc,
            "setVisibility",
            "(I)V",
            "onPanelVisibilityChanged",
            False,
        )
        state = "override_added"
    ops["setVisibility"] = state

    path.write_text(content, encoding="utf-8")
    return {
        "class": VOICE_CLASS,
        "file": str(path.relative_to(decompile_dir)),
        "operations": ops,
        "explicitly_not_hooked": [
            "setAlpha(F)V",
            "onVisibilityChanged(Landroid/view/View;I)V",
            "onWindowVisibilityChanged(I)V",
        ],
    }


def _audit_v11(decompile_dir: Path) -> dict[str, int]:
    root = Path(decompile_dir)
    voice_path = _find_class_file(root, VOICE_CLASS)
    if voice_path is None:
        raise RuntimeError("V11 audit lost ImeVoiceView")
    voice = voice_path.read_text(encoding="utf-8")
    overlay = _find_generated_helper(
        root, "ColorOSV2OverlayHierarchyV9.smali"
    ).read_text(encoding="utf-8")
    candidate = _find_generated_helper(
        root, "ColorOSV2PanelHierarchyV7.smali"
    ).read_text(encoding="utf-8")

    if VOICE_CLASS not in overlay:
        raise RuntimeError("Voice missing from full-overlay predicate")
    if VOICE_CLASS not in candidate:
        raise RuntimeError("Voice missing from candidate ownership predicate")

    # Only one explicit visibility callback is allowed on voice. Alpha/window
    # callbacks were the hot-loop risk in V10.
    visibility_callbacks = voice.count(
        f"{LIFECYCLE_DESCRIPTOR}->onPanelVisibilityChanged(Landroid/view/View;)V"
    )
    if visibility_callbacks != 1:
        raise RuntimeError(
            f"Unexpected voice visibility callback count: {visibility_callbacks}"
        )
    if "ColorOSV2LayerMaterialV10" in voice:
        raise RuntimeError("V10 local material call leaked into voice class")

    all_smali = []
    for smali_root in sorted(root.glob("smali*")):
        for path in smali_root.rglob("*.smali"):
            all_smali.append(path.read_text(encoding="utf-8", errors="ignore"))
    joined = "\n".join(all_smali)
    if "ColorOSV2LayerMaterialV10" in joined:
        raise RuntimeError("V10 local material helper leaked into rebuilt APK")

    # Root keyboard material is still allowed to own ViewRootManager. V11 adds
    # no second local owner.
    viewroot_sites = joined.count("Lcom/oplus/view/ViewRootManager;")
    root_owner_sites = 0
    for smali_root in sorted(root.glob("smali*")):
        owner = smali_root / "com/tencent/wetype/monet/OplusKeyboardBlur.smali"
        if owner.is_file():
            root_owner_sites += owner.read_text(encoding="utf-8").count(
                "Lcom/oplus/view/ViewRootManager;"
            )
    if viewroot_sites != root_owner_sites:
        raise RuntimeError(
            "Unexpected non-root ViewRootManager owner in V11: "
            f"all={viewroot_sites}, root={root_owner_sites}"
        )

    return {
        "voice_visibility_callbacks": visibility_callbacks,
        "all_viewroot_manager_sites": viewroot_sites,
        "root_material_viewroot_sites": root_owner_sites,
        "local_viewroot_manager_sites": viewroot_sites - root_owner_sites,
    }


def apply_coloros_v2_visual_profile_v11(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)

    # Start from V9 exactly. This restores V7's opaque key-preview resources and
    # deliberately excludes every V10 local-blur mutation.
    visual_v9 = base.apply_coloros_v2_visual_profile_v9(
        decompile_dir, patch_report
    )

    overlay_path = _find_generated_helper(
        decompile_dir, "ColorOSV2OverlayHierarchyV9.smali"
    )
    candidate_path = _find_generated_helper(
        decompile_dir, "ColorOSV2PanelHierarchyV7.smali"
    )
    overlay_patch = _insert_class_predicate(
        overlay_path, "isOverlayClass", VOICE_CLASS
    )
    candidate_patch = _insert_class_predicate(
        candidate_path, "isOwnChromeClass", VOICE_CLASS
    )
    voice = _patch_voice_lifecycle(decompile_dir)
    audit = _audit_v11(decompile_dir)

    return {
        "strategy": (
            "V9 stable root FAST_KAWASE material + voice as a lightweight full overlay; "
            "no local voice/bubble ViewRootManager, no voice alpha/window callbacks, "
            "opaque V7 key-preview fallback"
        ),
        "base_v9": visual_v9,
        "voice": {
            "class": VOICE_CLASS,
            "overlay_predicate": overlay_patch,
            "candidate_predicate": candidate_patch,
            "lifecycle": voice,
            "material_source": "existing single IME root BackgroundBlurDrawable",
            "base_keyboard_suppressed": True,
            "candidate_suppressed": True,
        },
        "key_preview": {
            "policy": "restore V7 opaque preview colors; remove unsupported V10 float-container blur",
            "light": "#FFFFFFFF",
            "dark": "#FF2C2C2E",
        },
        "performance_contract": {
            "voice_local_viewroot_blur": False,
            "bubble_local_viewroot_blur": False,
            "voice_set_alpha_hook": False,
            "voice_window_visibility_hook": False,
            "global_layout_scan": False,
            "root_material_owner": "OplusKeyboardBlur only",
        },
        "runtime_audit": audit,
    }
