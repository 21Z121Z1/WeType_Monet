import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v6 as v6


class V6Tests(unittest.TestCase):
    def test_selfdraw_key_round_calls_use_v6_radius_helper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scope = root / "smali_classes2/com/tencent/wetype/plugin/hld/keyboard/selfdraw/drawmethod"
            scope.mkdir(parents=True)
            path = scope / "a.smali"
            path.write_text(
                """.class public La;\n.super Ljava/lang/Object;\n"
                "    invoke-static {p0, p1, p2, p3, p4}, Lcom/tencent/wetype/monet/ColorOSV2Round;->drawRoundRect(Landroid/graphics/Canvas;Landroid/graphics/RectF;FFLandroid/graphics/Paint;)V\n"
                "    invoke-static {p0, p1, p2, p3}, Lcom/tencent/wetype/monet/ColorOSV2Round;->addRoundRect(Landroid/graphics/Path;Landroid/graphics/RectF;[FLandroid/graphics/Path$Direction;)V\n"
                """,
                encoding="utf-8",
            )

            result = v6._patch_key_round_calls(root)
            out = path.read_text(encoding="utf-8")
            self.assertEqual(result["calls"], 1)
            self.assertIn("ColorOSV2KeyRoundV6;->drawRoundRect", out)
            # Per-corner/asymmetric geometry must not be normalized.
            self.assertIn("ColorOSV2Round;->addRoundRect", out)
            self.assertIn("0x3e75c28f", v6.KEY_HELPER_SMALI)
            self.assertEqual(v6.KEY_RADIUS_RATIO, 0.24)

    def test_v5_runtime_outline_no_longer_flattens_drawable_radius(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = root / "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round.smali"
            helper.parent.mkdir(parents=True)
            helper.write_text(
                """.class public Lcom/tencent/wetype/monet/ColorOSV2Round;\n"
                "    invoke-virtual {p0, v1}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V\n"
                "    invoke-virtual {p0, v5}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadii([F)V\n"
                """,
                encoding="utf-8",
            )
            visual = {
                "injected_helpers": [
                    "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round.smali"
                ]
            }
            rel = v6._preserve_runtime_drawable_geometry(root, visual)
            out = helper.read_text(encoding="utf-8")
            self.assertEqual(
                rel, "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round.smali"
            )
            self.assertNotIn("->setCornerRadius(F)V", out)
            self.assertNotIn("->setCornerRadii([F)V", out)
            self.assertIn("preserve original drawable radius", out)

    def test_emoji_hierarchy_is_hooked_into_initial_and_global_layout_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            monet = root / "smali_classes2/com/tencent/wetype/monet"
            monet.mkdir(parents=True)
            listener = monet / "ColorOSV2Round$GlobalLayoutListener.smali"
            listener.write_text(
                """.class final Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;\n"
                ".super Ljava/lang/Object;\n"
                ".method public onGlobalLayout()V\n"
                "    .locals 1\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyTree(Landroid/view/View;)V\n"
                "    return-void\n"
                ".end method\n"
                """,
                encoding="utf-8",
            )
            runnable = monet / "OplusKeyboardBlur$ApplyRunnable.smali"
            runnable.write_text(
                """.class final Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;\n"
                ".super Ljava/lang/Object;\n"
                ".method public run()V\n"
                "    .locals 1\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->install(Landroid/view/View;)V\n"
                "    return-void\n"
                ".end method\n"
                """,
                encoding="utf-8",
            )
            visual = {
                "injected_helpers": [
                    "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round.smali",
                    "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener.smali",
                ],
                "runnable": "smali_classes2/com/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable.smali",
            }
            result = v6._patch_hierarchy_hooks(root, visual)
            call = "ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V"
            self.assertIn(call, listener.read_text(encoding="utf-8"))
            self.assertIn(call, runnable.read_text(encoding="utf-8"))
            self.assertIn("global_layout_listener", result)

    def test_hierarchy_helper_targets_real_emoji_roots_and_restores_alpha(self):
        text = v6.HIERARCHY_HELPER_SMALI
        self.assertIn(
            "com.tencent.wetype.plugin.hld.emoji.ImeEmojiBoardView", text
        )
        self.assertIn(
            "com.tencent.wetype.plugin.hld.emoji.ImeEmojiShowBoardView", text
        )
        self.assertIn("S11EmojiKeyboard", text)
        self.assertIn("S5SymbolKeyboard", text)
        self.assertIn("Ljava/util/WeakHashMap;->remove", text)
        self.assertIn("Landroid/view/View;->setAlpha(F)V", text)


if __name__ == "__main__":
    unittest.main()
