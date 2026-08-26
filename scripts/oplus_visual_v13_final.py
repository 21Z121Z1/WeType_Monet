#!/usr/bin/env python3
"""V13 final wrapper: normalize V12 metadata without changing runtime patches.

The real 3.5.3 build exposed a metadata-only assumption in V13: V12's return
value does not guarantee a top-level `floating` block, while V13 annotates that
block after all smali mutations have already succeeded. Normalize the report
shape before V13 adds annotations. This file changes no runtime bytecode or
material behavior.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    import oplus_visual_v13_fix as impl
except ModuleNotFoundError:
    _P = Path(__file__).resolve().with_name("oplus_visual_v13_fix.py")
    _S = importlib.util.spec_from_file_location("oplus_visual_v13_fix", _P)
    if _S is None or _S.loader is None:
        raise RuntimeError(f"Could not load sibling V13 fix: {_P}")
    impl = importlib.util.module_from_spec(_S)
    _S.loader.exec_module(impl)


def apply_coloros_v2_visual_profile_v13(
    decompile_dir: Path, patch_report: dict[str, object]
) -> dict[str, object]:
    base13 = impl.base
    original_v12_apply = base13.v12.apply_coloros_v2_visual_profile_v12

    def _normalized_v12(*args, **kwargs):
        result = original_v12_apply(*args, **kwargs)
        if not isinstance(result, dict):
            raise RuntimeError("V12 visual pass returned non-dict metadata")
        result.setdefault("key_preview", {})
        result.setdefault("floating", {})
        return result

    base13.v12.apply_coloros_v2_visual_profile_v12 = _normalized_v12
    try:
        result = impl.apply_coloros_v2_visual_profile_v13(
            decompile_dir, patch_report
        )
    finally:
        base13.v12.apply_coloros_v2_visual_profile_v12 = original_v12_apply

    result["metadata_shape_normalized"] = True
    return result
