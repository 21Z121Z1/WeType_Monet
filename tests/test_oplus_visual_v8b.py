import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v8b as v8b


class V8BCorrectionTests(unittest.TestCase):
    def test_gradient_names_are_signatures_not_resource_targets(self):
        for name in v8b.WETYPE_TOOL_DEXKIT_GRADIENT_SIGNATURES:
            self.assertNotIn(name, v8b.WETYPE_TOOL_RESOURCE_COLORS)
        self.assertEqual(
            set(v8b.WETYPE_TOOL_RESOURCE_COLORS),
            {
                "ime_skin_clipboard_item_bg_color",
                "ime_skin_dark_clipboard_item_bg_color",
            },
        )

    def test_corrected_wrapper_patches_only_real_resource_semantics(self):
        original_apply = v8b.base.apply_coloros_v2_visual_profile_v8
        seen = {}

        def fake_apply(decompile_dir, patch_report):
            seen["surface_colors"] = dict(v8b.base.WETYPE_TOOL_SURFACE_COLORS)
            return {
                "wetype_tool_evidence": {},
                "tool_surfaces": {},
            }

        v8b.base.apply_coloros_v2_visual_profile_v8 = fake_apply
        try:
            result = v8b.apply_coloros_v2_visual_profile_v8(Path("."), {})
        finally:
            v8b.base.apply_coloros_v2_visual_profile_v8 = original_apply

        self.assertEqual(seen["surface_colors"], v8b.WETYPE_TOOL_RESOURCE_COLORS)
        self.assertEqual(
            result["resource_resolution_correction"]["verified_non_resource_signatures"],
            list(v8b.WETYPE_TOOL_DEXKIT_GRADIENT_SIGNATURES),
        )
        self.assertIn("DexKit", result["wetype_tool_evidence"]["gradient_signature_interpretation"])


if __name__ == "__main__":
    unittest.main()
