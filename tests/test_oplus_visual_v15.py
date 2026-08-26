import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v15 as v15


class V15VisualRefinementTests(unittest.TestCase):
    def test_bubble_fill_is_explicitly_theme_aware(self):
        text = v15._BUBBLE_FILL_METHOD
        self.assertIn("->isNight(Landroid/view/View;)Z", text)
        self.assertIn(f"0x{v15.DARK_BUBBLE_COLOR:08x}", text)
        self.assertIn(f"0x{v15.LIGHT_BUBBLE_COLOR:08x}", text)
        self.assertIn(f"0x{v15.DARK_BUBBLE_ALPHA:02x}", text)
        self.assertIn(f"0x{v15.LIGHT_BUBBLE_ALPHA:02x}", text)
        self.assertGreater(v15.DARK_BUBBLE_ALPHA, v15.LIGHT_BUBBLE_ALPHA)
        self.assertGreaterEqual(v15.DARK_BUBBLE_ALPHA, 0xF0)

    def test_bubble_fill_does_not_create_blur_owner(self):
        text = v15._BUBBLE_FILL_METHOD
        self.assertNotIn("ViewRootManager", text)
        self.assertNotIn("getBackgroundBlurDrawable", text)
        self.assertNotIn("createLocalBlur", text)
        self.assertNotIn("setBlurRadius", text)

    def test_highlight_disable_is_invisible_not_another_geometry(self):
        self.assertIn("setVisibility(I)V", v15._HIGHLIGHT_DISABLE)
        self.assertIn("const/4 v7, 0x4", v15._HIGHLIGHT_DISABLE)

    def test_rewrite_replaces_bubble_method_and_disables_one_highlight(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "smali" / v15.LOCAL_RELATIVE_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                ".class public final Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;\n"
                ".super Ljava/lang/Object;\n"
                ".method public static applyBubbleFill(Landroid/view/View;Landroid/graphics/Paint;)V\n"
                "    .locals 0\n"
                "    return-void\n"
                ".end method\n"
                ".method public static installFloating(Landroid/view/View;)V\n"
                "    .locals 11\n"
                "    const-string v5, \"WeTypeBlurCarrier_Float\"\n"
                "    const-string v11, \"WeTypeBlurHighlight_Float\"\n"
                "    invoke-virtual {v10, v6}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            result = v15._rewrite_v15_material(root)
            text = path.read_text(encoding="utf-8")
            self.assertIn("->isNight(Landroid/view/View;)Z", text)
            self.assertEqual(text.count("setVisibility(I)V"), 1)
            self.assertFalse(result["floating"]["decorative_highlight_visible"])


if __name__ == "__main__":
    unittest.main()
