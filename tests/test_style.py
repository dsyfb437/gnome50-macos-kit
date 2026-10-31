import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import style

class StyleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_home = style.d.HOME
        style.d.HOME = self.root
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'gnome-shell.css').write_text('/* original */')
        (self.source / 'asset.svg').write_text('<svg/>')
        self.overlay = self.root / 'overlay.css'
        self.overlay.write_text('#panel { color: black; }')
    def tearDown(self):
        style.d.HOME = self.old_home
        self.tmp.cleanup()
    def test_plan_does_not_write(self):
        style.plan(self.source, self.overlay)
        self.assertFalse((self.root / '.themes').exists())
    def test_build_preserves_source_and_reuses_exact_copy(self):
        src, inv, css, name, dest = style.plan(self.source, self.overlay)
        style.build(src, inv, css, dest)
        before = style.d.digest(dest)
        style.build(src, inv, css, dest)
        self.assertEqual(style.d.digest(dest), before)
        self.assertEqual(style.d.digest(src), inv)
        self.assertIn(css, (dest / 'gnome-shell/gnome-shell.css').read_bytes())
    def test_refuse_modified_destination(self):
        src, inv, css, name, dest = style.plan(self.source, self.overlay)
        style.build(src, inv, css, dest)
        f = dest / 'gnome-shell/gnome-shell.css'
        f.write_text('user edit')
        with self.assertRaises(RuntimeError): style.build(src, inv, css, dest)
        self.assertEqual(f.read_text(), 'user edit')
    def test_refuse_external_and_absolute_links(self):
        p = self.source / 'link'
        p.symlink_to('../overlay.css')
        with self.assertRaises(RuntimeError): style.plan(self.source, self.overlay)
        p.unlink();p.symlink_to(self.source / 'asset.svg')
        with self.assertRaises(RuntimeError): style.plan(self.source, self.overlay)
    def test_source_mutation_stops_install(self):
        src, inv, css, name, dest = style.plan(self.source, self.overlay)
        (src / 'asset.svg').write_text('changed')
        with self.assertRaises(RuntimeError): style.build(src, inv, css, dest)
        self.assertFalse(dest.exists())

if __name__ == '__main__': unittest.main()
