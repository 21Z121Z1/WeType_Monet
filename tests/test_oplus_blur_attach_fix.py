import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from oplus_blur_attach_fix import make_attachment_safe


ORIGINAL_HELPER = '''.class public final Lcom/tencent/wetype/monet/OplusKeyboardBlur;
.super Ljava/lang/Object;

.method public static apply(Landroid/view/View;)V
    .locals 0
    return-void
.end method
'''


class OplusBlurAttachFixTests(unittest.TestCase):
    def test_transforms_apply_into_attach_safe_wrapper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            helper = root / "smali_classes2/com/tencent/wetype/monet/OplusKeyboardBlur.smali"
            helper.parent.mkdir(parents=True)
            helper.write_text(ORIGINAL_HELPER, encoding="utf-8")
            report = {
                "smali": {
                    "helper_file": "smali_classes2/com/tencent/wetype/monet/OplusKeyboardBlur.smali"
                }
            }

            result = make_attachment_safe(root, report)
            transformed = helper.read_text(encoding="utf-8")
            self.assertIn(".method public static apply(Landroid/view/View;)V", transformed)
            self.assertIn(".method public static applyNow(Landroid/view/View;)V", transformed)
            self.assertIn("isAttachedToWindow()Z", transformed)
            self.assertIn("addOnAttachStateChangeListener", transformed)

            listener = root / result["listener_file"]
            self.assertTrue(listener.is_file())
            listener_text = listener.read_text(encoding="utf-8")
            self.assertIn("onViewAttachedToWindow", listener_text)
            self.assertIn("removeOnAttachStateChangeListener", listener_text)
            self.assertIn("OplusKeyboardBlur;->applyNow", listener_text)


if __name__ == "__main__":
    unittest.main()
