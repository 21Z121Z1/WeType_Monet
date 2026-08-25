#!/usr/bin/env python3
"""Inject ColorOS/Oplus private background-blur plumbing into a decoded IME APK.

This module deliberately keeps the experiment isolated from the normal Monet
resource build. It patches the decoded APK at smali/resource level so the
result can be rebuilt with the repository's existing release key.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ANDROID_NAME = f"{{{ANDROID_NS}}}name"
ANDROID_PERMISSION = f"{{{ANDROID_NS}}}permission"
BIND_INPUT_METHOD = "android.permission.BIND_INPUT_METHOD"
INPUT_METHOD_ACTION = "android.view.InputMethod"
HELPER_DESCRIPTOR = "Lcom/tencent/wetype/monet/OplusKeyboardBlur;"
HELPER_RELATIVE_PATH = Path("com/tencent/wetype/monet/OplusKeyboardBlur.smali")
APPLY_CALL_SUFFIX = "->apply(Landroid/view/View;)V"

# Full-panel colors in WeType's stable, unobfuscated resource map. They need to
# be transparent for BackgroundBlurDrawable to remain visible below the keys.
TRANSPARENT_BACKGROUND_KEYS = {
    "ime_skin_candidate_start_color",
    "ime_skin_candidate_end_color",
    "ime_skin_keyboard_end_color",
    "ime_skin_keyboard_background",
    "ime_skin_dark_candidate_start_color",
    "ime_skin_dark_candidate_end_color",
    "ime_skin_dark_keyboard_end_color",
    "ime_skin_dark_keyboard_background",
    "ime_skin_alternative_keyboard_bg_color",
    "ime_skin_dark_alternative_keyboard_bg_color",
}

HELPER_SMALI = r'''.class public final Lcom/tencent/wetype/monet/OplusKeyboardBlur;
.super Ljava/lang/Object;

.field private static final TAG:Ljava/lang/String; = "WeTypeOplusBlur"

.method private constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static apply(Landroid/view/View;)V
    .locals 7

    if-eqz p0, :return

    :try_start_0
    new-instance v0, Lcom/oplus/view/ViewRootManager;
    invoke-direct {v0, p0}, Lcom/oplus/view/ViewRootManager;-><init>(Landroid/view/View;)V

    invoke-virtual {v0}, Lcom/oplus/view/ViewRootManager;->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;
    move-result-object v1
    if-eqz v1, :return

    new-instance v2, Lcom/oplus/graphics/OplusBlurParam;
    invoke-direct {v2}, Lcom/oplus/graphics/OplusBlurParam;-><init>()V

    const/4 v3, 0x2
    invoke-virtual {v2, v3}, Lcom/oplus/graphics/OplusBlurParam;->setBlurType(I)V

    const/4 v3, 0x1
    invoke-virtual {v2, v3}, Lcom/oplus/graphics/OplusBlurParam;->setSmoothCornerType(I)V

    const/high16 v4, 0x40400000    # 3.0f
    invoke-virtual {v2, v4}, Lcom/oplus/graphics/OplusBlurParam;->setSmoothCornerWeight(F)V

    invoke-virtual {v0, v2}, Lcom/oplus/view/ViewRootManager;->setBlurParams(Lcom/oplus/graphics/OplusBlurParam;)V

    const/16 v3, 0x96    # 150
    invoke-virtual {v0, v3}, Lcom/oplus/view/ViewRootManager;->setBlurRadius(I)V

    # Restrained dark tint; the backdrop itself remains compositor blur.
    const v3, 0x42000000
    invoke-virtual {v0, v3}, Lcom/oplus/view/ViewRootManager;->setColor(I)V

    invoke-virtual {p0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v3
    invoke-virtual {v3}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v3
    iget v4, v3, Landroid/util/DisplayMetrics;->density:F
    const/high16 v5, 0x41e00000    # 28.0f
    mul-float/2addr v5, v4
    const/4 v6, 0x0
    invoke-virtual {v0, v5, v5, v6, v6}, Lcom/oplus/view/ViewRootManager;->setCornerRadius(FFFF)V

    invoke-virtual {p0, v1}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    const-string v3, "WeTypeOplusBlur"
    const-string v4, "Applied ColorOS private blur radius=150, smoothCorner=1/3.0, topRadius=28dp"
    invoke-static {v3, v4}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    goto :return

    :catch_0
    move-exception v0
    const-string v1, "WeTypeOplusBlur"
    const-string v2, "ColorOS private blur path failed"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I

    :return
    return-void
.end method
'''


def _resolve_component_name(package_name: str, component_name: str) -> str:
    if component_name.startswith("."):
        return package_name + component_name
    if "." not in component_name:
        return f"{package_name}.{component_name}"
    return component_name


def find_ime_service_descriptors(manifest_path: Path) -> list[str]:
    root = ET.parse(manifest_path).getroot()
    package_name = root.get("package") or ""
    if not package_name:
        raise RuntimeError(f"Manifest has no package name: {manifest_path}")

    descriptors: list[str] = []
    for service in root.findall(".//service"):
        is_ime = service.get(ANDROID_PERMISSION) == BIND_INPUT_METHOD
        if not is_ime:
            for action in service.findall("./intent-filter/action"):
                if action.get(ANDROID_NAME) == INPUT_METHOD_ACTION:
                    is_ime = True
                    break
        if not is_ime:
            continue
        raw_name = service.get(ANDROID_NAME)
        if not raw_name:
            continue
        fqcn = _resolve_component_name(package_name, raw_name)
        descriptors.append(f"L{fqcn.replace('.', '/')};")

    if not descriptors:
        raise RuntimeError("No BIND_INPUT_METHOD/InputMethod service found in decoded manifest")
    return descriptors


def _iter_smali_roots(decompile_dir: Path) -> list[Path]:
    roots = [path for path in decompile_dir.iterdir() if path.is_dir() and path.name.startswith("smali")]
    return sorted(roots, key=lambda path: (path.name != "smali", path.name))


def _descriptor_relative_path(descriptor: str) -> Path:
    if not (descriptor.startswith("L") and descriptor.endswith(";")):
        raise ValueError(f"Invalid class descriptor: {descriptor}")
    return Path(descriptor[1:-1] + ".smali")


def find_smali_file(decompile_dir: Path, descriptor: str) -> Path | None:
    relative = _descriptor_relative_path(descriptor)
    for root in _iter_smali_roots(decompile_dir):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def _read_super_descriptor(content: str) -> str | None:
    match = re.search(r"(?m)^\.super\s+(L[^;]+;)\s*$", content)
    return match.group(1) if match else None


def _find_on_create_input_view_block(content: str) -> tuple[int, int] | None:
    header = re.search(
        r"(?m)^\.method[^\n]*\bonCreateInputView\(\)Landroid/view/View;\s*$",
        content,
    )
    if not header:
        return None
    end = re.search(r"(?m)^\.end method\s*$", content[header.end() :])
    if not end:
        raise RuntimeError("Malformed smali: onCreateInputView has no .end method")
    return header.start(), header.end() + end.end()


def patch_on_create_input_view(smali_path: Path) -> int:
    content = smali_path.read_text(encoding="utf-8", errors="strict")
    block_range = _find_on_create_input_view_block(content)
    if block_range is None:
        return 0
    start, end = block_range
    block = content[start:end]
    if HELPER_DESCRIPTOR + APPLY_CALL_SUFFIX in block:
        return 0

    pattern = re.compile(r"(?m)^(?P<indent>\s*)return-object\s+(?P<reg>[vp]\d+)\s*$")
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        indent = match.group("indent") or "    "
        reg = match.group("reg")
        return (
            f"{indent}invoke-static {{{reg}}}, {HELPER_DESCRIPTOR}{APPLY_CALL_SUFFIX}\n"
            f"{match.group(0)}"
        )

    patched_block = pattern.sub(repl, block)
    if count:
        smali_path.write_text(content[:start] + patched_block + content[end:], encoding="utf-8")
    return count


def patch_set_input_view_calls(smali_path: Path) -> int:
    """Fallback for IMEs that install their view with setInputView()."""
    content = smali_path.read_text(encoding="utf-8", errors="strict")
    if HELPER_DESCRIPTOR + APPLY_CALL_SUFFIX in content:
        return 0

    pattern = re.compile(
        r"(?m)^(?P<indent>\s*)invoke-(?:virtual|super)\s+\{(?P<receiver>[vp]\d+),\s*(?P<view>[vp]\d+)\},\s*"
        r"Landroid/inputmethodservice/InputMethodService;->setInputView\(Landroid/view/View;\)V\s*$"
    )
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        indent = match.group("indent") or "    "
        view = match.group("view")
        return (
            f"{indent}invoke-static {{{view}}}, {HELPER_DESCRIPTOR}{APPLY_CALL_SUFFIX}\n"
            f"{match.group(0)}"
        )

    patched = pattern.sub(repl, content)
    if count:
        smali_path.write_text(patched, encoding="utf-8")
    return count


def _smali_root_for_file(smali_path: Path, decompile_dir: Path) -> Path:
    for parent in smali_path.parents:
        if parent.parent == decompile_dir and parent.name.startswith("smali"):
            return parent
    raise RuntimeError(f"Could not determine smali root for {smali_path}")


def patch_ime_entrypoint(decompile_dir: Path) -> dict[str, object]:
    manifest_path = decompile_dir / "AndroidManifest.xml"
    service_descriptors = find_ime_service_descriptors(manifest_path)
    patched_paths: list[Path] = []
    patch_count = 0
    helper_root: Path | None = None

    for service_descriptor in service_descriptors:
        descriptor = service_descriptor
        visited: set[str] = set()
        chain_paths: list[Path] = []

        while descriptor and descriptor not in visited:
            visited.add(descriptor)
            smali_path = find_smali_file(decompile_dir, descriptor)
            if smali_path is None:
                break
            chain_paths.append(smali_path)

            count = patch_on_create_input_view(smali_path)
            if count:
                patch_count += count
                patched_paths.append(smali_path)
                helper_root = helper_root or _smali_root_for_file(smali_path, decompile_dir)
                break

            content = smali_path.read_text(encoding="utf-8", errors="strict")
            descriptor = _read_super_descriptor(content)
            if descriptor == "Landroid/inputmethodservice/InputMethodService;":
                break

        for smali_path in chain_paths:
            count = patch_set_input_view_calls(smali_path)
            if count:
                patch_count += count
                patched_paths.append(smali_path)
                helper_root = helper_root or _smali_root_for_file(smali_path, decompile_dir)

    if patch_count == 0 or helper_root is None:
        raise RuntimeError(
            "Located the IME service but found neither onCreateInputView() returns nor setInputView() calls to patch"
        )

    helper_path = helper_root / HELPER_RELATIVE_PATH
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    if helper_path.exists() and helper_path.read_text(encoding="utf-8") != HELPER_SMALI:
        raise RuntimeError(f"Refusing to overwrite unexpected helper class: {helper_path}")
    helper_path.write_text(HELPER_SMALI, encoding="utf-8")

    return {
        "services": service_descriptors,
        "patched_calls": patch_count,
        "patched_files": sorted({str(path.relative_to(decompile_dir)) for path in patched_paths}),
        "helper_file": str(helper_path.relative_to(decompile_dir)),
    }


def make_keyboard_panel_transparent(decompile_dir: Path, config_file: Path) -> dict[str, object]:
    config = json.loads(config_file.read_text(encoding="utf-8"))
    obfuscated_names = {
        item.get("unobfuscated_key"): item.get("obfuscated_key")
        for item in config.get("theme_colors", [])
        if item.get("unobfuscated_key") in TRANSPARENT_BACKGROUND_KEYS and item.get("obfuscated_key")
    }
    target_names = {name for name in obfuscated_names.values() if name}
    if not target_names:
        raise RuntimeError("No WeType keyboard panel background resources resolved for Oplus blur experiment")

    changed_names: set[str] = set()
    changed_files: set[str] = set()
    res_dir = decompile_dir / "res"
    for values_dir in sorted(res_dir.glob("values*")):
        if not values_dir.is_dir():
            continue
        for xml_path in sorted(values_dir.rglob("*.xml")):
            if xml_path.name == "public.xml":
                continue
            try:
                tree = ET.parse(xml_path)
            except ET.ParseError as error:
                raise RuntimeError(f"Failed to parse resource XML: {xml_path}") from error
            changed = False
            for element in tree.getroot():
                element_type = element.tag.rsplit("}", 1)[-1]
                if element_type != "color" and not (element_type == "item" and element.get("type") == "color"):
                    continue
                name = element.get("name")
                if name in target_names:
                    element.text = "#00000000"
                    changed_names.add(name)
                    changed = True
            if changed:
                tree.write(xml_path, encoding="utf-8", xml_declaration=True)
                changed_files.add(str(xml_path.relative_to(decompile_dir)))

    missing = sorted(target_names - changed_names)
    if missing:
        raise RuntimeError(f"Resolved panel colors were not found in decoded resources: {', '.join(missing)}")

    return {
        "background_keys": sorted(obfuscated_names),
        "background_resources": sorted(changed_names),
        "resource_files": sorted(changed_files),
    }


def apply_oplus_private_blur(decompile_dir: Path, config_file: Path) -> dict[str, object]:
    decompile_dir = Path(decompile_dir)
    config_file = Path(config_file)
    resource_result = make_keyboard_panel_transparent(decompile_dir, config_file)
    smali_result = patch_ime_entrypoint(decompile_dir)
    return {"resources": resource_result, "smali": smali_result}
