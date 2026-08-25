import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_blur


MANIFEST = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.tencent.wetype">
  <application>
    <service android:name=".ime.WeTypeService" android:permission="android.permission.BIND_INPUT_METHOD">
      <intent-filter><action android:name="android.view.InputMethod"/></intent-filter>
    </service>
  </application>
</manifest>
'''

SERVICE = '''.class public Lcom/tencent/wetype/ime/WeTypeService;
.super Lcom/tencent/wetype/ime/BaseIme;
'''

BASE = '''.class public Lcom/tencent/wetype/ime/BaseIme;
.super Landroid/inputmethodservice/InputMethodService;

.method public onCreateInputView()Landroid/view/View;
    .locals 1
    new-instance v0, Landroid/view/View;
    invoke-direct {v0, p0}, Landroid/view/View;-><init>(Landroid/content/Context;)V
    return-object v0
.end method
'''


class OplusBlurPatchTests(unittest.TestCase):
    def make_tree(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / "AndroidManifest.xml").write_text(MANIFEST, encoding="utf-8")
        smali = root / "smali_classes2" / "com/tencent/wetype/ime"
        smali.mkdir(parents=True)
        (smali / "WeTypeService.smali").write_text(SERVICE, encoding="utf-8")
        (smali / "BaseIme.smali").write_text(BASE, encoding="utf-8")
        values = root / "res/values"
        values.mkdir(parents=True)
        (values / "colors.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><resources>'
            '<color name="a">#ff000000</color><color name="b">#ffffffff</color>'
            '</resources>',
            encoding="utf-8",
        )
        config = root / "target.json"
        config.write_text(
            json.dumps(
                {
                    "theme_colors": [
                        {
                            "unobfuscated_key": "ime_skin_candidate_start_color",
                            "obfuscated_key": "a",
                        },
                        {
                            "unobfuscated_key": "ime_skin_keyboard_background",
                            "obfuscated_key": "b",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        return temp_dir, root, config

    def test_find_ime_service(self):
        temp_dir, root, _ = self.make_tree()
        try:
            self.assertEqual(
                oplus_blur.find_ime_service_descriptors(root / "AndroidManifest.xml"),
                ["Lcom/tencent/wetype/ime/WeTypeService;"],
            )
        finally:
            temp_dir.cleanup()

    def test_apply_patches_superclass_and_resources(self):
        temp_dir, root, config = self.make_tree()
        try:
            result = oplus_blur.apply_oplus_private_blur(root, config)
            base = (root / "smali_classes2/com/tencent/wetype/ime/BaseIme.smali").read_text()
            self.assertIn("OplusKeyboardBlur;->apply(Landroid/view/View;)V", base)
            self.assertEqual(result["smali"]["patched_calls"], 1)
            helper = root / "smali_classes2/com/tencent/wetype/monet/OplusKeyboardBlur.smali"
            self.assertTrue(helper.is_file())
            colors = (root / "res/values/colors.xml").read_text()
            self.assertEqual(colors.count("#00000000"), 2)
        finally:
            temp_dir.cleanup()

    def test_set_input_view_fallback(self):
        temp_dir, root, config = self.make_tree()
        try:
            base_path = root / "smali_classes2/com/tencent/wetype/ime/BaseIme.smali"
            base_path.write_text(
                '''.class public Lcom/tencent/wetype/ime/BaseIme;\n"
                ".super Landroid/inputmethodservice/InputMethodService;\n"
                ".method public install(Landroid/view/View;)V\n"
                "    .locals 0\n"
                "    invoke-virtual {p0, p1}, Landroid/inputmethodservice/InputMethodService;->setInputView(Landroid/view/View;)V\n"
                "    return-void\n"
                ".end method\n'''.replace('"\n                "', ''),
                encoding="utf-8",
            )
            result = oplus_blur.apply_oplus_private_blur(root, config)
            self.assertEqual(result["smali"]["patched_calls"], 1)
            self.assertIn("invoke-static {p1}", base_path.read_text())
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
