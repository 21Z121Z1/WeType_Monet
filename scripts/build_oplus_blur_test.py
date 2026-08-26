#!/usr/bin/env python3
"""Build a same-project-signature WeType APK with the ColorOS keyboard experiment."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import build
from oplus_blur import apply_oplus_private_blur
from oplus_blur_attach_fix import make_attachment_safe
from oplus_blur_v2 import upgrade_to_keyboard_material_v2
from oplus_blur_v4 import apply_breeno_appearance_profile
from oplus_visual_v9 import apply_coloros_v2_visual_profile_v9


def _safe(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]', "_", value)


def _force_download_and_decompile():
    original_get_latest = build.get_latest_build_state
    build.get_latest_build_state = lambda: None
    try:
        result = build.download_and_decompile_apk()
    finally:
        build.get_latest_build_state = original_get_latest
    if result is None:
        raise RuntimeError(
            "Forced experimental download/decompile unexpectedly produced no build input"
        )
    return result


def rebuild_and_sign(apk_name: str, apk_code: str) -> tuple[Path, str]:
    _, zipalign, apksigner, _ = build.find_sdk_tools()
    build.ensure_original_package_name()

    unsigned_apk = build.OUT_DIR / "oplus-blur-v9-unsigned.apk"
    aligned_apk = build.OUT_DIR / "oplus-blur-v9-aligned.apk"
    final_apk = (
        build.OUT_DIR
        / f"Wetype_Monet_OplusBlurV9_{_safe(apk_name)}({_safe(apk_code)}).apk"
    )
    for path in (
        unsigned_apk,
        aligned_apk,
        final_apk,
        Path(f"{final_apk}.idsig"),
    ):
        if path.exists():
            path.unlink()

    print("[*] Rebuilding ColorOS keyboard-material v9 experiment with apktool...")
    result = subprocess.run(
        ["apktool", "b", str(build.DECOMPILE_DIR), "-o", str(unsigned_apk)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Apktool rebuild failed:\n{result.stderr or result.stdout}")

    subprocess.run(
        [str(zipalign), "-p", "-f", "4", str(unsigned_apk), str(aligned_apk)],
        check=True,
    )
    keystore_path = build.prepare_public_signing_keystore()
    subprocess.run(
        [
            str(apksigner),
            "sign",
            "--ks",
            str(keystore_path),
            "--ks-type",
            "PKCS12",
            "--ks-pass",
            f"pass:{build.PUBLIC_SIGNING_PASSWORD}",
            "--key-pass",
            f"pass:{build.PUBLIC_SIGNING_PASSWORD}",
            "--ks-key-alias",
            build.PUBLIC_SIGNING_ALIAS,
            "--v1-signing-enabled",
            "true",
            "--v2-signing-enabled",
            "true",
            "--v3-signing-enabled",
            "true",
            "--v4-signing-enabled",
            "false",
            "--out",
            str(final_apk),
            str(aligned_apk),
        ],
        check=True,
    )
    verify = subprocess.run(
        [str(apksigner), "verify", "--verbose", "--print-certs", str(final_apk)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    print(verify.stdout)

    for path in (
        unsigned_apk,
        aligned_apk,
        Path(f"{final_apk}.idsig"),
        keystore_path,
    ):
        if path.exists():
            path.unlink()
    return final_apk, verify.stdout


def main() -> None:
    build.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    build.TARGET_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    build.OUT_DIR.mkdir(parents=True, exist_ok=True)

    sha256_str, apk_code, apk_name, release_date, changelog = (
        _force_download_and_decompile()
    )
    print(f"[+] Upstream WeType: {apk_name} ({apk_code}), sha256={sha256_str}")

    config_path = build.generate_version_config(
        sha256_str, apk_code, apk_name, release_date, changelog
    )
    build.apply_monet_resources(config_path)

    patch_report = apply_oplus_private_blur(build.DECOMPILE_DIR, config_path)
    patch_report["attachment_v1"] = make_attachment_safe(
        build.DECOMPILE_DIR, patch_report
    )

    patch_report["material_v2"] = upgrade_to_keyboard_material_v2(
        build.DECOMPILE_DIR, patch_report
    )

    patch_report["appearance_v4"] = apply_breeno_appearance_profile(
        build.DECOMPILE_DIR, config_path
    )

    # V9 keeps the V8b WeType-Tool-guided event architecture, but fixes the
    # device-proven state bugs: all full replacement keyboards (including S15
    # clipboard/common phrase and S31 inspiration) suppress the underlying
    # self-draw keyboard, and effective visibility/alpha/window callbacks plus
    # one delayed transition repair guarantee restoration after emoji/tool exit.
    # There is still no steady-state global-layout tree walk or per-key blur.
    patch_report["visual_v9"] = apply_coloros_v2_visual_profile_v9(
        build.DECOMPILE_DIR, patch_report
    )

    print("[+] ColorOS keyboard-material v9 patch report:")
    print(json.dumps(patch_report, ensure_ascii=False, indent=2))

    final_apk, cert_output = rebuild_and_sign(apk_name, apk_code)
    metadata = {
        "apk_file": final_apk.name,
        "experiment": (
            "ColorOS keyboard material v9 - native FAST_KAWASE/tint + Breeno hierarchy + "
            "SystemUI G2/V2 smooth corners + system font + WeType Tool guided hook surfaces + "
            "single full-overlay alpha owner + lifecycle-complete transition restoration + "
            "self-draw Normal/Pressed states"
        ),
        "upstream_version_name": apk_name,
        "upstream_version_code": apk_code,
        "upstream_sha256": sha256_str,
        "config_file": config_path.name,
        "signing_key": "repository public release key (signing/LSPatch.bks)",
        "patch_report": patch_report,
        "apksigner_verify": cert_output,
    }
    metadata_path = build.OUT_DIR / "oplus-blur-v9-build-metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[+] Experimental APK: {final_apk}")
    print(f"[+] Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
