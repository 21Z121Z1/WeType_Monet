import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v13_fix as v13


class V13LocalBlurTests(unittest.TestCase):
    def test_helper_uses_coloros_manager_not_hidden_viewrootimpl(self):
        text = v13.LOCAL_HELPER_SMALI
        self.assertIn("Lcom/oplus/view/ViewRootManager;", text)
        self.assertIn("->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;", text)
        self.assertIn("->setBlurRadius(I)V", text)
        self.assertIn("->setColor(I)V", text)
        self.assertIn("Landroid/view/View;->getRootView()Landroid/view/View;", text)
        self.assertNotIn("getViewRootImpl", text)
        self.assertNotIn("createBackgroundBlurDrawable", text)
        self.assertNotIn("Landroid/view/ViewRootImpl;", text)
        self.assertNotIn("OplusBlurParam", text)
        self.assertNotIn("->setBlurParams(", text)

    def test_bubble_is_fail_closed(self):
        text = v13.LOCAL_HELPER_SMALI
        self.assertIn("hasBubbleBlur", text)
        self.assertIn("applyBubbleFill", text)
        self.assertIn("const/16 v0, 0x5a", text)
        self.assertIn("const/16 v0, 0xff", text)
        self.assertIn("installBubble failed closed", text)
        # Resource fallback itself stays opaque.
        for semantic, value in v13.V13_KEY_PREVIEW_COLORS.items():
            if semantic.endswith("click_color"):
                continue
            self.assertTrue(value.startswith("#FF"), (semantic, value))

    def test_floating_is_transactional(self):
        text = v13.LOCAL_HELPER_SMALI
        self.assertIn("WeTypeBlurCarrier_Float", text)
        self.assertIn("WeTypeBlurHighlight_Float", text)
        self.assertIn("IdentityHashMap", text)
        self.assertIn("floating blur unavailable; original backgrounds kept", text)
        set_blur_bg = text.index(
            "invoke-virtual {v3, v9}, Landroid/view/View;->setBackground"
        )
        strip = text.index(
            "->stripBackgrounds(Landroid/view/View;Ljava/util/IdentityHashMap;)V"
        )
        self.assertLess(set_blur_bg, strip)

    def test_no_high_frequency_local_hooks(self):
        text = v13.LOCAL_HELPER_SMALI
        self.assertNotIn("onGlobalLayout", text)
        self.assertNotIn("onWindowVisibilityChanged", text)
        self.assertNotIn("setAlpha(F)V", text)

    def test_bubble_painter_patch_is_runtime_gated(self):
        source = '''.class public Lcom/tencent/wetype/plugin/hld/floatview/u;\n.super Landroid/widget/FrameLayout;\n.method protected onDraw(Landroid/graphics/Canvas;)V\n    .locals 5\n    sget v4, Lcom/tencent/wetype/plugin/hld/o;->ime_color_12:I\n    invoke-static {v2, v4}, Lcom/tencent/wetype/plugin/hld/utils/q1;->m(Landroid/content/Context;I)I\n    move-result v2\n    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setColor(I)V\n    sget v3, Lcom/tencent/wetype/plugin/hld/o;->ime_color_09:I\n    invoke-static {v2, v3}, Lcom/tencent/wetype/plugin/hld/utils/q1;->m(Landroid/content/Context;I)I\n    move-result v2\n    invoke-virtual {v1, v2}, Landroid/graphics/Paint;->setColor(I)V\n    return-void\n.end method\n'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "smali" / "com/tencent/wetype/plugin/hld/floatview/u.smali"
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding="utf-8")
            report = v13.base._patch_bubble_fill_fail_closed(root)
            patched = path.read_text(encoding="utf-8")
            self.assertIn("fail-closed", report["fill_policy"])
            self.assertEqual(patched.count("->applyBubbleFill"), 1)
            self.assertEqual(patched.count("->restoreBubbleStroke"), 1)


if __name__ == "__main__":
    unittest.main()
