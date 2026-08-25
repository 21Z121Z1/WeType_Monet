#!/usr/bin/env python3
"""V8: WeType-Tool-guided, event-driven ColorOS appearance integration.

V1-V7 proved the ColorOS compositor/material path and most visual geometry on
real ColorOS 17 hardware.  V8 uses the independently shipped WeType Tool
v1.3.2 API102 module as a *hook-surface map*, not as a blur implementation.

The v1.3.2 release (SHA-256
9893b3416ce6ca20221d2afe49a166318c7e2c5b123dc709b14264c6b3f57eff)
exposes stable semantic targets for keyboardBlurInitMethod,
keyboardBlurRootViewField, keyRuntimeStyleBinder/keyRuntimeCornerSetter,
toolbarInvokeMethod, candidate bind/background hooks, press-bubble symbols and
floating-keyboard root/content accessors.  Its resource-side background pass
explicitly groups exactly these surfaces:

* ime_emoji_keyboard_gradient_bg_color[_dark]
* ime_keyboard_full_gradient_bg_color[_dark]
* ime_skin_clipboard_item_bg_color

It also installs lifecycle/visibility hooks instead of re-walking the complete
IME tree on every layout.  V8 follows that architecture:

* one ColorOS FAST_KAWASE BackgroundBlurDrawable remains the only compositor
  blur owner;
* full keyboard/tool/emoji gradient painters are made transparent so they do
  not cover that blur;
* clipboard cards keep a restrained elevated tint;
* normal/pressed keys remain WeType's self-draw state machine (V7), so there is
  no per-key ViewRootManager allocation;
* own-chrome tool panels get exact attach/detach/visibility hooks.  Expensive
  V6/V7 tree reconciliation only happens when a panel changes lifecycle, not on
  every global layout;
* newly attached tool panels receive the G2/V2/system-font tree adaptation once
  when shown.

The old global-layout listener is deliberately neutralized after initial
attachment.  This removes the per-keystroke O(N-view-tree) scan while retaining
V8 lifecycle hooks for emoji, clipboard/common phrase, Ask AI and the other
audited full tool panels.
"""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import oplus_visual_v7 as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v7.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v7", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V7 pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


WETYPE_TOOL_RELEASE_SHA256 = (
    "9893b3416ce6ca20221d2afe49a166318c7e2c5b123dc709b14264c6b3f57eff"
)

# The three visual resource families explicitly referenced by WeType Tool's
# v1.3.2 background-handling implementation.  We have a single verified
# compositor blur underneath all of them, so full-surface painters must be
# clear.  Clipboard items are cards, not full surfaces, and retain elevation.
WETYPE_TOOL_SURFACE_COLORS = {
    "ime_emoji_keyboard_gradient_bg_color": "#00000000",
    "ime_emoji_keyboard_gradient_bg_color_dark": "#00000000",
    "ime_keyboard_full_gradient_bg_color": "#00000000",
    "ime_keyboard_full_gradient_bg_color_dark": "#00000000",
    "ime_skin_clipboard_item_bg_color": "#46FFFFFF",
    "ime_skin_dark_clipboard_item_bg_color": "#24FFFFFF",
}

LIFECYCLE_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;"
LIFECYCLE_RELATIVE_PATH = Path(
    "com/tencent/wetype/monet/ColorOSV2PanelLifecycleV8.smali"
)
RUNNABLE_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;"
RUNNABLE_RELATIVE_PATH = Path(
    "com/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable.smali"
)


LIFECYCLE_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeOplusV8"

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static reconcileRoot(Landroid/view/View;)V
    .locals 0
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->apply(Landroid/view/View;)V
    :return
    return-void
.end method

.method private static postReconcile(Landroid/view/View;)V
    .locals 2
    if-eqz p0, :return
    new-instance v0, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;
    invoke-direct {v0, p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;-><init>(Landroid/view/View;)V
    invoke-virtual {p0, v0}, Landroid/view/View;->post(Ljava/lang/Runnable;)Z
    move-result v1
    :return
    return-void
.end method

.method private static adaptPanel(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyTree(Landroid/view/View;)V
    :return
    return-void
.end method

.method public static onPanelAttached(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;->adaptPanel(Landroid/view/View;)V
    invoke-virtual {p0}, Landroid/view/View;->getRootView()Landroid/view/View;
    move-result-object v0
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;->postReconcile(Landroid/view/View;)V
    :return
    return-void
.end method

.method public static onPanelVisibilityChanged(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;->adaptPanel(Landroid/view/View;)V
    invoke-virtual {p0}, Landroid/view/View;->getRootView()Landroid/view/View;
    move-result-object v0
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;->postReconcile(Landroid/view/View;)V
    :return
    return-void
.end method

.method public static onPanelDetached(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    # Called before the panel's super.onDetachedFromWindow().  The posted
    # reconcile runs after the current detach transaction, when the panel is no
    # longer shown, allowing V6/V7 to restore the exact previous base/candidate
    # state without a persistent global-layout scan.
    invoke-virtual {p0}, Landroid/view/View;->getRootView()Landroid/view/View;
    move-result-object v0
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;->postReconcile(Landroid/view/View;)V
    :return
    return-void
.end method
'''


RUNNABLE_SMALI = r'''.class final Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;

.field private final root:Landroid/view/View;

.method constructor <init>(Landroid/view/View;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;->root:Landroid/view/View;
    return-void
.end method

.method public run()V
    .locals 1
    iget-object v0, p0, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;->root:Landroid/view/View;
    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;->reconcileRoot(Landroid/view/View;)V
    return-void
.end method
'''


_FIELD_PATTERN = re.compile(
    r"\.field\s+.*?\s+([a-zA-Z0-9_$]+):I\s*=\s*(0x7f[0-9a-fA-F]{6})",
    re.IGNORECASE,
)
_CONST_PATTERN = re.compile(
    r"const[/\w]*\s+v\d+,\s*(0x7f[0-9a-fA-F]{6})", re.IGNORECASE
)
_SPUT_PATTERN = re.compile(
    r"sput[/\w]*\s+v\d+,\s*L[^;]+;->([a-zA-Z0-9_$]+):I"
)
_PUBLIC_COLOR_PATTERN = re.compile(
    r'<public\s+type="color"\s+name="([^"]+)"\s+id="(0x7f[0-9a-fA-F]{6})"'
)


def _parse_all_hld_resource_ids(decompile_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for smali_root in Path(decompile_dir).glob("smali*"):
        target = smali_root / "com/tencent/wetype/plugin/hld"
        if not target.is_dir():
            continue
        for path in target.rglob("*.smali"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in _FIELD_PATTERN.finditer(text):
                result[match.group(1)] = match.group(2).lower()
            last_id: str | None = None
            for line in text.splitlines():
                const_match = _CONST_PATTERN.search(line)
                if const_match:
                    last_id = const_match.group(1).lower()
                    continue
                sput_match = _SPUT_PATTERN.search(line)
                if sput_match and last_id:
                    result[sput_match.group(1)] = last_id
                    last_id = None
    return result


def _public_colors(decompile_dir: Path) -> dict[str, str]:
    public = Path(decompile_dir) / "res/values/public.xml"
    if not public.is_file():
        raise RuntimeError(f"Missing decoded public.xml: {public}")
    result: dict[str, str] = {}
    for line in public.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = _PUBLIC_COLOR_PATTERN.search(line)
        if match:
            result[match.group(2).lower()] = match.group(1)
    return result


def _resolve_tool_surface_resources(decompile_dir: Path) -> dict[str, tuple[str, str]]:
    ids = _parse_all_hld_resource_ids(decompile_dir)
    public = _public_colors(decompile_dir)
    resolved: dict[str, tuple[str, str]] = {}
    missing: list[str] = []
    for semantic, color in WETYPE_TOOL_SURFACE_COLORS.items():
        rid = ids.get(semantic)
        name = public.get(rid or "")
        if not name:
            missing.append(semantic)
            continue
        resolved[name] = (semantic, color)
    if missing:
        raise RuntimeError(
            "V8 could not resolve WeType-Tool-proven surface resources: "
            + ", ".join(missing)
        )
    return resolved


def _apply_tool_surface_resources(decompile_dir: Path) -> dict[str, object]:
    root = Path(decompile_dir)
    targets = _resolve_tool_surface_resources(root)
    changed: dict[str, dict[str, str]] = {}
    files: set[str] = set()
    for values_dir in sorted((root / "res").glob("values*")):
        if not values_dir.is_dir():
            continue
        for path in sorted(values_dir.glob("*.xml")):
            if path.name == "public.xml":
                continue
            try:
                tree = ET.parse(path)
            except ET.ParseError:
                continue
            dirty = False
            for element in tree.getroot():
                tag = element.tag.rsplit("}", 1)[-1]
                if tag != "color" and not (
                    tag == "item" and element.get("type") == "color"
                ):
                    continue
                name = element.get("name")
                if name not in targets:
                    continue
                semantic, color = targets[name]
                old = (element.text or "").strip()
                element.text = color
                changed[name] = {"semantic": semantic, "old": old, "new": color}
                dirty = True
            if dirty:
                tree.write(path, encoding="utf-8", xml_declaration=True)
                files.add(str(path.relative_to(root)))

    unresolved = sorted(set(targets) - set(changed))
    if unresolved:
        raise RuntimeError(
            "V8 resolved WeType Tool surface names but did not find their color definitions: "
            + ", ".join(unresolved)
        )
    return {
        "release_sha256": WETYPE_TOOL_RELEASE_SHA256,
        "changed_resources": changed,
        "resource_files": sorted(files),
        "policy": (
            "emoji/full-tool full-surface gradients are clear over the single ColorOS root blur; "
            "clipboard items keep elevated neutral glass tint"
        ),
    }


def _descriptor_to_relative(class_name: str) -> Path:
    return Path(class_name.replace(".", "/") + ".smali")


def _find_class_file(decompile_dir: Path, class_name: str) -> Path | None:
    relative = _descriptor_to_relative(class_name)
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / relative
        if candidate.is_file():
            return candidate
    return None


def _super_descriptor(content: str) -> str:
    match = re.search(r"(?m)^\.super\s+(L[^;]+;)\s*$", content)
    if not match:
        raise RuntimeError("Could not resolve direct superclass while adding V8 lifecycle hooks")
    return match.group(1)


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


def _append_override(
    content: str,
    super_desc: str,
    method_name: str,
    signature: str,
    visibility: str,
    callback: str,
    callback_before_super: bool,
) -> str:
    if method_name == "setVisibility":
        args = "{p0, p1}"
    else:
        args = "{p0}"
    super_call = f"    invoke-super {args}, {super_desc}->{method_name}{signature}\n"
    callback_call = f"    invoke-static {{p0}}, {LIFECYCLE_DESCRIPTOR}->{callback}(Landroid/view/View;)V\n"
    body = callback_call + super_call if callback_before_super else super_call + callback_call
    method = (
        f"\n.method {visibility} {method_name}{signature}\n"
        "    .locals 0\n"
        f"{body}"
        "    return-void\n"
        ".end method\n"
    )
    return content.rstrip() + "\n" + method


def _patch_existing_method_returns(block: str, callback: str) -> tuple[str, int]:
    call = f"    invoke-static {{p0}}, {LIFECYCLE_DESCRIPTOR}->{callback}(Landroid/view/View;)V\n"
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


def _patch_existing_method_entry(block: str, callback: str) -> tuple[str, int]:
    call = f"    invoke-static {{p0}}, {LIFECYCLE_DESCRIPTOR}->{callback}(Landroid/view/View;)V\n"
    if call.strip() in block:
        return block, 0
    # Insert after .locals/.registers.  No temporary register is needed.
    pattern = re.compile(r"(?m)^(\s*\.(?:locals|registers)\s+\d+\s*)$")
    match = pattern.search(block)
    if not match:
        raise RuntimeError("Lifecycle method has no .locals/.registers directive")
    patched = block[: match.end()] + "\n" + call + block[match.end() :]
    return patched, 1


def _patch_one_panel_class(decompile_dir: Path, class_name: str) -> dict[str, object]:
    path = _find_class_file(decompile_dir, class_name)
    if path is None:
        raise RuntimeError(f"V8 audited panel class missing from decoded APK: {class_name}")
    content = path.read_text(encoding="utf-8")
    super_desc = _super_descriptor(content)
    operations: dict[str, str] = {}

    specs = (
        ("onAttachedToWindow", "()V", "protected", "onPanelAttached", False, "returns"),
        ("onDetachedFromWindow", "()V", "protected", "onPanelDetached", True, "entry"),
        ("setVisibility", "(I)V", "public", "onPanelVisibilityChanged", False, "returns"),
    )
    for method_name, signature, visibility, callback, before_super, mode in specs:
        located = _method_block(content, method_name, signature)
        if located is None:
            content = _append_override(
                content,
                super_desc,
                method_name,
                signature,
                visibility,
                callback,
                before_super,
            )
            operations[method_name] = "override_added"
            continue

        start, end = located
        block = content[start:end]
        if mode == "entry":
            patched, _ = _patch_existing_method_entry(block, callback)
        else:
            patched, _ = _patch_existing_method_returns(block, callback)
        content = content[:start] + patched + content[end:]
        operations[method_name] = "existing_method_hooked"

    path.write_text(content, encoding="utf-8")
    return {
        "class": class_name,
        "file": str(path.relative_to(decompile_dir)),
        "super": super_desc,
        "operations": operations,
    }


def _v5_result(visual_v7: dict[str, object]) -> dict[str, object]:
    v6 = visual_v7.get("base_v6")
    if not isinstance(v6, dict):
        raise RuntimeError("V7 result has no base_v6")
    v5 = v6.get("base_v5")
    if not isinstance(v5, dict):
        raise RuntimeError("V6 result has no base_v5")
    return v5


def _smali_root_from_v7(decompile_dir: Path, visual_v7: dict[str, object]) -> Path:
    v5 = _v5_result(visual_v7)
    injected = v5.get("injected_helpers")
    if not isinstance(injected, list) or not injected:
        raise RuntimeError("V5 result has no injected helper list")
    first = Path(decompile_dir) / str(injected[0])
    for parent in first.parents:
        if parent.parent == Path(decompile_dir) and parent.name.startswith("smali"):
            return parent
    raise RuntimeError(f"Could not resolve V8 smali root from {first}")


def _inject_v8_helpers(decompile_dir: Path, visual_v7: dict[str, object]) -> list[str]:
    root = _smali_root_from_v7(decompile_dir, visual_v7)
    result: list[str] = []
    for relative, text in (
        (LIFECYCLE_RELATIVE_PATH, LIFECYCLE_SMALI),
        (RUNNABLE_RELATIVE_PATH, RUNNABLE_SMALI),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        result.append(str(path.relative_to(decompile_dir)))
    return result


def _neutralize_global_layout(decompile_dir: Path, visual_v7: dict[str, object]) -> str:
    v5 = _v5_result(visual_v7)
    injected = v5.get("injected_helpers")
    assert isinstance(injected, list)
    listener_rel = next(
        (
            str(p)
            for p in injected
            if str(p).endswith("ColorOSV2Round$GlobalLayoutListener.smali")
        ),
        None,
    )
    if listener_rel is None:
        raise RuntimeError("V8 could not locate V5 global-layout listener")
    path = Path(decompile_dir) / listener_rel
    content = path.read_text(encoding="utf-8")
    located = _method_block(content, "onGlobalLayout", "()V")
    if located is None:
        raise RuntimeError("V8 could not locate onGlobalLayout()")
    start, end = located
    replacement = (
        ".method public onGlobalLayout()V\n"
        "    .locals 0\n"
        "    # V8 is event-driven.  This listener is retained only because V5\n"
        "    # already registered it before the V8 transform; doing no work here\n"
        "    # removes per-keystroke full-tree scans.\n"
        "    return-void\n"
        ".end method"
    )
    path.write_text(content[:start] + replacement + content[end:], encoding="utf-8")
    return listener_rel


def _patch_apply_runnable(decompile_dir: Path, visual_v7: dict[str, object]) -> str:
    v5 = _v5_result(visual_v7)
    runnable_rel = str(v5.get("runnable") or "")
    if not runnable_rel:
        raise RuntimeError("V8 could not locate root apply runnable")
    path = Path(decompile_dir) / runnable_rel
    content = path.read_text(encoding="utf-8")

    # V6/V7 were previously called separately on every delayed root apply.
    # Collapse them into one V8 reconciliation call.  The delayed applies are
    # only 0/250/700 ms attachment stabilization and are not a steady-state cost.
    v6_call = re.compile(
        r"(?m)^\s*invoke-static \{v0\}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;"
        r"->apply\(Landroid/view/View;\)V\s*$"
    )
    v7_call = re.compile(
        r"(?m)^\s*invoke-static \{v0\}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;"
        r"->apply\(Landroid/view/View;\)V\s*$"
    )
    had_v6 = bool(v6_call.search(content))
    had_v7 = bool(v7_call.search(content))
    if not had_v6 or not had_v7:
        raise RuntimeError("V8 expected the V6 and V7 delayed reconciliation calls")
    content = v6_call.sub("", content)
    content = v7_call.sub("", content)

    call = (
        "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;"
        "->reconcileRoot(Landroid/view/View;)V\n"
    )
    # Place after ColorOSV2Round.install so system-font/G2 adaptation exists.
    anchor = re.compile(
        r"(?m)^(?P<line>\s*invoke-static \{v0\}, Lcom/tencent/wetype/monet/ColorOSV2Round;"
        r"->install\(Landroid/view/View;\)V\s*)$"
    )
    match = anchor.search(content)
    if not match:
        raise RuntimeError("V8 could not find ColorOSV2Round.install in apply runnable")
    content = content[: match.end()] + "\n" + call.rstrip("\n") + content[match.end() :]
    path.write_text(content, encoding="utf-8")
    return runnable_rel


def _patch_panel_lifecycles(decompile_dir: Path) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for class_name in base.OWN_CHROME_PANEL_CLASSES:
        reports.append(_patch_one_panel_class(decompile_dir, class_name))
    return reports


def apply_coloros_v2_visual_profile_v8(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    visual_v7 = base.apply_coloros_v2_visual_profile_v7(decompile_dir, patch_report)

    resources = _apply_tool_surface_resources(decompile_dir)
    helpers = _inject_v8_helpers(decompile_dir, visual_v7)
    panels = _patch_panel_lifecycles(decompile_dir)
    listener = _neutralize_global_layout(decompile_dir, visual_v7)
    runnable = _patch_apply_runnable(decompile_dir, visual_v7)

    if len(panels) != len(base.OWN_CHROME_PANEL_CLASSES):
        raise RuntimeError("V8 did not hook every audited own-chrome panel")

    return {
        "strategy": (
            "WeType Tool v1.3.2 hook-surface map + ColorOS native material: "
            "single FAST_KAWASE root, G2/V2 geometry, self-draw Normal/Pressed state, "
            "event-driven tool hierarchy"
        ),
        "base_v7": visual_v7,
        "wetype_tool_evidence": {
            "release_sha256": WETYPE_TOOL_RELEASE_SHA256,
            "borrowed_surfaces": [
                "keyboardBlurInitMethod / keyboardBlurRootViewField",
                "keyRuntimeStyleBinder / keyRuntimeCornerSetter / keyRuntimeShadowSetter",
                "keyPressBubbleConfigConstructor / keyPressBubbleCornerField",
                "toolbarInvokeMethod / toolbarFunctionField / toolbarCategoryField",
                "candidate background/bind/item-root hooks",
                "floating keyboard root/content/state/visibility hooks",
                "emoji/full-gradient + clipboard-item resource surfaces",
            ],
            "implementation_policy": (
                "borrow hook locations/lifecycle architecture only; retain ColorOS private "
                "ViewRootManager/OplusBlurParam compositor material instead of WeType Tool blur"
            ),
        },
        "tool_surfaces": resources,
        "panel_lifecycle": {
            "hooked_classes": panels,
            "count": len(panels),
            "global_layout_listener": listener,
            "steady_state_global_layout_work": "none (onGlobalLayout returns immediately)",
            "root_apply_runnable": runnable,
            "helpers": helpers,
            "reconcile_policy": (
                "V6/V7 recursive reconciliation runs only on audited panel attach/detach/visibility "
                "events and the three existing root attachment stabilization applies"
            ),
        },
        "performance_contract": {
            "compositor_blur_instances": 1,
            "per_key_viewroot_blur_instances": 0,
            "per_key_layout_tree_scan": False,
            "pressed_key_path": "existing self-draw pressMaskColor branch",
            "panel_scan_frequency": "lifecycle/visibility changes only",
        },
        "confidence_boundary": (
            "Build-time assertions prove every audited class/resource is present and hooked, and CI "
            "proves smali assembly/signature validity. Final visual correctness across every tool "
            "transition still requires one ColorOS 17 device pass; no static analysis can honestly "
            "make that hardware/rendering observation 100%."
        ),
    }
