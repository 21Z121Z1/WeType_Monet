import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v12 as v12


def write_class(root: Path, class_name: str, body: str) -> Path:
    path = root / "smali" / (class_name.replace(".", "/") + ".smali")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class V12ToolParityTests(unittest.TestCase):
    def test_local_helper_uses_existing_viewrootimpl_factory(self):
        helper = v12.LOCAL_HELPER_SMALI
        self.assertIn('const-string v2, "getViewRootImpl"', helper)
        self.assertIn('const-string v3, "createBackgroundBlurDrawable"', helper)
        self.assertIn('const-string v3, "setBlurRadius"', helper)
        self.assertIn('const-string v3, "setCornerRadius"', helper)
        self.assertNotIn("Lcom/oplus/view/ViewRootManager;", helper)
        self.assertIn("WeTypeBlurCarrier_Float", helper)
        self.assertIn("WeTypeBlurHighlight_Float", helper)
        self.assertIn("Ljava/util/IdentityHashMap;", helper)
        self.assertIn("restoreBackgrounds", helper)

    def test_bubble_creation_hook_is_after_background_reset_and_N(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = write_class(
                root,
                v12.FLOAT_BASE_CLASS,
                '.class public Lcom/tencent/wetype/plugin/hld/floatview/u;\n'
                '.super Landroid/widget/FrameLayout;\n'
                f'.method public final v{v12.BUBBLE_METHOD_SIGNATURE}\n'
                '    .locals 1\n'
                '    if-eqz p2, :early\n'
                '    invoke-virtual {p2, p0}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V\n'
                '    const/4 v0, 0x0\n'
                '    invoke-virtual {p0, v0}, Landroid/view/View;->setBackgroundColor(I)V\n'
                '    invoke-virtual {p0}, Lcom/tencent/wetype/plugin/hld/floatview/u;->N()V\n'
                '    return-void\n'
                '    :early\n'
                '    return-void\n'
                '.end method\n',
            )
            first = v12._patch_bubble_creation(root)
            second = v12._patch_bubble_creation(root)
            text = p.read_text(encoding="utf-8")
            call = f"{v12.LOCAL_DESCRIPTOR}->installBubble(Landroid/view/View;)V"
            self.assertEqual(first["creation_hook"], "inserted_after_N")
            self.assertEqual(second["creation_hook"], "already_hooked")
            self.assertEqual(text.count(call), 1)
            self.assertLess(text.index("setBackgroundColor(I)V"), text.index("->N()V"))
            self.assertLess(text.index("->N()V"), text.index(call))

    def test_bubble_fill_fades_only_fill_and_restores_stroke_alpha(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = write_class(
                root,
                v12.FLOAT_BASE_CLASS,
                '.class public Lcom/tencent/wetype/plugin/hld/floatview/u;\n'
                '.super Landroid/widget/FrameLayout;\n'
                '.method protected onDraw(Landroid/graphics/Canvas;)V\n'
                '    .locals 5\n'
                '    sget v4, Lcom/tencent/wetype/plugin/hld/o;->ime_color_12:I\n'
                '    move-result v2\n'
                '    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setColor(I)V\n'
                '    invoke-virtual {p1, v0, v1}, Landroid/graphics/Canvas;->drawPath(Landroid/graphics/Path;Landroid/graphics/Paint;)V\n'
                '    sget v3, Lcom/tencent/wetype/plugin/hld/o;->ime_color_09:I\n'
                '    move-result v2\n'
                '    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setColor(I)V\n'
                '    invoke-virtual {p1, v0, v1}, Landroid/graphics/Canvas;->drawPath(Landroid/graphics/Path;Landroid/graphics/Paint;)V\n'
                '    return-void\n'
                '.end method\n',
            )
            first = v12._patch_bubble_fill_alpha(root)
            second = v12._patch_bubble_fill_alpha(root)
            text = p.read_text(encoding="utf-8")
            self.assertEqual(first["fill_alpha"], "patched_exact_ime_color_12_site")
            self.assertEqual(first["stroke_alpha"], "restored_exact_ime_color_09_site")
            self.assertEqual(second["fill_alpha"], "already_patched")
            self.assertEqual(text.count("# WeTypeOplusV12 bubble fill alpha"), 1)
            self.assertEqual(text.count("# WeTypeOplusV12 bubble stroke alpha restore"), 1)
            self.assertLess(text.index("ime_color_12"), text.index("bubble fill alpha"))
            self.assertLess(text.index("bubble fill alpha"), text.index("ime_color_09"))
            self.assertLess(text.index("ime_color_09"), text.index("bubble stroke alpha restore"))

    def test_floating_hooks_are_attach_detach_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = write_class(
                root,
                v12.FLOATING_CONTENT_CLASS,
                '.class public final Lcom/tencent/wetype/plugin/hld/float/e;\n'
                '.super Landroidx/constraintlayout/widget/ConstraintLayout;\n'
                '.method protected onAttachedToWindow()V\n'
                '    .locals 1\n'
                '    invoke-super {p0}, Landroid/view/View;->onAttachedToWindow()V\n'
                '    const/4 v0, 0x1\n'
                '    return-void\n'
                '.end method\n'
                '.method protected onDetachedFromWindow()V\n'
                '    .locals 1\n'
                '    invoke-super {p0}, Landroid/view/View;->onDetachedFromWindow()V\n'
                '    return-void\n'
                '.end method\n',
            )
            first = v12._patch_floating_lifecycle(root)
            second = v12._patch_floating_lifecycle(root)
            text = p.read_text(encoding="utf-8")
            install = f"{v12.LOCAL_DESCRIPTOR}->installFloating(Landroid/view/View;)V"
            restore = f"{v12.LOCAL_DESCRIPTOR}->restoreFloating(Landroid/view/View;)V"
            self.assertEqual(first["attach"], "inserted_after_app_attach_work")
            self.assertEqual(first["detach"], "inserted_before_detach_work")
            self.assertEqual(second["attach"], "already_hooked")
            self.assertEqual(second["detach"], "already_hooked")
            self.assertEqual(text.count(install), 1)
            self.assertEqual(text.count(restore), 1)
            detach = text[text.index(".method protected onDetachedFromWindow"):]
            self.assertLess(detach.index(restore), detach.index("invoke-super"))
            self.assertNotIn("setAlpha(F)V", text)
            self.assertNotIn("onWindowVisibilityChanged", text)

    def test_preview_colors_are_translucent_material_tints(self):
        for semantic in (
            "ime_skin_key_float_view_upper_bg_color",
            "ime_skin_dark_key_float_view_upper_bg_color",
            "ime_skin_key_float_view_long_click_bg_color",
            "ime_skin_dark_key_float_view_long_click_bg_color",
        ):
            self.assertTrue(v12.V12_KEY_PREVIEW_COLORS[semantic].startswith("#5A"))

    def test_voice_is_deliberately_not_a_local_v12_blur_surface(self):
        self.assertEqual(v12.VOICE_CLASS, "com.tencent.wetype.plugin.hld.voice.ImeVoiceView")
        self.assertNotIn("ImeVoiceView", v12.LOCAL_HELPER_SMALI)


if __name__ == "__main__":
    unittest.main()
