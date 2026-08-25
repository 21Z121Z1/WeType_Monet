import tempfile
import unittest
from pathlib import Path
import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "v5", Path(__file__).resolve().parents[1] / "scripts" / "oplus_visual_v5.py"
)
v5 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v5)

ROUND_SAMPLE = '''.class public Lcom/tencent/wetype/plugin/hld/keyboard/selfdraw/Test;\n.super Ljava/lang/Object;\n.method public draw(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V\n    .locals 0\n    invoke-virtual {p1, p2, p3, p4, p5}, Landroid/graphics/Canvas;->drawRoundRect(Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V\n    return-void\n.end method\n'''
FONT_SAMPLE = '''.class public Lcom/tencent/wetype/plugin/hld/keyboard/selfdraw/Font;\n.super Ljava/lang/Object;\n.method public f(Landroid/content/res/AssetManager;Ljava/lang/String;)Landroid/graphics/Typeface;\n    .locals 1\n    invoke-static {p1, p2}, Landroid/graphics/Typeface;->createFromAsset(Landroid/content/res/AssetManager;Ljava/lang/String;)Landroid/graphics/Typeface;\n    move-result-object v0\n    return-object v0\n.end method\n'''
RUNNABLE = '''.class final Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;\n.super Ljava/lang/Object;\n.method public run()V\n    .locals 1\n    iget-object v0, p0, Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;->target:Landroid/view/View;\n    invoke-static {v0}, Lcom/tencent/wetype/monet/OplusKeyboardBlur;->applyNow(Landroid/view/View;)V\n    return-void\n.end method\n'''


class V5Tests(unittest.TestCase):
    def tree(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        smali = root / "smali_classes2"
        (smali / "com/tencent/wetype/plugin/hld/keyboard/selfdraw").mkdir(parents=True)
        (smali / "com/tencent/wetype/plugin/hld/settings").mkdir(parents=True)
        helper_dir = smali / "com/tencent/wetype/monet"
        helper_dir.mkdir(parents=True)
        helper = helper_dir / "OplusKeyboardBlur.smali"
        helper.write_text(
            ".class public final Lcom/tencent/wetype/monet/OplusKeyboardBlur;\n"
            ".super Ljava/lang/Object;\n",
            encoding="utf-8",
        )
        (helper_dir / "OplusKeyboardBlur$ApplyRunnable.smali").write_text(
            RUNNABLE, encoding="utf-8"
        )
        return td, root, smali, helper

    def test_round_and_font_rewrites_are_scoped(self):
        td, root, smali, helper = self.tree()
        try:
            keyboard = smali / "com/tencent/wetype/plugin/hld/keyboard/selfdraw/Test.smali"
            keyboard.write_text(ROUND_SAMPLE, encoding="utf-8")
            font = smali / "com/tencent/wetype/plugin/hld/keyboard/selfdraw/Font.smali"
            font.write_text(FONT_SAMPLE, encoding="utf-8")
            settings = smali / "com/tencent/wetype/plugin/hld/settings/Test.smali"
            settings.write_text(
                ROUND_SAMPLE.replace("/keyboard/selfdraw/", "/settings/"),
                encoding="utf-8",
            )

            report = v5.patch_keyboard_smali(root)

            self.assertEqual(report["round_calls_rewritten"], 1)
            self.assertEqual(report["bundled_font_factories_rewritten"], 1)
            self.assertIn("ColorOSV2Round;->drawRoundRect", keyboard.read_text())
            self.assertIn("Typeface;->DEFAULT", font.read_text())
            self.assertIn("Canvas;->drawRoundRect", settings.read_text())
        finally:
            td.cleanup()

    def test_full_profile_injects_g2_helpers_and_runnable_hook(self):
        td, root, smali, helper = self.tree()
        try:
            (smali / "com/tencent/wetype/plugin/hld/keyboard/selfdraw/Test.smali").write_text(
                ROUND_SAMPLE, encoding="utf-8"
            )
            (smali / "com/tencent/wetype/plugin/hld/keyboard/selfdraw/Font.smali").write_text(
                FONT_SAMPLE, encoding="utf-8"
            )
            report = {"smali": {"helper_file": str(helper.relative_to(root))}}

            result = v5.apply_coloros_v2_visual_profile(root, report)

            round_helper = smali / "com/tencent/wetype/monet/ColorOSV2Round.smali"
            outline = smali / "com/tencent/wetype/monet/ColorOSV2Round$OutlineProvider.smali"
            font = smali / "com/tencent/wetype/monet/SystemFontBridge.smali"
            self.assertTrue(round_helper.is_file())
            self.assertTrue(outline.is_file())
            self.assertTrue(font.is_file())
            text = round_helper.read_text()
            self.assertIn("OplusSmoothRoundedManager;->getG2CornerType()I", text)
            self.assertIn("OplusSmoothRoundedManager;->getDefaultG2Weight()F", text)
            self.assertIn("OplusCanvas;->drawSmoothRoundRect", text)
            self.assertIn("OplusPathAdapter;->addSmoothRoundRect", text)
            self.assertIn("OplusOutlineAdapter;->setSmoothRoundRect", outline.read_text())
            self.assertIn("Typeface;->DEFAULT", font.read_text())
            runnable = (
                smali / "com/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable.smali"
            ).read_text()
            self.assertIn("ColorOSV2Round;->install(Landroid/view/View;)V", runnable)
            self.assertEqual(
                result["strategy"],
                "ColorOS 17 SystemUI G2/V2 smooth corners + default system font",
            )
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
