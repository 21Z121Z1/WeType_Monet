import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v10 as v10


class V10LayerMaterialTests(unittest.TestCase):
    def test_preview_tints_are_translucent_material_overlays(self):
        for name, value in v10.LAYERED_KEY_PREVIEW_COLORS.items():
            if name.endswith("click_color"):
                continue
            alpha = int(value[1:3], 16)
            self.assertGreater(alpha, 0)
            self.assertLess(alpha, 0xFF)

    def test_local_helper_uses_background_blur_without_second_blurparam_owner(self):
        text = v10.LAYER_HELPER_SMALI
        self.assertIn("Lcom/oplus/view/ViewRootManager;", text)
        self.assertIn("->getBackgroundBlurDrawable()", text)
        self.assertIn("->setBlurRadius(I)V", text)
        self.assertIn("->setColor(I)V", text)
        self.assertIn("->setCornerRadius(FFFF)V", text)
        self.assertIn("Landroid/graphics/drawable/LayerDrawable;", text)
        self.assertNotIn("OplusBlurParam", text)
        self.assertNotIn("->setBlurParams(", text)
        self.assertNotIn("OplusKeyboardBlur;->applyNow", text)

    def test_float_root_hooks_existing_attach_and_visibility(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "smali" / "com/tencent/wetype/plugin/hld/floatview/u.smali"
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public Lcom/tencent/wetype/plugin/hld/floatview/u;\n"
                ".super Landroid/widget/FrameLayout;\n"
                ".method protected onAttachedToWindow()V\n"
                "    .locals 0\n"
                "    invoke-super {p0}, Landroid/widget/FrameLayout;->onAttachedToWindow()V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            report = v10._patch_float_root(root)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(report["attach"], "existing_method_hooked")
            self.assertEqual(report["visibility"], "override_added")
            self.assertEqual(text.count("->applyFloat(Landroid/view/View;)V"), 2)
            self.assertIn("invoke-super {p0}, Landroid/widget/FrameLayout;->onAttachedToWindow()V", text)
            self.assertIn("onVisibilityChanged(Landroid/view/View;I)V", text)

    def test_voice_root_preserves_existing_lifecycle_logic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "smali_classes3" / "com/tencent/wetype/plugin/hld/voice/ImeVoiceView.smali"
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public Lcom/tencent/wetype/plugin/hld/voice/ImeVoiceView;\n"
                ".super Landroid/widget/FrameLayout;\n"
                ".method protected onAttachedToWindow()V\n"
                "    .locals 0\n"
                "    invoke-super {p0}, Landroid/widget/FrameLayout;->onAttachedToWindow()V\n"
                "    return-void\n"
                ".end method\n"
                ".method protected onVisibilityChanged(Landroid/view/View;I)V\n"
                "    .locals 0\n"
                "    invoke-super {p0, p1, p2}, Landroid/widget/FrameLayout;->onVisibilityChanged(Landroid/view/View;I)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            report = v10._patch_voice_root(root)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(report["attach"], "existing_method_hooked")
            self.assertEqual(report["visibility"], "existing_method_hooked")
            self.assertEqual(text.count("->applyVoice(Landroid/view/View;)V"), 2)
            self.assertIn("FrameLayout;->onVisibilityChanged", text)

    def test_candidate_helper_voice_insertion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = root / "smali" / "com/tencent/wetype/monet/ColorOSV2PanelHierarchyV7.smali"
            helper.parent.mkdir(parents=True)
            helper.write_text(
                ".class public final Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;\n"
                ".super Ljava/lang/Object;\n"
                ".method private static isOwnChromeClass(Ljava/lang/String;)Z\n"
                "    .locals 1\n"
                "    const-string v0, \"existing\"\n"
                "    invoke-virtual {p0, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n"
                "    move-result v0\n"
                "    if-nez v0, :yes\n"
                "    const/4 v0, 0x0\n"
                "    return v0\n"
                "    :yes\n"
                "    const/4 v0, 0x1\n"
                "    return v0\n"
                ".end method\n",
                encoding="utf-8",
            )
            # _find_v9_helper needs the V9 overlay helper to establish the same tree.
            overlay = helper.with_name("ColorOSV2OverlayHierarchyV9.smali")
            overlay.write_text(".class public final Lx;\n.super Ljava/lang/Object;\n", encoding="utf-8")
            rel = v10._add_voice_to_candidate_helper(root)
            self.assertTrue(rel.endswith("ColorOSV2PanelHierarchyV7.smali"))
            self.assertIn(v10.VOICE_CLASS, helper.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
