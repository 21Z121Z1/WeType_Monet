import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import oplus_blur
from oplus_blur_attach_fix import make_attachment_safe
from oplus_blur_v2 import upgrade_to_keyboard_material_v2


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
.super Landroid/inputmethodservice/InputMethodService;

.method public onCreateInputView()Landroid/view/View;
    .locals 1
    new-instance v0, Landroid/view/View;
    invoke-direct {v0, p0}, Landroid/view/View;-><init>(Landroid/content/Context;)V
    return-object v0
.end method
'''


class OplusBlurV2Tests(unittest.TestCase):
    def make_tree(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / "AndroidManifest.xml").write_text(MANIFEST, encoding="utf-8")
        smali = root / "smali_classes2" / "com/tencent/wetype/ime"
        smali.mkdir(parents=True)
        (smali / "WeTypeService.smali").write_text(SERVICE, encoding="utf-8")
        values = root / "res/values"
        values.mkdir(parents=True)
        (values / "colors.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><resources>'
            '<color name="a">#ff000000</color>'
            '</resources>',
            encoding="utf-8",
        )
        config = root / "target.json"
        config.write_text(
            json.dumps(
                {
                    "theme_colors": [
                        {
                            "unobfuscated_key": "ime_skin_keyboard_background",
                            "obfuscated_key": "a",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return temp_dir, root, config

    def test_v2_replaces_helper_with_device_validated_material_path(self):
        temp_dir, root, config = self.make_tree()
        try:
            report = oplus_blur.apply_oplus_private_blur(root, config)
            make_attachment_safe(root, report)
            result = upgrade_to_keyboard_material_v2(root, report)

            helper = root / result["helper_file"]
            text = helper.read_text(encoding="utf-8")

            self.assertIn("->getRootView()Landroid/view/View;", text)
            self.assertIn("->getBackgroundBlurDrawable()Landroid/graphics/drawable/Drawable;", text)
            self.assertIn("->setBlurType(I)V", text)
            self.assertIn("->setMaterialParams(I[F[F)V", text)
            self.assertIn("0x3f800000", text)
            self.assertIn("->setSmoothCornerType(I)V", text)
            self.assertIn("0x40400000", text)
            self.assertIn("const/16 v4, 0x96", text)
            self.assertIn("0x41e00000", text)
            self.assertNotIn("->setColor(I)V", text)
            self.assertIn("0xfa", text)
            self.assertIn("0x2bc", text)

            self.assertTrue((root / result["listener_file"]).is_file())
            self.assertTrue((root / result["runnable_file"]).is_file())
            self.assertEqual(result["blur_type"], 2)
            self.assertEqual(result["blur_radius"], 150)
            self.assertEqual(
                result["material_params"],
                "setMaterialParams(1, [1,1,1,1], normalized RGBA tint)",
            )
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
