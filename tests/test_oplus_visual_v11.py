import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v11 as v11


class V11VoiceHotfixTests(unittest.TestCase):
    def test_voice_is_not_part_of_v9_generic_panel_set(self):
        # V11 intentionally patches voice after V9 generation so V9 never adds
        # setAlpha/window-visibility hooks to an animated voice surface.
        self.assertNotIn(v11.VOICE_CLASS, v11.base.PANEL_CLASSES)

    def test_voice_lifecycle_only_hooks_attach_detach_and_direct_visibility(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "smali" / "com/tencent/wetype/plugin/hld/voice/ImeVoiceView.smali"
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public Lcom/tencent/wetype/plugin/hld/voice/ImeVoiceView;\n"
                ".super Landroid/widget/FrameLayout;\n"
                ".method protected onAttachedToWindow()V\n"
                "    .locals 0\n"
                "    invoke-super {p0}, Landroid/widget/FrameLayout;->onAttachedToWindow()V\n"
                "    return-void\n"
                ".end method\n"
                ".method protected onDetachedFromWindow()V\n"
                "    .locals 0\n"
                "    invoke-super {p0}, Landroid/widget/FrameLayout;->onDetachedFromWindow()V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            report = v11._patch_voice_lifecycle(root)
            text = path.read_text(encoding="utf-8")
            self.assertIn(report["operations"]["onAttachedToWindow"], {"existing_method_hooked", "override_added"})
            self.assertIn(report["operations"]["onDetachedFromWindow"], {"existing_method_hooked", "override_added"})
            self.assertEqual(report["operations"]["setVisibility"], "override_added")
            self.assertEqual(text.count("->onPanelVisibilityChanged(Landroid/view/View;)V"), 1)
            self.assertNotIn("setAlpha(F)V", text)
            self.assertNotIn("onWindowVisibilityChanged(I)V", text)
            self.assertNotIn("ColorOSV2LayerMaterialV10", text)

    def test_predicate_insertion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Helper.smali"
            path.write_text(
                ".class public LHelper;\n"
                ".super Ljava/lang/Object;\n"
                ".method private static isOverlayClass(Ljava/lang/String;)Z\n"
                "    .locals 1\n"
                "    const/4 v0, 0x0\n"
                "    return v0\n"
                "    :yes\n"
                "    const/4 v0, 0x1\n"
                "    return v0\n"
                ".end method\n",
                encoding="utf-8",
            )
            first = v11._insert_class_predicate(path, "isOverlayClass", v11.VOICE_CLASS)
            second = v11._insert_class_predicate(path, "isOverlayClass", v11.VOICE_CLASS)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(first, "inserted")
            self.assertEqual(second, "already_present")
            self.assertEqual(text.count(v11.VOICE_CLASS), 1)

    def test_v7_preview_fallback_is_opaque(self):
        v7 = v11.base.V7
        for semantic in (
            "ime_skin_key_float_view_upper_bg_color",
            "ime_skin_dark_key_float_view_upper_bg_color",
            "ime_skin_key_float_view_long_click_bg_color",
            "ime_skin_dark_key_float_view_long_click_bg_color",
        ):
            value = v7.KEY_PREVIEW_COLORS[semantic]
            self.assertTrue(value.startswith("#FF"), (semantic, value))


if __name__ == "__main__":
    unittest.main()
