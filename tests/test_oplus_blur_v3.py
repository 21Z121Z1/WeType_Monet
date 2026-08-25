import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_blur_v3


class OplusBlurV3Tests(unittest.TestCase):
    def test_surface_palette_replaces_backgrounds_but_not_foregrounds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = root / "res" / "values"
            values_night = root / "res" / "values-night"
            values.mkdir(parents=True)
            values_night.mkdir(parents=True)

            semantics = [
                "ime_skin_candidate_start_color",
                "ime_skin_dark_candidate_start_color",
                "ime_skin_color_10",
                "ime_skin_dark_color_10",
                "ime_skin_color_12",
                "ime_skin_dark_color_12",
                "ime_skin_color_13",
                "ime_skin_dark_color_13",
                "ime_skin_color_btn_white_text",  # foreground: must remain untouched
            ]
            items = []
            names = {}
            for i, semantic in enumerate(semantics):
                name = f"c{i}"
                names[semantic] = name
                items.append({"unobfuscated_key": semantic, "obfuscated_key": name})

            config = root / "target.json"
            config.write_text(json.dumps({"theme_colors": items}), encoding="utf-8")

            xml = ['<?xml version="1.0" encoding="utf-8"?><resources>']
            for name in names.values():
                xml.append(f'<color name="{name}">#FF123456</color>')
            xml.append('</resources>')
            (values / "colors.xml").write_text("".join(xml), encoding="utf-8")

            # Keep an unrelated values-night file to ensure directory traversal is harmless.
            (values_night / "other.xml").write_text(
                '<?xml version="1.0" encoding="utf-8"?><resources><color name="other">#FF000000</color></resources>',
                encoding="utf-8",
            )

            result = oplus_blur_v3.apply_glass_surface_palette(root, config)
            out = (values / "colors.xml").read_text(encoding="utf-8")

            self.assertIn('#00000000', out)
            self.assertIn('#38FFFFFF', out)  # light container / emoji tab bar
            self.assertIn('#18FFFFFF', out)  # dark container / emoji tab bar
            self.assertIn('#8CFFFFFF', out)  # light ordinary key
            self.assertIn('#2EFFFFFF', out)  # dark ordinary key
            self.assertIn('#66FFFFFF', out)  # light function key
            self.assertIn('#42FFFFFF', out)  # dark function key

            # Foreground mapping is not part of the glass-surface target set.
            self.assertIn(f'<color name="{names["ime_skin_color_btn_white_text"]}">#FF123456</color>', out)
            self.assertFalse(result["secondary_child_blur"])
            self.assertEqual(result["strategy"], "single root compositor blur + translucent child material tints")

    def test_real_target_semantics_cover_emoji_and_key_surfaces(self):
        target = REPO_ROOT / "config" / "targets" / "3.5.3(55201).json"
        resolved = oplus_blur_v3._resolved_surface_map(target)
        semantics = {semantic for semantic, _role, _argb in resolved.values()}

        for expected in (
            "ime_skin_color_10",
            "ime_skin_dark_color_10",
            "ime_skin_S5_type_selected_color",
            "ime_skin_dark_S5_type_selected_color",
            "ime_skin_color_12",
            "ime_skin_dark_color_12",
            "ime_skin_color_13",
            "ime_skin_dark_color_13",
            "ime_skin_color_btn_white_bg",
            "ime_skin_dark_color_btn_white_bg",
        ):
            self.assertIn(expected, semantics)


if __name__ == "__main__":
    unittest.main()
