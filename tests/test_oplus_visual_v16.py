import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v16 as v16


class V16SystemUICornerPolicyTests(unittest.TestCase):
    def test_policy_reads_all_physical_rounded_corners_in_loop(self):
        text = v16.POLICY_SMALI
        self.assertIn("Landroid/view/Display;->getRoundedCorner(I)Landroid/view/RoundedCorner;", text)
        self.assertIn("Landroid/view/RoundedCorner;->getRadius()I", text)
        self.assertIn("const/4 v3, 0x4", text)
        self.assertIn("add-int/lit8 v1, v1, 0x1", text)

    def test_toolbar_policy_matches_systemui_local_bounds_half(self):
        text = v16.POLICY_SMALI
        self.assertIn("com.tencent.wetype.plugin.hld.toolbar.", text)
        self.assertIn("->getWidth()I", text)
        self.assertIn("->getHeight()I", text)
        self.assertIn("const/high16 v5, 0x40000000", text)
        self.assertIn("div-float/2addr v4, v5", text)

    def test_policy_reuses_existing_g2_outline_provider(self):
        text = v16.POLICY_SMALI
        self.assertIn("ColorOSV2Round;->getWeight()F", text)
        self.assertIn("ColorOSV2Round;->getCornerType()I", text)
        self.assertIn("ColorOSV2Round$OutlineProvider;-><init>(FFI)V", text)
        self.assertIn("->setClipToOutline(Z)V", text)

    def test_floating_patch_removes_fixed_14dp_and_adds_g2_clip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = root / "smali" / v16.LOCAL_RELATIVE_PATH
            helper.parent.mkdir(parents=True)
            helper.write_text(
                ".class public final Lcom/tencent/wetype/monet/ColorOSV2LocalBlurV13;\n"
                ".super Ljava/lang/Object;\n"
                ".method public static installFloating(Landroid/view/View;)V\n"
                "    .locals 14\n"
                + v16._FLOATING_RADIUS_OLD
                + "    if-eqz v9, :rollback_carrier\n"
                + v16._FLOATING_BG_INSTALL
                + "    :rollback_carrier\n"
                "    return-void\n"
                ".end method\n"
                ".method public static installBubble(Landroid/view/View;)V\n"
                "    .locals 0\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            report = v16._patch_floating_geometry(root)
            text = helper.read_text(encoding="utf-8")
            self.assertEqual(report["radius_source"], "Display.getRoundedCorner(0..3) max radius")
            self.assertNotIn("# 14.0f", v16._method_slice(text, ".method public static installFloating(Landroid/view/View;)V"))
            self.assertIn("->getScreenCornerRadius(Landroid/view/View;)F", text)
            self.assertEqual(text.count("->applyG2Outline(Landroid/view/View;F)V"), 2)
            self.assertEqual(text.count("->createLocalBlur(Landroid/view/View;IFFFF)"), 1)

    def test_round_policy_only_resolves_existing_rounded_view_radius(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = root / "smali_classes2" / v16.ROUND_RELATIVE_PATH
            helper.parent.mkdir(parents=True)
            helper.write_text(
                ".class public final Lcom/tencent/wetype/monet/ColorOSV2Round;\n"
                ".super Ljava/lang/Object;\n"
                ".method private static applyView(Landroid/view/View;)V\n"
                "    .locals 3\n"
                "    invoke-virtual {p0}, Landroid/view/View;->getBackground()Landroid/graphics/drawable/Drawable;\n"
                "    move-result-object v0\n"
                + v16._ROUND_RADIUS_ANCHOR
                + "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            report = v16._patch_round_policy(root)
            text = helper.read_text(encoding="utf-8")
            self.assertIn("min(width,height)/2", report["toolbar_policy"])
            self.assertEqual(text.count("->resolveRoundedViewRadius(Landroid/view/View;F)F"), 1)

    def test_policy_injection_uses_same_smali_partition_as_round_helper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            round_helper = root / "smali_classes4" / v16.ROUND_RELATIVE_PATH
            round_helper.parent.mkdir(parents=True)
            round_helper.write_text(".class public final Lcom/tencent/wetype/monet/ColorOSV2Round;\n.super Ljava/lang/Object;\n", encoding="utf-8")
            rel = v16._inject_policy(root)
            self.assertTrue(rel.startswith("smali_classes4/"))
            policy = root / rel
            self.assertTrue(policy.is_file())


if __name__ == "__main__":
    unittest.main()
