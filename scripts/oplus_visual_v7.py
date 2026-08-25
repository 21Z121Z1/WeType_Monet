#!/usr/bin/env python3
"""V7: finish WeType panel hierarchy and pressed-material parity.

This pass is based on two independently verified facts from the 3.5.3 (56201)
WeType APK and com.oplus.keyboard 15.17.238:

* WeType's normal keys are not individual Android Views.  S* self-draw
  keyboards render KeyData/runtime-j objects into one custom View.  KeyData
  already carries bgColor, bgCorner, shadowColor, shadowHeight and
  pressMaskColor, and drawmethod/c switches the press layer when the runtime
  key state string is "press".
* Oplus/Breeno uses the same architectural model for its main keyboard body:
  com.oplus.keyboard.input.view.body.s is one custom View.  Its
  h(softKey, pressed) method selects separate theme Drawables such as
  bgKeyNormalBlur/bgKeyPressedBlur, bgFuncKeyNormal/bgFuncKeyPressed and
  bgEnterOtherNormal/bgEnterOtherPressed.

Therefore V7 does NOT invent per-key ViewRootManager instances.  It maps
WeType's existing pressed-state resources to neutral ColorOS-like material
state tints, while the already-working root FAST_KAWASE blur remains the
compositor blur owner.

V7 also fixes the last visible z-order leak.  ImeCandidateView is a sibling of
replacement keyboard content in ImeRootView.  Emoji, clipboard/custom phrase,
Ask AI and several full-tool keyboards already provide their own top chrome;
when one of those roots is visible, the global candidate/toolbar must be
INVISIBLE.  Panels that intentionally depend on the global candidate area
(e.g. S20CorrectionKeyboard / spelling correction) are explicitly preserved.
"""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import oplus_visual_v6 as base
except ModuleNotFoundError:
    _BASE_PATH = Path(__file__).resolve().with_name("oplus_visual_v6.py")
    _BASE_SPEC = importlib.util.spec_from_file_location("oplus_visual_v6", _BASE_PATH)
    if _BASE_SPEC is None or _BASE_SPEC.loader is None:
        raise RuntimeError(f"Could not load sibling V6 pass: {_BASE_PATH}")
    base = importlib.util.module_from_spec(_BASE_SPEC)
    _BASE_SPEC.loader.exec_module(base)


PANEL_HELPER_DESCRIPTOR = "Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;"
PANEL_HELPER_RELATIVE_PATH = Path(
    "com/tencent/wetype/monet/ColorOSV2PanelHierarchyV7.smali"
)

# Exact roots proven by the decoded layouts/class hierarchy to own their own
# toolbar/header.  The l/n-derived classes expose getDescTitle/getDescTipsText
# and build their own chrome; S15/S24/S25/S30/S32 have explicit top rows in
# their binary XML.  Emoji has its own board header.
OWN_CHROME_PANEL_CLASSES = (
    "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S11EmojiKeyboard",
    "com.tencent.wetype.plugin.hld.emoji.ImeEmojiBoardView",
    "com.tencent.wetype.plugin.hld.emoji.ImeEmojiShowBoardView",
    "com.tencent.wetype.plugin.hld.keyboard.S15CustomPhraseAndClipboardKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S21RecordPermissionKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S24NetworkSettingKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S25PrivacySettingKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S30KeyboardChooseKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S31InspirationKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S32PCSettingKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S33ImagePreviewKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S34ClipboardBombKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S35RequestAIKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S37ProductActivityKeyboard",
)

# Audited replacement keyboards that deliberately keep the global candidate
# area.  Most importantly, S20's eb.xml has only correction content/state and
# no local header, so hiding ImeCandidateView there would be a regression.
KEEP_GLOBAL_CANDIDATE_CLASSES = (
    "com.tencent.wetype.plugin.hld.keyboard.S10SettingsKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S19RecommendKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S20CorrectionKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S29ClipboardCleanRecordKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S36GameKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S6AlternativeWordsKeyboard",
    "com.tencent.wetype.plugin.hld.keyboard.S100DebugKeyboard",
)

PANEL_AUDIT = {
    "emoji": {
        "class": "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S11EmojiKeyboard",
        "policy": "hide_global_candidate",
        "evidence": "e0.xml owns ImeEmojiBoardView/pager/type bar; candidate toolbar is a sibling",
    },
    "clipboard_custom_phrase": {
        "class": "com.tencent.wetype.plugin.hld.keyboard.S15CustomPhraseAndClipboardKeyboard",
        "policy": "hide_global_candidate",
        "evidence": "e6.xml owns back button + TabContainerView header",
    },
    "spelling_correction": {
        "class": "com.tencent.wetype.plugin.hld.keyboard.S20CorrectionKeyboard",
        "policy": "keep_global_candidate",
        "evidence": "eb.xml contains correction ScrollView/CorrectStateView only; no local header",
    },
    "ask_ai": {
        "class": "com.tencent.wetype.plugin.hld.keyboard.S35RequestAIKeyboard",
        "policy": "hide_global_candidate",
        "evidence": "ep.xml owns an explicit header plus RequestAi content",
    },
}

# WeType already references these six pressed colors from KeyData.pressMaskColor
# (assets keyboard/output/*.json).  Neutral overlays preserve the root blur
# while giving the pressed state its own material response, instead of falling
# back to Monet hue.
PRESSED_STATE_COLORS = {
    "ime_skin_color_btn_white_press": "#5EFFFFFF",
    "ime_skin_dark_color_btn_white_press": "#46FFFFFF",
    "ime_skin_color_btn_grey_press": "#26000000",
    "ime_skin_dark_color_btn_grey_press": "#46FFFFFF",
    "ime_skin_color_btn_green_press": "#26000000",
    "ime_skin_dark_color_btn_green_press": "#46FFFFFF",
}

# The key preview/long-click bubble is a separate float-view surface, not the
# normal/pressed key drawable.  Make that surface opaque so it cannot expose
# the app/video through itself.  click_color remains a restrained state overlay.
KEY_PREVIEW_COLORS = {
    "ime_skin_key_float_view_upper_bg_color": "#FFFFFFFF",
    "ime_skin_dark_key_float_view_upper_bg_color": "#FF2C2C2E",
    "ime_skin_key_float_view_long_click_bg_color": "#FFFFFFFF",
    "ime_skin_dark_key_float_view_long_click_bg_color": "#FF2C2C2E",
    "ime_skin_key_float_view_click_color": "#22000000",
    "ime_skin_dark_key_float_view_click_color": "#2EFFFFFF",
}

EXTRA_STATE_COLORS = {**PRESSED_STATE_COLORS, **KEY_PREVIEW_COLORS}


PANEL_HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;
.super Ljava/lang/Object;

.field private static final candidateVisibility:Ljava/util/WeakHashMap;

.method static constructor <clinit>()V
    .locals 1
    new-instance v0, Ljava/util/WeakHashMap;
    invoke-direct {v0}, Ljava/util/WeakHashMap;-><init>()V
    sput-object v0, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->candidateVisibility:Ljava/util/WeakHashMap;
    return-void
.end method

.method private constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method private static isOwnChromeClass(Ljava/lang/String;)Z
    .locals 1
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S11EmojiKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.emoji.ImeEmojiBoardView"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.emoji.ImeEmojiShowBoardView"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S15CustomPhraseAndClipboardKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S21RecordPermissionKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S24NetworkSettingKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S25PrivacySettingKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S30KeyboardChooseKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S31InspirationKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S32PCSettingKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S33ImagePreviewKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S34ClipboardBombKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S35RequestAIKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const-string v0, "com.tencent.wetype.plugin.hld.keyboard.S37ProductActivityKeyboard"
    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :yes
    const/4 v0, 0x0
    return v0
    :yes
    const/4 v0, 0x1
    return v0
.end method

.method private static hasOwnChromePanel(Landroid/view/View;)Z
    .locals 5
    if-eqz p0, :no
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :children
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v1
    invoke-virtual {v1}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v2
    invoke-static {v2}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->isOwnChromeClass(Ljava/lang/String;)Z
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
    invoke-static {v3}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->hasOwnChromePanel(Landroid/view/View;)Z
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

.method private static isCandidateView(Landroid/view/View;)Z
    .locals 3
    if-eqz p0, :no
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/Class;->getName()Ljava/lang/String;
    move-result-object v1
    const-string v2, "com.tencent.wetype.plugin.hld.candidate.ImeCandidateView"
    invoke-virtual {v1, v2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    return v0
    :no
    const/4 v0, 0x0
    return v0
.end method

.method private static updateCandidates(Landroid/view/View;Z)V
    .locals 7
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->isCandidateView(Landroid/view/View;)Z
    move-result v0
    if-eqz v0, :children
    sget-object v1, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->candidateVisibility:Ljava/util/WeakHashMap;
    if-eqz p1, :restore

    invoke-virtual {v1, p0}, Ljava/util/WeakHashMap;->containsKey(Ljava/lang/Object;)Z
    move-result v2
    if-nez v2, :force_hidden
    invoke-virtual {p0}, Landroid/view/View;->getVisibility()I
    move-result v3
    if-nez v3, :return
    invoke-static {v3}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;
    move-result-object v4
    invoke-virtual {v1, p0, v4}, Ljava/util/WeakHashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;

    :force_hidden
    const/4 v5, 0x4
    invoke-virtual {p0, v5}, Landroid/view/View;->setVisibility(I)V
    goto :return

    :restore
    invoke-virtual {v1, p0}, Ljava/util/WeakHashMap;->remove(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v2
    if-eqz v2, :return
    check-cast v2, Ljava/lang/Integer;
    invoke-virtual {v2}, Ljava/lang/Integer;->intValue()I
    move-result v3
    invoke-virtual {p0, v3}, Landroid/view/View;->setVisibility(I)V
    goto :return

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
    invoke-static {v3, p1}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->updateCandidates(Landroid/view/View;Z)V
    add-int/lit8 v2, v2, 0x1
    goto :loop

    :return
    return-void
.end method

.method public static apply(Landroid/view/View;)V
    .locals 1
    if-eqz p0, :return
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->hasOwnChromePanel(Landroid/view/View;)Z
    move-result v0
    invoke-static {p0, v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->updateCandidates(Landroid/view/View;Z)V
    :return
    return-void
.end method
'''


def _parse_hld_key_ids(decompile_dir: Path) -> dict[str, str]:
    field_pattern = re.compile(
        r"\.field\s+.*?\s+([a-zA-Z0-9_$]+):I\s*=\s*(0x7f[0-9a-fA-F]{6})",
        re.IGNORECASE,
    )
    const_pattern = re.compile(
        r"const[/\w]*\s+v\d+,\s*(0x7f[0-9a-fA-F]{6})", re.IGNORECASE
    )
    sput_pattern = re.compile(
        r"sput[/\w]*\s+v\d+,\s*L[^;]+;->([a-zA-Z0-9_$]+):I"
    )
    result: dict[str, str] = {}
    hld = Path("com/tencent/wetype/plugin/hld")
    for smali_root in Path(decompile_dir).glob("smali*"):
        target = smali_root / hld
        if not target.is_dir():
            continue
        for path in target.glob("*.smali"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in field_pattern.finditer(text):
                result[match.group(1)] = match.group(2).lower()
            last_id = None
            for line in text.splitlines():
                const_match = const_pattern.search(line)
                if const_match:
                    last_id = const_match.group(1).lower()
                    continue
                sput_match = sput_pattern.search(line)
                if sput_match and last_id:
                    result[sput_match.group(1)] = last_id
                    last_id = None
    return result


def _public_color_names(decompile_dir: Path) -> dict[str, str]:
    path = Path(decompile_dir) / "res/values/public.xml"
    if not path.is_file():
        raise RuntimeError(f"Missing decoded public.xml: {path}")
    pattern = re.compile(
        r'<public\s+type="color"\s+name="([^"]+)"\s+id="(0x7f[0-9a-fA-F]{6})"'
    )
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.search(line)
        if match:
            result[match.group(2).lower()] = match.group(1)
    return result


def _resolve_extra_state_colors(decompile_dir: Path) -> dict[str, tuple[str, str]]:
    key_ids = _parse_hld_key_ids(decompile_dir)
    public = _public_color_names(decompile_dir)
    resolved: dict[str, tuple[str, str]] = {}
    missing: list[str] = []
    for semantic, color in EXTRA_STATE_COLORS.items():
        resource_id = key_ids.get(semantic)
        resource_name = public.get(resource_id or "")
        if not resource_name:
            missing.append(semantic)
            continue
        resolved[resource_name] = (semantic, color)
    if missing:
        raise RuntimeError(
            "V7 could not resolve pressed/preview color resources: " + ", ".join(missing)
        )
    return resolved


def _apply_extra_state_colors(decompile_dir: Path) -> dict[str, object]:
    root = Path(decompile_dir)
    targets = _resolve_extra_state_colors(root)
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

    missing_names = sorted(set(targets) - set(changed))
    if missing_names:
        raise RuntimeError(
            "V7 resolved resources but did not find decoded color definitions: "
            + ", ".join(missing_names)
        )
    return {
        "changed_resources": changed,
        "resource_files": sorted(files),
        "pressed_state_semantics": list(PRESSED_STATE_COLORS),
        "preview_semantics": list(KEY_PREVIEW_COLORS),
    }


def _v5_result(visual_v6: dict[str, object]) -> dict[str, object]:
    result = visual_v6.get("base_v5")
    if not isinstance(result, dict):
        raise RuntimeError("V6 result does not contain base_v5")
    return result


def _smali_root(decompile_dir: Path, visual_v6: dict[str, object]) -> Path:
    v5 = _v5_result(visual_v6)
    injected = v5.get("injected_helpers")
    if not isinstance(injected, list) or not injected:
        raise RuntimeError("V5 result has no injected helpers")
    first = Path(decompile_dir) / str(injected[0])
    for parent in first.parents:
        if parent.parent == Path(decompile_dir) and parent.name.startswith("smali"):
            return parent
    raise RuntimeError(f"Could not resolve smali root from {first}")


def _inject_panel_helper(
    decompile_dir: Path, visual_v6: dict[str, object]
) -> str:
    smali_root = _smali_root(Path(decompile_dir), visual_v6)
    path = smali_root / PANEL_HELPER_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PANEL_HELPER_SMALI, encoding="utf-8")
    return str(path.relative_to(decompile_dir))


def _patch_panel_hooks(
    decompile_dir: Path, visual_v6: dict[str, object]
) -> dict[str, str]:
    root = Path(decompile_dir)
    v5 = _v5_result(visual_v6)
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
        raise RuntimeError("Could not locate V5 global-layout listener")
    call = (
        "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;"
        "->apply(Landroid/view/View;)V\n"
    )

    listener = root / listener_rel
    text = listener.read_text(encoding="utf-8")
    if call.strip() not in text:
        anchor = (
            "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;"
            "->apply(Landroid/view/View;)V\n"
        )
        if anchor not in text:
            raise RuntimeError("Could not locate V6 hierarchy hook in global-layout listener")
        text = text.replace(anchor, anchor + call, 1)
        listener.write_text(text, encoding="utf-8")

    runnable_rel = str(v5.get("runnable") or "")
    if not runnable_rel:
        raise RuntimeError("V5 result has no apply runnable")
    runnable = root / runnable_rel
    rtext = runnable.read_text(encoding="utf-8")
    if call.strip() not in rtext:
        anchor = (
            "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;"
            "->apply(Landroid/view/View;)V\n"
        )
        if anchor not in rtext:
            raise RuntimeError("Could not locate V6 hierarchy hook in apply runnable")
        rtext = rtext.replace(anchor, anchor + call, 1)
        runnable.write_text(rtext, encoding="utf-8")

    return {"global_layout_listener": listener_rel, "apply_runnable": runnable_rel}


def apply_coloros_v2_visual_profile_v7(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    visual_v6 = base.apply_coloros_v2_visual_profile_v6(decompile_dir, patch_report)
    state_colors = _apply_extra_state_colors(decompile_dir)
    helper = _inject_panel_helper(decompile_dir, visual_v6)
    hooks = _patch_panel_hooks(decompile_dir, visual_v6)

    return {
        "strategy": (
            "V6 ColorOS G2/material stack + audited tool/candidate hierarchy + "
            "WeType self-draw Normal/Pressed material states + opaque key preview"
        ),
        "base_v6": visual_v6,
        "key_architecture": {
            "wetype": (
                "single self-draw keyboard View; KeyData/runtime-j state; drawmethod/c press branch"
            ),
            "oplus": (
                "single input/view/body/s View; h(softKey, pressed) selects "
                "bgKeyNormalBlur/bgKeyPressedBlur and function/enter state Drawables"
            ),
            "policy": (
                "do not create per-key ViewRootManager blur instances; use WeType's existing "
                "pressMaskColor state machine over the verified root FAST_KAWASE material"
            ),
        },
        "state_materials": state_colors,
        "panel_hierarchy": {
            "candidate_view": "com.tencent.wetype.plugin.hld.candidate.ImeCandidateView",
            "suppressed_for": list(OWN_CHROME_PANEL_CLASSES),
            "preserved_for": list(KEEP_GLOBAL_CANDIDATE_CLASSES),
            "named_tool_audit": PANEL_AUDIT,
            "restore_policy": (
                "only a previously VISIBLE candidate is changed to INVISIBLE; exact prior "
                "visibility is restored from WeakHashMap when the own-chrome panel closes"
            ),
            "helper": helper,
            "hooks": hooks,
        },
        "confidence_boundary": (
            "static DEX + binary-layout mapping and CI can prove call sites/buildability; "
            "final rendering/transitions still require ColorOS 17 device validation"
        ),
    }
