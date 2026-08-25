import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_blur_v4


class OplusBlurV4Tests(unittest.TestCase):
    def test_breeno_profile_builds_depth_hierarchy_and_keeps_foregrounds_safe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = root / "res" / "values"
            values.mkdir(parents=True)

            semantics = [
                "ime_skin_candidate_start_color",
                "ime_skin_color_10",
                "ime_skin_color_18",
                "ime_skin_color_12",
                "ime_skin_color_13",
                "ime_skin_S5_type_selected_color",
                "ime_skin_key_white_border_color",
                "ime_skin_key_grey_border_color",
                "ime_skin_key_white_shadow_color",
                "ime_skin_color_14",  # mixed foreground/background: excluded
                "ime_skin_color_btn_white_text",  # foreground: untouched
            ]
            items = []
            names = {}
            for i, semantic in enumerate(semantics):
                name = f"c{i}"
                names[semantic] = name
                items.append(
                    {
                        "unobfuscated_key": semantic,
                        "obfuscated_key": name,
                    }
                )

            config = root / "target.json"
            config.write_text(
                json.dumps({"theme_colors": items}),
                encoding="utf-8",
            )

            xml = ['<?xml version="1.0" encoding="utf-8"?><resources>']
            for name in names.values():
                xml.append(f'<color name="{name}">#FF123456</color>')
            xml.append("</resources>")
            (values / "colors.xml").write_text("".join(xml), encoding="utf-8")

            result = oplus_blur_v4.apply_breeno_appearance_profile(root, config)
            out = (values / "colors.xml").read_text(encoding="utf-8")

            self.assertIn("#00000000", out)  # root clear
            self.assertIn("#24FFFFFF", out)  # panel
            self.assertIn("#46FFFFFF", out)  # elevated card
            self.assertIn("#72FFFFFF", out)  # normal key
            self.assertIn("#18000000", out)  # light function key
            self.assertIn("#58FFFFFF", out)  # selected surface
            self.assertIn("#5CFFFFFF", out)  # key edge
            self.assertIn("#1F000000", out)  # control edge
            self.assertIn("#1A000000", out)  # ambient shadow

            # Mixed foreground/background token must not be globally repainted.
            self.assertIn(
                f'<color name="{names["ime_skin_color_14"]}">#FF123456</color>',
                out,
            )
            # Pure foreground token must also remain untouched.
            self.assertIn(
                f'<color name="{names["ime_skin_color_btn_white_text"]}">#FF123456</color>',
                out,
            )

            self.assertFalse(result["true_child_blur"])
            self.assertIn("ime_skin_color_14", result["mixed_role_exclusions"])
            self.assertEqual(
                result["strategy"],
                "ColorOS/Breeno-derived layered glass appearance over root FAST_KAWASE blur",
            )
            self.assertIn("bgKeyNormalBlur", result["reference_apk_evidence"])
            self.assertIn("keyShadowRadius", result["reference_apk_evidence"])

    def test_real_target_covers_breeno_like_surface_edge_and_shadow_roles(self):
        target = REPO_ROOT / "config" / "targets" / "3.5.3(55201).json"
        resolved, missing = oplus_blur_v4._resolved_style_map(target)
        semantics = {semantic for semantic, _role, _argb in resolved.values()}

        for expected in (
            "ime_skin_color_10",
            "ime_skin_color_18",
            "ime_skin_color_12",
            "ime_skin_color_13",
            "ime_skin_S5_type_selected_color",
            "ime_skin_key_white_border_color",
            "ime_skin_color_btn_grey_border",
            "ime_skin_key_white_shadow_color",
            "ime_skin_color_btn_green_shadow",
        ):
            self.assertIn(expected, semantics)

        self.assertNotIn("ime_skin_color_14", semantics)
        self.assertNotIn("ime_skin_dark_color_14", semantics)

        # The checked-in 3.5.3 mapping contains every role token used by v4.
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
