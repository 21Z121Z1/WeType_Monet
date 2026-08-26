import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v14 as v14


class V14BubbleReuseTests(unittest.TestCase):
    def test_bubble_install_has_no_local_blur_owner(self):
        block = v14._BUBBLE_INSTALL_METHOD
        for forbidden in (
            "ViewRootManager",
            "getBackgroundBlurDrawable",
            "createLocalBlur",
            "OplusBlurParam",
            "setBlurRadius",
            "setColor",
            "setBackground(Landroid/graphics/drawable/Drawable;)",
        ):
            self.assertNotIn(forbidden, block)
        self.assertIn("setClipToOutline(Z)V", block)
        self.assertIn("bubbleActive", block)

    def test_bubble_fill_is_dense_material_tint(self):
        self.assertGreaterEqual(v14.BUBBLE_REUSE_ALPHA, 0xC0)
        self.assertLess(v14.BUBBLE_REUSE_ALPHA, 0xFF)
        self.assertIn(
            f"const/16 v0, 0x{v14.BUBBLE_REUSE_ALPHA:02x}",
            v14._BUBBLE_FILL_METHOD,
        )

    def test_method_replacement_is_exact_and_idempotent_shape(self):
        original = (
            ".class public final Lx;\n"
            ".super Ljava/lang/Object;\n"
            ".method public static installBubble(Landroid/view/View;)V\n"
            "    .locals 1\n"
            "    return-void\n"
            ".end method\n"
            ".method public static tail()V\n"
            "    .locals 0\n"
            "    return-void\n"
            ".end method\n"
        )
        patched = v14._replace_method(
            original,
            ".method public static installBubble(Landroid/view/View;)V",
            v14._BUBBLE_INSTALL_METHOD,
        )
        self.assertEqual(patched.count("installBubble(Landroid/view/View;)V"), 1)
        self.assertIn(".method public static tail()V", patched)

    def test_audit_accepts_root_reuse_and_preserved_floating(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = root / "smali" / v14.LOCAL_RELATIVE_PATH
            helper.parent.mkdir(parents=True)
            helper.write_text(
                ".class public final Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;\n"
                ".super Ljava/lang/Object;\n"
                ".field private static final bubbleActive:Ljava/util/WeakHashMap;\n"
                + v14._BUBBLE_FILL_METHOD
                + "\n"
                + v14._BUBBLE_INSTALL_METHOD
                + "\n"
                + ".method public static installFloating(Landroid/view/View;)V\n"
                  "    .locals 1\n"
                  "    const-string v0, \"WeTypeBlurCarrier_Float\"\n"
                  "    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;->createLocalBlur(Landroid/view/View;)Landroid/graphics/drawable/Drawable;\n"
                  "    return-void\n"
                  ".end method\n",
                encoding="utf-8",
            )
            report = v14._audit_v14(root)
            self.assertTrue(report["bubble_root_blur_reuse"])
            self.assertEqual(report["bubble_local_blur_calls"], 0)
            self.assertTrue(report["floating_v13_carrier_preserved"])


if __name__ == "__main__":
    unittest.main()
