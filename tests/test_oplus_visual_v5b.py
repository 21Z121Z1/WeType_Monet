import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "v5b", Path(__file__).resolve().parents[1] / "scripts" / "oplus_visual_v5b.py"
)
v5b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v5b)


class V5BTests(unittest.TestCase):
    def test_font_loader_with_debug_directives_is_rewritten(self):
        source = '''    .line 41\n    invoke-static {v0, v1}, Landroid/graphics/Typeface;->createFromAsset(Landroid/content/res/AssetManager;Ljava/lang/String;)Landroid/graphics/Typeface;\n    .line 42\n    .local v2, "face":Landroid/graphics/Typeface;\n    move-result-object v2\n    invoke-virtual {p0, v2}, Landroid/graphics/Paint;->setTypeface(Landroid/graphics/Typeface;)Landroid/graphics/Typeface;\n'''
        patched, count = v5b.patch_font_factories_directive_tolerant(source)
        self.assertEqual(count, 1)
        self.assertIn(
            "sget-object v2, Landroid/graphics/Typeface;->DEFAULT:Landroid/graphics/Typeface;",
            patched,
        )
        self.assertNotIn("createFromAsset", patched)
        self.assertNotIn("move-result-object v2", patched)
        self.assertIn('.local v2, "face"', patched)

    def test_unrelated_typeface_creation_is_preserved(self):
        source = '''    invoke-static {v0, v1}, Landroid/graphics/Typeface;->create(Ljava/lang/String;I)Landroid/graphics/Typeface;\n    move-result-object v2\n'''
        patched, count = v5b.patch_font_factories_directive_tolerant(source)
        self.assertEqual(count, 0)
        self.assertEqual(patched, source)


if __name__ == "__main__":
    unittest.main()
