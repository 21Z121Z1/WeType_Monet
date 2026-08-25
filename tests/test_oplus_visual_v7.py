import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v7 as v7


class V7Tests(unittest.TestCase):
    def test_panel_policy_covers_named_tools_without_breaking_correction(self):
        own = set(v7.OWN_CHROME_PANEL_CLASSES)
        keep = set(v7.KEEP_GLOBAL_CANDIDATE_CLASSES)
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S11EmojiKeyboard", own
        )
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.S15CustomPhraseAndClipboardKeyboard",
            own,
        )
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.S35RequestAIKeyboard", own
        )
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.S20CorrectionKeyboard", keep
        )
        self.assertNotIn(
            "com.tencent.wetype.plugin.hld.keyboard.S20CorrectionKeyboard", own
        )
        self.assertEqual(
            v7.PANEL_AUDIT["spelling_correction"]["policy"],
            "keep_global_candidate",
        )

    def test_panel_helper_hides_only_visible_candidate_and_restores_exact_visibility(self):
        text = v7.PANEL_HELPER_SMALI
        self.assertIn(
            "com.tencent.wetype.plugin.hld.candidate.ImeCandidateView", text
        )
        self.assertIn("Landroid/view/View;->getVisibility()I", text)
        self.assertIn("const/4 v5, 0x4", text)  # INVISIBLE, not GONE
        self.assertIn("Ljava/util/WeakHashMap;->remove", text)
        self.assertIn("Landroid/view/View;->setVisibility(I)V", text)
        # Correction is deliberately absent from the suppression helper.
        self.assertNotIn("S20CorrectionKeyboard", text)

    def test_extra_pressed_and_preview_colors_resolve_and_patch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hld = root / "smali_classes2/com/tencent/wetype/plugin/hld"
            hld.mkdir(parents=True)
            values = root / "res/values"
            values.mkdir(parents=True)

            semantic_names = list(v7.EXTRA_STATE_COLORS)
            public_lines = ['<?xml version="1.0" encoding="utf-8"?><resources>']
            color_lines = ['<?xml version="1.0" encoding="utf-8"?><resources>']
            smali_lines = [
                ".class public final Lcom/tencent/wetype/plugin/hld/p;",
                ".super Ljava/lang/Object;",
            ]
            for index, semantic in enumerate(semantic_names, start=1):
                rid = 0x7F060000 + index
                obfuscated = f"c{index}"
                smali_lines.append(f".field public static {semantic}:I = 0x{rid:08x}")
                public_lines.append(
                    f'<public type="color" name="{obfuscated}" id="0x{rid:08x}" />'
                )
                color_lines.append(f'<color name="{obfuscated}">#FF123456</color>')
            public_lines.append("</resources>")
            color_lines.append("</resources>")
            (hld / "p.smali").write_text("\n".join(smali_lines), encoding="utf-8")
            (values / "public.xml").write_text("\n".join(public_lines), encoding="utf-8")
            (values / "colors.xml").write_text("\n".join(color_lines), encoding="utf-8")

            result = v7._apply_extra_state_colors(root)
            out = (values / "colors.xml").read_text(encoding="utf-8")
            self.assertEqual(len(result["changed_resources"]), len(semantic_names))
            self.assertIn("#5EFFFFFF", out)
            self.assertIn("#26000000", out)
            self.assertIn("#FFFFFFFF", out)
            self.assertIn("#FF2C2C2E", out)

    def test_hooks_attach_after_v6_hierarchy(self):
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
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V\n"
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
                "    invoke-static {v0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            v6_result = {
                "base_v5": {
                    "injected_helpers": [
                        "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round.smali",
                        "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener.smali",
                    ],
                    "runnable": "smali_classes2/com/tencent/wetype/monet/OplusKeyboardBlur$ApplyRunnable.smali",
                }
            }
            result = v7._patch_panel_hooks(root, v6_result)
            call = "ColorOSV2PanelHierarchyV7;->apply(Landroid/view/View;)V"
            self.assertIn(call, listener.read_text(encoding="utf-8"))
            self.assertIn(call, runnable.read_text(encoding="utf-8"))
            self.assertEqual(
                result["global_layout_listener"],
                "smali_classes2/com/tencent/wetype/monet/ColorOSV2Round$GlobalLayoutListener.smali",
            )

    def test_architecture_evidence_is_state_not_per_key_view(self):
        self.assertIn("ime_skin_color_btn_white_press", v7.PRESSED_STATE_COLORS)
        self.assertIn("ime_skin_key_float_view_upper_bg_color", v7.KEY_PREVIEW_COLORS)
        # Opaque preview background is intentional: this is a float-view surface,
        # not a key material overlay.
        self.assertEqual(
            v7.KEY_PREVIEW_COLORS["ime_skin_key_float_view_upper_bg_color"],
            "#FFFFFFFF",
        )


if __name__ == "__main__":
    unittest.main()
