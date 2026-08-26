import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_visual_v9 as v9


class V9OverlayRegressionTests(unittest.TestCase):
    def test_full_overlay_set_covers_device_regressions(self):
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.S15CustomPhraseAndClipboardKeyboard",
            v9.PANEL_CLASSES,
        )
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.S31InspirationKeyboard",
            v9.PANEL_CLASSES,
        )
        self.assertIn(
            "com.tencent.wetype.plugin.hld.keyboard.selfdraw.S11EmojiKeyboard",
            v9.PANEL_CLASSES,
        )

    def test_overlay_helper_has_one_alpha_owner_and_effective_visibility(self):
        text = v9._overlay_helper_smali()
        self.assertIn("suppressedAlpha:Ljava/util/WeakHashMap;", text)
        self.assertIn("S15CustomPhraseAndClipboardKeyboard", text)
        self.assertIn("S31InspirationKeyboard", text)
        self.assertIn("S11EmojiKeyboard", text)
        self.assertIn("->getAlpha()F", text)
        self.assertIn("0x3c23d70a", text)
        self.assertIn("->getParent()Landroid/view/ViewParent;", text)
        self.assertIn("->setAlpha(F)V", text)
        self.assertNotIn("selfdraw.S5SymbolKeyboard", text)

    def test_reconcile_root_replaces_v6_alpha_owner(self):
        original = """.method public static reconcileRoot(Landroid/view/View;)V
    .locals 0
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V
    invoke-static {p0}, Lcom/tencent/wetype/monet/ColorOSV2PanelHierarchyV7;->apply(Landroid/view/View;)V
    return-void
.end method
"""
        out = v9._replace_reconcile_root(original)
        self.assertNotIn("ColorOSV2HierarchyV6;->apply", out)
        self.assertEqual(out.count("ColorOSV2OverlayHierarchyV9;->apply"), 1)
        self.assertEqual(out.count("ColorOSV2PanelHierarchyV7;->apply"), 1)

    def test_transition_reconcile_has_delayed_final_state_repair(self):
        original = """.method private static postReconcile(Landroid/view/View;)V
    .locals 1
    return-void
.end method
"""
        out = v9._replace_post_reconcile(original)
        self.assertIn("->post(Ljava/lang/Runnable;)Z", out)
        self.assertIn("->postDelayed(Ljava/lang/Runnable;J)Z", out)
        self.assertIn("const-wide/16 v1, 0x30", out)

    def test_panel_hooks_cover_ancestor_window_and_alpha_transitions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            class_name = v9.PANEL_CLASSES[0]
            path = root / "smali" / (class_name.replace(".", "/") + ".smali")
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public L" + class_name.replace(".", "/") + ";\n"
                ".super Landroid/view/View;\n",
                encoding="utf-8",
            )
            report = v9._patch_panel_effective_visibility(root, class_name)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(report["operations"]["onVisibilityChanged"], "override_added")
            self.assertEqual(report["operations"]["onWindowVisibilityChanged"], "override_added")
            self.assertEqual(report["operations"]["setAlpha"], "override_added")
            self.assertIn("onVisibilityChanged(Landroid/view/View;I)V", text)
            self.assertIn("onWindowVisibilityChanged(I)V", text)
            self.assertIn("setAlpha(F)V", text)
            self.assertEqual(
                text.count(
                    "ColorOSV2PanelLifecycleV8;->onPanelVisibilityChanged(Landroid/view/View;)V"
                ),
                3,
            )

    def test_existing_visibility_method_is_hooked_without_replacing_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            class_name = v9.PANEL_CLASSES[1]
            path = root / "smali_classes2" / (class_name.replace(".", "/") + ".smali")
            path.parent.mkdir(parents=True)
            path.write_text(
                ".class public L" + class_name.replace(".", "/") + ";\n"
                ".super Landroid/view/View;\n"
                ".method protected onVisibilityChanged(Landroid/view/View;I)V\n"
                "    .locals 0\n"
                "    invoke-super {p0, p1, p2}, Landroid/view/View;->onVisibilityChanged(Landroid/view/View;I)V\n"
                "    return-void\n"
                ".end method\n",
                encoding="utf-8",
            )
            report = v9._patch_panel_effective_visibility(root, class_name)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(
                report["operations"]["onVisibilityChanged"],
                "existing_method_hooked",
            )
            self.assertIn(
                "invoke-super {p0, p1, p2}, Landroid/view/View;->onVisibilityChanged",
                text,
            )
            self.assertIn(
                "ColorOSV2PanelLifecycleV8;->onPanelVisibilityChanged",
                text,
            )

    def test_runtime_audit_rejects_any_remaining_v6_owner(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            smali = root / "smali/test.smali"
            smali.parent.mkdir(parents=True)
            callbacks = (
                "ColorOSV2PanelLifecycleV8;->onPanelVisibilityChanged(Landroid/view/View;)V\n"
                * (len(v9.PANEL_CLASSES) * 4)
            )
            smali.write_text(
                "ColorOSV2OverlayHierarchyV9;->apply(Landroid/view/View;)V\n"
                + callbacks,
                encoding="utf-8",
            )
            audit = v9._audit_v9_runtime_calls(root)
            self.assertEqual(audit["v6_apply_callers"], 0)
            self.assertEqual(audit["v9_overlay_apply_callers"], 1)

            smali.write_text(
                smali.read_text(encoding="utf-8")
                + "ColorOSV2HierarchyV6;->apply(Landroid/view/View;)V\n",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                v9._audit_v9_runtime_calls(root)


if __name__ == "__main__":
    unittest.main()
