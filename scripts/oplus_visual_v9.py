#!/usr/bin/env python3
"""V9: fix full-tool stacking and make overlay restoration lifecycle-complete.

ColorOS V8 deliberately removed the expensive global-layout tree walk. Device
feedback then exposed two consequences of making that optimization too early:

* clipboard/custom phrase (S15) and inspiration (S31) are full replacement
  keyboards just like emoji, but V6 only suppressed the base self-draw keyboard
  for emoji. Their own content was therefore composited on top of the still
  visible QWERTY keyboard;
* an emoji exit can change effective visibility through an ancestor. V8 only
  watched attach/detach and setVisibility on the exact audited panel classes,
  so one transition can miss the restore edge and leave the base keyboard at
  alpha 0 indefinitely.

V9 keeps the low-overhead V8 architecture and fixes the state model instead of
bringing the global-layout scan back:

1. A single overlay hierarchy owns base-keyboard suppression for *all* audited
   own-chrome replacement keyboards, not only emoji. V6's emoji-only helper is
   no longer called at runtime, avoiding two independent alpha restore maps.
2. Every audited panel also observes onVisibilityChanged, window visibility and
   alpha changes. Android dispatches onVisibilityChanged to descendants when
   an ancestor changes visibility, covering the transition that the exact
   setVisibility override missed.
3. Reconciliation is posted immediately and once more 48 ms later. The second
   event is a transition-only safety net after detach/visibility animations;
   there is still no per-layout or per-key scan.
4. Effective overlay visibility checks alpha along the ancestor chain, so a
   panel that remains VISIBLE but has been faded to alpha 0 cannot keep the base
   keyboard suppressed.

Normal/pressed key rendering, ColorOS FAST_KAWASE ownership and V7 candidate
suppression are unchanged.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

try:
    import oplus_visual_v8b as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v8b.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v8b", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V8b pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


# v8b.base -> v8, v8.base -> v7.
V8 = base.base
V7 = V8.base
PANEL_CLASSES = tuple(V7.OWN_CHROME_PANEL_CLASSES)

OVERLAY_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;"
OVERLAY_RELATIVE_PATH = Path(
    "com/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9.smali"
)
V8_LIFECYCLE_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;"


def _overlay_class_checks() -> str:
    lines: list[str] = []
    for class_name in PANEL_CLASSES:
        lines.extend(
            (
                f'    const-string v0, "{class_name}"',
                "    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z",
                "    move-result v0",
                "    if-nez v0, :yes",
            )
        )
    return "\n".join(lines)


def _overlay_helper_smali() -> str:
    return r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;
.super Ljava/lang/Object;

.field private static final suppressedAlpha:Ljava/util/WeakHashMap;

.method static constructor <clinit>()V
    .locals 1
    new-instance v0, Ljava/util/WeakHashMap;
    invoke-direct {v0}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v0, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->suppressedAlpha:Ljava/util/WeakHashMap;
    return-void
.end method

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method private static isOverlayClass(Ljava/lang/String;)Z
    .locals 1
''' + _overlay_class_checks() + r'''
    const/4 v0, 0x0
    return v0
    :yes
    const/4 v0, 0x1
    return v0
.end method

# View.isShown() intentionally ignores alpha. Some WeType transitions keep a
# panel VISIBLE while fading an ancestor, so check alpha up the View ancestry as
# part of the effective-visibility predicate.
.method private static isEffectivelyShown(Landroid/view/View;)Z
    .locals 4
    if-eqz p0, :no
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :no
    :loop
    invoke-virtual {p0}, Landroid/view/View;->getVisibility()I
    move-result v0
    if-nez v0, :no
    invoke-virtual {p0}, Landroid/view/View;->getAlpha()F
    move-result v0
    const v1, 0x3c23d70a    # 0.01f
    cmpl-float v2, v0, v1
    if-lez v2, :no
    invoke-virtual {p0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v3
    instance-of v0, v3, Landroid/view/View;
    if-eqz v0, :yes
    check-cast v3, Landroid/view/View;
    move-object p0, v3
    goto :loop
    :yes
    const/4 v0, 0x1
    return v0
    :no
    const/4 v0, 0x0
    return v0
.end method

.method private static hasActiveOverlay(Landroid/view/View;)Z
    .locals 5
    if-eqz p0, :no
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->isEffectivelyShown(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :children
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v1
    invoke-virtual {v1}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v2
    invoke-static {v2}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->isOverlayClass(Ljava/lang/String;)Z
    move-result v3
    if-nez v3, :yes
    :children
    instance-of v0, p0, Landroid/view/ViewGroup;
    if-eqz v0, :no
    check-cast p0, Landroid/view/ViewGroup;
    invoke-virtual {p0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v1
    const/4 v2, 0x0
    :loop
    if-ge v2, v1, :no
    invoke-virtual {p0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v3
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->hasActiveOverlay(Landroid/view/View;)Z
    move-result v4
    if-nez v4, :yes
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :yes
    const/4 v0, 0x1
    return v0
    :no
    const/4 v0, 0x0
    return v0
.end method

.method private static isBaseSelfDrawKeyboard(Landroid/view/View;)Z
    .locals 5
    if-eqz p0, :no
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v1
    const-string v2, "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S"
    invoke-virtual {v1, v2}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v3
    if-eqz v3, :no
    const-string v2, "Keyboard"
    invoke-virtual {v1, v2}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v3
    if-eqz v3, :no
    # An own-chrome self-draw keyboard (currently S11 Emoji) is the overlay,
    # never the underlying keyboard that should be suppressed.
    invoke-static {v1}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->isOverlayClass(Ljava/lang/String;)Z
    move-result v4
    if-nez v4, :no
    const/4 v0, 0x1
    return v0
    :no
    const/4 v0, 0x0
    return v0
.end method

.method private static updateBaseKeyboards(Landroid/view/View;Z)V
    .locals 7
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->isBaseSelfDrawKeyboard(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :children
    sget-object v1, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->suppressedAlpha:Ljava/util/WeakHashMap;
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
    invoke-static {v3, p1}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->updateBaseKeyboards(Landroid/view/View;Z)V
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :return
    return-void
.end method

.method public static apply(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->hasActiveOverlay(Landroid/view/View;)Z
    move-result v0
    invoke-static {p0, v0}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->updateBaseKeyboards(Landroid/view/View;Z)V
    :return
    return-void
.end method
'''


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


def _v8_smali_root(decompile_dir: Path, visual_v8: dict[str, object]) -> Path:
    lifecycle = visual_v8.get("panel_lifecycle")
    if not isinstance(lifecycle, dict):
        raise RuntimeError("V8 result has no panel_lifecycle block")
    helpers = lifecycle.get("helpers")
    if not isinstance(helpers, list) or not helpers:
        raise RuntimeError("V8 result has no lifecycle helper paths")
    first = Path(decompile_dir) / str(helpers[0])
    for parent in first.parents:
        if parent.parent == Path(decompile_dir) and parent.name.startswith("smali"):
            return parent
    raise RuntimeError(f"Could not resolve V9 smali root from {first}")


def _inject_overlay_helper(
    decompile_dir: Path, visual_v8: dict[str, object]
) -> str:
    smali_root = _v8_smali_root(Path(decompile_dir), visual_v8)
    path = smali_root / OVERLAY_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_overlay_helper_smali(), encoding="utf-8")
    return str(path.relative_to(decompile_dir))


def _lifecycle_helper_path(
    decompile_dir: Path, visual_v8: dict[str, object]
) -> Path:
    lifecycle = visual_v8.get("panel_lifecycle")
    assert isinstance(lifecycle, dict)
    helpers = lifecycle.get("helpers")
    assert isinstance(helpers, list)
    for rel in helpers:
        if str(rel).endswith("ColorOSV2PanelLifecycleV8.smali"):
            return Path(decompile_dir) / str(rel)
    raise RuntimeError("V9 could not locate V8 lifecycle helper")


def _replace_reconcile_root(content: str) -> str:
    located = _method_block(content, "reconcileRoot", "(Landroid/view/View;)V")
    if located is None:
        raise RuntimeError("V9 could not locate V8 reconcileRoot")
    start, end = located
    replacement = r'''.method public static reconcileRoot(Landroid/view/View;)V
    .locals 0
    if-eqz p0, :return
    # V9 owns base-keyboard suppression for every full overlay. Do not call
    # V6 here: its emoji-only WeakHashMap would create a second alpha owner and
    # can restore the 0 written by another owner instead of the real alpha.
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2OverlayHierarchyV9;->apply(Landroid/view/View;)V
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->apply(Landroid/view/View;)V
    :return
    return-void
.end method'''
    return content[:start] + replacement + content[end:]


def _replace_post_reconcile(content: str) -> str:
    located = _method_block(content, "postReconcile", "(Landroid/view/View;)V")
    if located is None:
        raise RuntimeError("V9 could not locate V8 postReconcile")
    start, end = located
    replacement = r'''.method private static postReconcile(Landroid/view/View;)V
    .locals 4
    if-eqz p0, :return
    new-instance v0, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;
    invoke-direct {v0, p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;-><init>(Landroid/view/View;)V
    invoke-virtual {p0, v0}, Landroid/view/View;->post(Ljava/lang/Runnable;)Z
    move-result v3
    # Detach/visibility animations can report the callback before the old panel
    # has left the effective hierarchy. One delayed transition-only repair is
    # cheap and guarantees the final state without restoring global-layout work.
    new-instance v0, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;
    invoke-direct {v0, p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8$ReconcileRunnable;-><init>(Landroid/view/View;)V
    const-wide/16 v1, 0x30    # 48 ms
    invoke-virtual {p0, v0, v1, v2}, Landroid/view/View;->postDelayed(Ljava/lang/Runnable;J)Z
    move-result v3
    :return
    return-void
.end method'''
    return content[:start] + replacement + content[end:]


def _upgrade_lifecycle_helper(
    decompile_dir: Path, visual_v8: dict[str, object]
) -> str:
    path = _lifecycle_helper_path(decompile_dir, visual_v8)
    content = path.read_text(encoding="utf-8")
    content = _replace_reconcile_root(content)
    content = _replace_post_reconcile(content)
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(decompile_dir))


def _find_class_file(decompile_dir: Path, class_name: str) -> Path | None:
    relative = Path(class_name.replace(".", "/") + ".smali")
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        candidate = smali_root / relative
        if candidate.is_file():
            return candidate
    return None


def _super_descriptor(content: str) -> str:
    match = re.search(r"(?m)^\.super\s+(L[^;]+;)\s*$", content)
    if not match:
        raise RuntimeError("Could not resolve panel superclass for V9 visibility hook")
    return match.group(1)


def _callback_call() -> str:
    return (
        "    invoke-static {p0}, "
        "Lcom/tencent/wetype/monet/ColorOSV2PanelLifecycleV8;"
        "->onPanelVisibilityChanged(Landroid/view/View;)V\n"
    )


def _patch_returns(block: str) -> tuple[str, int]:
    call = _callback_call()
    if call.strip() in block:
        return block, 0
    count = len(re.findall(r"(?m)^\s*return-void\s*$", block))
    if count == 0:
        raise RuntimeError("V9 visibility lifecycle method has no return-void")
    patched = re.sub(
        r"(?m)^(?P<indent>\s*)return-void\s*$",
        lambda m: call + f"{m.group('indent')}return-void",
        block,
    )
    return patched, count


def _append_visibility_override(
    content: str,
    super_desc: str,
    method_name: str,
    signature: str,
    visibility: str,
) -> str:
    if signature == "(Landroid/view/View;I)V":
        args = "{p0, p1, p2}"
    else:
        args = "{p0, p1}"
    method = (
        f"\n.method {visibility} {method_name}{signature}\n"
        "    .locals 0\n"
        f"    invoke-super {args}, {super_desc}->{method_name}{signature}\n"
        + _callback_call()
        + "    return-void\n"
        ".end method\n"
    )
    return content.rstrip() + "\n" + method


def _patch_panel_effective_visibility(
    decompile_dir: Path, class_name: str
) -> dict[str, object]:
    path = _find_class_file(decompile_dir, class_name)
    if path is None:
        raise RuntimeError(f"V9 audited panel class missing: {class_name}")
    content = path.read_text(encoding="utf-8")
    super_desc = _super_descriptor(content)
    operations: dict[str, str] = {}
    specs = (
        ("onVisibilityChanged", "(Landroid/view/View;I)V", "protected"),
        ("onWindowVisibilityChanged", "(I)V", "protected"),
        ("setAlpha", "(F)V", "public"),
    )
    for method_name, signature, visibility in specs:
        located = _method_block(content, method_name, signature)
        if located is None:
            content = _append_visibility_override(
                content, super_desc, method_name, signature, visibility
            )
            operations[method_name] = "override_added"
            continue
        start, end = located
        block = content[start:end]
        patched, _ = _patch_returns(block)
        content = content[:start] + patched + content[end:]
        operations[method_name] = "existing_method_hooked"
    path.write_text(content, encoding="utf-8")
    return {
        "class": class_name,
        "file": str(path.relative_to(decompile_dir)),
        "super": super_desc,
        "operations": operations,
    }


def _patch_all_panel_effective_visibility(
    decompile_dir: Path,
) -> list[dict[str, object]]:
    return [
        _patch_panel_effective_visibility(decompile_dir, class_name)
        for class_name in PANEL_CLASSES
    ]


def _audit_v9_runtime_calls(decompile_dir: Path) -> dict[str, int]:
    v6_calls = 0
    v9_calls = 0
    lifecycle_visibility_calls = 0
    for smali_root in sorted(Path(decompile_dir).glob("smali*")):
        for path in smali_root.rglob("*.smali"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            v6_calls += text.count(
                "ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V"
            )
            v9_calls += text.count(
                "ColorOSV2OverlayHierarchyV9;->apply(Landroid/view/View;)V"
            )
            lifecycle_visibility_calls += text.count(
                "ColorOSV2PanelLifecycleV8;->onPanelVisibilityChanged(Landroid/view/View;)V"
            )
    if v6_calls != 0:
        raise RuntimeError(
            f"V9 expected zero runtime V6 hierarchy callers, found {v6_calls}"
        )
    if v9_calls != 1:
        raise RuntimeError(
            f"V9 expected exactly one overlay hierarchy caller, found {v9_calls}"
        )
    # V8 already added setVisibility callbacks and V9 adds three more effective
    # visibility callbacks per audited panel. Require at least four each; exact
    # counts can be higher when an upstream class already has multiple returns.
    minimum = len(PANEL_CLASSES) * 4
    if lifecycle_visibility_calls < minimum:
        raise RuntimeError(
            "V9 lifecycle hook coverage too small: "
            f"{lifecycle_visibility_calls} < {minimum}"
        )
    return {
        "v6_apply_callers": v6_calls,
        "v9_overlay_apply_callers": v9_calls,
        "panel_visibility_callback_sites": lifecycle_visibility_calls,
    }


def apply_coloros_v2_visual_profile_v9(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    visual_v8 = base.apply_coloros_v2_visual_profile_v8(decompile_dir, patch_report)

    helper = _inject_overlay_helper(decompile_dir, visual_v8)
    lifecycle = _upgrade_lifecycle_helper(decompile_dir, visual_v8)
    panels = _patch_all_panel_effective_visibility(decompile_dir)
    audit = _audit_v9_runtime_calls(decompile_dir)

    return {
        "strategy": (
            "V8b ColorOS material + WeType Tool lifecycle map, with one V9 overlay owner "
            "for all full replacement keyboards and lifecycle-complete restoration"
        ),
        "base_v8": visual_v8,
        "device_regressions_fixed": {
            "clipboard_common_phrase": (
                "S15 now suppresses the underlying self-draw keyboard while visible"
            ),
            "inspiration": (
                "S31 now suppresses the underlying self-draw keyboard while visible"
            ),
            "emoji_return": (
                "V9 is the sole base-alpha owner; ancestor/window/alpha visibility hooks plus "
                "a 48 ms transition repair restore the exact pre-overlay alpha"
            ),
        },
        "overlay_hierarchy": {
            "helper": helper,
            "full_overlay_classes": list(PANEL_CLASSES),
            "base_keyboard_match": (
                "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S*Keyboard excluding any "
                "audited overlay class"
            ),
            "restore_storage": "WeakHashMap<View, Float>, exact previous alpha",
            "effective_visibility": (
                "View.isShown + visibility/alpha check along the ancestor View chain"
            ),
        },
        "lifecycle_repair": {
            "helper": lifecycle,
            "panels": panels,
            "new_events": [
                "onVisibilityChanged(View,int)",
                "onWindowVisibilityChanged(int)",
                "setAlpha(float)",
            ],
            "reconcile_schedule": "post immediately + one postDelayed at 48 ms",
            "steady_state_global_layout_work": "none",
        },
        "runtime_audit": audit,
        "performance_contract": {
            "steady_state_tree_scans_per_key": 0,
            "global_layout_tree_scan": False,
            "compositor_blur_instances": 1,
            "per_key_viewroot_blur_instances": 0,
            "transition_only_reconciliation": True,
        },
        "confidence_boundary": (
            "Static transformation, call-site audit, apktool assembly and signature checks can "
            "prove the state machine is wired as intended. Device rendering is validated only "
            "after the resulting APK is exercised across emoji, clipboard/common phrase and "
            "inspiration transitions on ColorOS 17."
        ),
    }
