import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v8 as v8


class V8Tests(unittest.TestCase):
    def test_wetype_tool_surfaces_match_release_evidence(self):
        self.assertEqual(
            v8.WETYPE_TOOL_RELEASE_SHA256,
            "9893b3416ce6ca20221d2afe49a166318c7e2c5b123dc709b14264c6b3f57eff",
        )
        self.assertEqual(
            v8.WETYPE_TOOL_SURFACE_COLORS["ime_emoji_keyboard_gradient_bg_color"],
            "#00000000",
        )
        self.assertEqual(
            v8.WETYPE_TOOL_SURFACE_COLORS["ime_keyboard_full_gradient_bg_color"],
            "#00000000",
        )
        self.assertEqual(
            v8.WETYPE_TOOL_SURFACE_COLORS["ime_skin_clipboard_item_bg_color"],
            "#46FFFFFF",
        )

    def test_surface_resolution_and_patch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hld = root / "smali_classes2/com/tencent/wetype/plugin/hld/r"
            hld.mkdir(parents=True)
            values = root / "res/values"
            values.mkdir(parents=True)
            smali = [
                ".class public final Lcom/tencent/wetype/plugin/hld/r/RColor;",
                ".super Ljava/lang/Object;",
            ]
            public = ['<?xml version="1.0" encoding="utf-8"?><resources>']
            colors = ['<?xml version="1.0" encoding="utf-8"?><resources>']
            for index, semantic in enumerate(v8.WETYPE_TOOL_SURFACE_COLORS, start=1):
                rid = 0x7F060100 + index
                obfuscated = f"tool_surface_{index}"
                smali.append(f".field public static {semantic}:I = 0x{rid:08x}")
                public.append(
                    f'<public type="color" name="{obfuscated}" id="0x{rid:08x}" />'
                )
                colors.append(f'<color name="{obfuscated}">#FF123456</color>')
            public.append("</resources>")
            colors.append("</resources>")
            (hld / "RColor.smali").write_text("\n".join(smali), encoding="utf-8")
            (values / "public.xml").write_text("\n".join(public), encoding="utf-8")
            (values / "colors.xml").write_text("\n".join(colors), encoding="utf-8")

            result = v8._apply_tool_surface_resources(root)
            out = (values / "colors.xml").read_text(encoding="utf-8")
            self.assertEqual(
                len(result["changed_resources"]), len(v8.WETYPE_TOOL_SURFACE_COLORS)
            )
            self.assertGreaterEqual(out.count("#00000000"), 4)
            self.assertIn("#46FFFFFF", out)
            self.assertIn("#24FFFFFF", out)

    def test_panel_class_gets_event_hooks_without_global_polling(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = (
                root
                / "smali_classes2/com/tencent/wetype/plugin/hld/keyboard/S35RequestAIKeyboard.smali"
            )
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public Lcom/tencent/wetype/plugin/hld/keyboard/S35RequestAIKeyboard;\n"
                ".super Landroid/widget/FrameLayout;\n"
                ".method public setVisibility(I)V\n"
                "    .locals 0\n"
                "    invoke-super {p0, p1}, Landroid/widget/FrameLayout;->setVisibility(I)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )

            report = v8._patch_one_panel_class(
                root, "com.tencent.wetype.plugin.hld.keyboard.S35RequestAIKeyboard"
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "ColorOSV2PanelLifecycleV8;->onPanelVisibilityChanged", text
            )
            self.assertIn("ColorOSV2PanelLifecycleV8;->onPanelAttached", text)
            self.assertIn("ColorOSV2PanelLifecycleV8;->onPanelDetached", text)
            self.assertEqual(
                report["operations"]["setVisibility"], "existing_method_hooked"
            )
            self.assertEqual(
                report["operations"]["onAttachedToWindow"], "override_added"
            )

    def test_detach_hook_runs_before_existing_detach_body(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = (
                root
                / "smali/com/tencent/wetype/plugin/hld/emoji/ImeEmojiBoardView.smali"
            )
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public Lcom/tencent/wetype/plugin/hld/emoji/ImeEmojiBoardView;\n"
                ".super Landroid/widget/FrameLayout;\n"
                ".method protected onDetachedFromWindow()V\n"
                "    .locals 0\n"
                "    invoke-super {p0}, Landroid/widget/FrameLayout;->onDetachedFromWindow()V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            v8._patch_one_panel_class(
                root, "com.tencent.wetype.plugin.hld.emoji.ImeEmojiBoardView"
            )
            text = path.read_text(encoding="utf-8")
            callback = text.index("ColorOSV2PanelLifecycleV8;->onPanelDetached")
            super_call = text.index("FrameLayout;->onDetachedFromWindow()V")
            self.assertLess(callback, super_call)

    def test_global_layout_is_neutralized_and_runnable_collapses_v6_v7(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            monet = root / "smali_classes2/com/tencent/wetype/monet"
            monet.mkdir(parents=True)
            listener = monet / "ColorOSV2Round$GlobalLayoutListener.smali"
            listener.write_text(
                ".class final Lcom/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener;\n"
                ".super Ljava/lang/Object;\n"
                ".method public onGlobalLayout()V\n"
                "    .locals 1\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->applyTree(Landroid/view/View;)V\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->apply(Landroid/view/View;)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            runnable = monet / "OplusKeyboardBlur$ApplyRunnable.smali"
            runnable.write_text(
                ".class final Lcom/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable;\n"
                ".super Ljava/lang/Object;\n"
                ".method public run()V\n"
                "    .locals 1\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2Round;->install(Landroid/view/View;)V\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V\n"
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->apply(Landroid/view/View;)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            visual_v7 = {
                "base_v6": {
                    "base_v5": {
                        "injected_helpers": [
                            "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round.smali",
                            "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener.smali",
                        ],
                        "runnable": "smali_classes2/com/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable.smali",
                    }
                }
            }

            v8._neutralize_global_layout(root, visual_v7)
            v8._patch_apply_runnable(root, visual_v7)
            ltext = listener.read_text(encoding="utf-8")
            rtext = runnable.read_text(encoding="utf-8")
            self.assertNotIn("applyTree", ltext)
            self.assertNotIn("HierarchyV6;->apply", ltext)
            self.assertNotIn("PanelHierarchyV7;->apply", ltext)
            self.assertIn("ColorOSV2PanelLifecycleV8;->reconcileRoot", rtext)
            self.assertNotIn("ColorOSV2HierarchyV6;->apply", rtext)
            self.assertNotIn("ColorOSV2PanelHierarchyV7;->apply", rtext)

    def test_performance_contract_uses_one_root_blur_and_event_reconcile(self):
        text = v8.LIFECYCLE_SMALI
        self.assertNotIn("ViewRootManager", text)
        self.assertIn("View;->post(Ljava/lang/Runnable;)Z", text)
        self.assertIn("ColorOSV2Round;->applyTree", text)
        # Event helper reuses V6/V7 reconciliation; no permanent global layout listener.
        self.assertNotIn("addOnGlobalLayoutListener", text)


if __name__ == "__main__":
    unittest.main()
