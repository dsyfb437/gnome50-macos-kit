#!/usr/bin/env python3
"""Runs only inside an isolated HOME + D-Bus. Does not use the user's dconf."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / 'desktop.py'

if '--inside-isolated-test' not in sys.argv:
    with tempfile.TemporaryDirectory(prefix='gnome-kit-tests-') as tmp:
        env = dict(os.environ)
        for name in ['DBUS_SESSION_BUS_ADDRESS', 'GSETTINGS_SCHEMA_DIR', 'DCONF_PROFILE',
                     'GSETTINGS_BACKEND', 'DISPLAY', 'WAYLAND_DISPLAY']:
            env.pop(name, None)
        env.update(HOME=tmp, XDG_CONFIG_HOME=tmp + '/.config', XDG_DATA_HOME=tmp + '/.local/share',
                   XDG_STATE_HOME=tmp + '/.local/state', XDG_CACHE_HOME=tmp + '/.cache',
                   XDG_RUNTIME_DIR=tmp + '/run', KIT_TEST_HOME=tmp, GVFS_DISABLE_FUSE='1', GIO_USE_VFS='local')
        Path(tmp, 'run').mkdir(mode=0o700)
        result = subprocess.run(['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                                 '--inside-isolated-test'], env=env)
        sys.exit(result.returncode)

sys.argv.remove('--inside-isolated-test')
assert os.environ['KIT_TEST_HOME'] == os.environ['HOME']
assert Path.home().name.startswith('gnome-kit-tests-')
HOME = Path.home()
STATE = HOME / '.local/state/gnome50-macos-kit'


def call(*args, ok=True, env=None):
    p = subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, env=env)
    if ok and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


def dc(*args):
    return subprocess.check_output(['dconf', *args], text=True).strip()


def backup(module):
    text = call('backup', '--module', module, '--execute').stdout
    return Path(next(x[7:] for x in text.splitlines() if x.startswith('BACKUP ')))


class DesktopTests(unittest.TestCase):
    def setUp(self):
        dc('reset', '-f', '/')  # isolated session only; guarded above
        self.gtk = HOME / '.config/gtk-4.0'
        if self.gtk.is_symlink():
            self.gtk.unlink()
        elif self.gtk.exists():
            shutil.rmtree(self.gtk)
        self.gtk.mkdir(parents=True)
        self.css = self.gtk / 'gtk.css'
        self.css.write_text('original custom CSS\n')

    def test_01_default_status_is_readonly(self):
        old = list(STATE.glob('backups/*'))
        data = json.loads(call().stdout)
        self.assertIn('settings', data)
        self.assertEqual(list(STATE.glob('backups/*')), old)
        self.assertEqual(self.css.read_text(), 'original custom CSS\n')

    def test_02_dry_run_never_creates_state(self):
        old = list(STATE.glob('backups/*'))
        before = dc('dump', '/')
        for cmd in ['apply', 'backup']:
            call(cmd, '--module', 'buttons', '--dry-run')
        self.assertEqual(before, dc('dump', '/'))
        self.assertEqual(old, list(STATE.glob('backups/*')))

    def test_03_exact_unset_key_restoration(self):
        key = '/org/gnome/desktop/wm/preferences/button-layout'
        self.assertEqual(dc('read', key), '')
        p = call('apply', '--module', 'buttons', '--execute')
        source = Path(next(x[7:] for x in p.stdout.splitlines() if x.startswith('BACKUP ')))
        self.assertEqual(dc('read', key), "'close,minimize,maximize:'")
        call('restore', '--module', 'buttons', '--from', str(source), '--execute')
        self.assertEqual(dc('read', key), '')

    def test_04_preserves_explicit_prior_value(self):
        key = '/org/gnome/desktop/wm/preferences/button-layout'
        dc('write', key, "'menu:close'")
        source = backup('buttons')
        call('apply', '--module', 'buttons', '--execute')
        call('restore', '--module', 'buttons', '--from', str(source), '--execute')
        self.assertEqual(dc('read', key), "'menu:close'")

    def test_05_gtk4_roundtrip_and_safety_backup(self):
        (self.gtk / 'gtk-dark.css').symlink_to('gtk.css')
        source = backup('gtk4')
        self.css.write_text('modified\n')
        (self.gtk / 'new.css').write_text('new')
        p = call('restore', '--module', 'gtk4', '--from', str(source), '--execute')
        self.assertEqual(self.css.read_text(), 'original custom CSS\n')
        self.assertFalse((self.gtk / 'new.css').exists())
        self.assertTrue((self.gtk / 'gtk-dark.css').is_symlink())
        safety = Path(next(x[7:] for x in p.stdout.splitlines() if x.startswith('BACKUP ')))
        call('restore', '--module', 'gtk4', '--from', str(safety), '--execute')
        self.assertEqual(self.css.read_text(), 'modified\n')

    def test_06_absent_path_restores_to_absence(self):
        shutil.rmtree(self.gtk)
        source = backup('gtk4')
        self.gtk.mkdir(); self.css.write_text('created later')
        call('restore', '--module', 'gtk4', '--from', str(source), '--execute')
        self.assertFalse(self.gtk.exists())

    def test_07_tampered_payload_refused_before_writes(self):
        source = backup('gtk4')
        (source / 'files/gtk4-0/gtk.css').write_text('tampered')
        before = self.css.read_text()
        self.assertNotEqual(call('restore', '--module', 'gtk4', '--from', str(source), '--execute', ok=False).returncode, 0)
        self.assertEqual(self.css.read_text(), before)

    def test_08_manifest_tampering_refused(self):
        source = backup('buttons')
        (source / 'manifest.json').write_text('{}')
        self.assertNotEqual(call('restore', '--module', 'buttons', '--from', str(source), '--execute', ok=False).returncode, 0)

    def test_09_extension_settings_do_not_enable_extensions(self):
        enabled = '/org/gnome/shell/enabled-extensions'
        blur = '/org/gnome/shell/extensions/blur-my-shell/panel/blur'
        dc('write', enabled, "['dhruva@test']")
        dc('write', blur, 'true')
        source = backup('extension-settings')
        dc('write', blur, 'false')
        dc('write', '/org/gnome/shell/extensions/test/extra', 'true')
        call('restore', '--module', 'extension-settings', '--from', str(source), '--execute')
        self.assertEqual(dc('read', blur), 'true')
        self.assertEqual(dc('read', enabled), "['dhruva@test']")
        self.assertEqual(dc('read', '/org/gnome/shell/extensions/test/extra'), '')

    def test_10_no_implicit_all_or_forbidden_module(self):
        for args in [('apply',), ('apply', '--module', 'all'), ('apply', '--module', 'power'),
                     ('apply', '--module', 'gtk4'), ('restore', '--module', 'gtk4')]:
            self.assertNotEqual(call(*args, ok=False).returncode, 0)

    def test_11_symlink_parent_refused(self):
        parent = HOME / '.local/share'
        ext = parent / 'themes'
        parent.mkdir(parents=True, exist_ok=True)
        elsewhere = HOME / 'redirect'; elsewhere.mkdir(exist_ok=True)
        # An allowlisted root may itself be a symlink, but its parent must not.
        linkroot = HOME / 'linkconfig'; linkroot.symlink_to(elsewhere)
        env = dict(os.environ, XDG_CONFIG_HOME=str(linkroot))
        p = call('backup', '--module', 'gtk4', '--execute', env=env, ok=False)
        self.assertNotEqual(p.returncode, 0)
        linkroot.unlink()

    def test_12_transaction_rolls_back_on_write_failure(self):
        # Fault injection: first write succeeds, second one fails. Rollback uses real dconf.
        bin_dir = HOME / 'test-bin'; bin_dir.mkdir(exist_ok=True)
        real = shutil.which('gsettings')
        wrapper = bin_dir / 'gsettings'
        wrapper.write_text('#!/usr/bin/env python3\nimport os,sys\n'
                           'if "set" in sys.argv and "cursor-theme" in sys.argv: sys.exit(9)\n'
                           f'os.execv({real!r}, [{real!r}]+sys.argv[1:])\n')
        wrapper.chmod(0o700)
        theme = HOME / '.themes/WhiteSur-Light/gtk-3.0'; theme.mkdir(parents=True, exist_ok=True)
        (theme / 'gtk.css').write_text('/* fixture */')
        for name in ['WhiteSur', 'WhiteSur-cursors']:
            d = HOME / '.icons' / name; d.mkdir(parents=True, exist_ok=True)
            (d / 'index.theme').write_text('[Icon Theme]\nName=' + name)
        key = '/org/gnome/desktop/interface/gtk-theme'
        dc('write', key, "'MyOriginalTheme'")
        env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'])
        result = call('apply', '--module', 'appearance', '--execute', env=env, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('restoring safety backup', result.stderr)
        self.assertEqual(dc('read', key), "'MyOriginalTheme'")
        self.assertEqual(dc('read', '/org/gnome/desktop/interface/icon-theme'), '')

    def test_13_restore_dry_run_is_readonly(self):
        source = backup('gtk4')
        self.css.write_text('later')
        old = list(STATE.glob('backups/*'))
        call('restore', '--module', 'gtk4', '--from', str(source), '--dry-run')
        self.assertEqual(self.css.read_text(), 'later')
        self.assertEqual(old, list(STATE.glob('backups/*')))

    def test_14_backup_recursion_refused(self):
        env = dict(os.environ, XDG_STATE_HOME=str(self.gtk / 'state'))
        p = call('backup', '--module', 'gtk4', '--execute', env=env, ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('inside source', p.stderr)

    def test_15_absent_session_bus_refused(self):
        env = dict(os.environ)
        env.pop('DBUS_SESSION_BUS_ADDRESS', None)
        before = self.css.read_text()
        p = call('backup', '--module', 'gtk4', '--execute', env=env, ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('No session bus', p.stderr)
        self.assertEqual(self.css.read_text(), before)

    def test_16_extension_source_hot_restore_refused(self):
        running = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'gnome-shell'], capture_output=True).returncode == 0
        if not running:
            self.skipTest('No live user gnome-shell process for hot-restore guard test')
        source = backup('extension-files')
        p = call('restore', '--module', 'extension-files', '--from', str(source), '--execute', ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Hot replacement', p.stderr)

    def test_17_user_menu_runtime_roundtrip(self):
        source = HOME / '.local/share/gnome50-macos-kit/orbit-daemon/test-version'
        source.mkdir(parents=True, exist_ok=True)
        payload = source / 'version.txt'; payload.write_text('locked source')
        entry = HOME / '.local/bin/global-menu'; entry.parent.mkdir(parents=True, exist_ok=True)
        entry.symlink_to(payload)
        saved = backup('menu-runtime')
        payload.write_text('changed source')
        call('restore', '--module', 'menu-runtime', '--from', str(saved), '--execute')
        self.assertEqual(payload.read_text(), 'locked source')
        self.assertTrue(entry.is_symlink())


    def test_18_version_and_install_dependency_check(self):
        p = call('--version')
        self.assertIn('gnome50-macos-kit', p.stdout)
        # The isolated HOME has no Dhruva/global-menu schemas, so install must
        # refuse before planning instead of half-applying the profile.
        p = call('install', '--dry-run', ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Missing schema', p.stderr)

    def test_19_verify_is_readonly_and_reports_failures(self):
        before = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        p = call('verify', ok=False)
        after = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        self.assertNotEqual(p.returncode, 0)
        report = json.loads(p.stdout)
        self.assertFalse(report['ok'])
        names = {c['name'] for c in report['checks']}
        self.assertIn('settings', names)
        self.assertEqual(before, after, 'verify must not create state files')

    def test_20_doctor_is_readonly_and_lists_missing(self):
        before = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        p = call('doctor', ok=False)
        after = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        self.assertNotEqual(p.returncode, 0)
        report = json.loads(p.stdout)
        self.assertFalse(report['ok'])
        self.assertTrue(any(n.startswith('theme:') for n in report['missing']))
        self.assertTrue(any(c.get('hint') for c in report['checks'] if not c['ok']))
        self.assertEqual(before, after, 'doctor must not create state files')

    def test_21_bootstrap_dry_run_is_readonly(self):
        before = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        p = call('bootstrap', '--dry-run', ok=False)
        after = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        # The isolated HOME has no WhiteSur/Inter/extensions, so preflight is not ready.
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('CHECK doctor:', p.stdout)
        self.assertIn('BOOTSTRAP DRY-RUN: not ready', p.stdout)
        self.assertEqual(before, after, 'bootstrap dry-run must not create state files')

    def test_22_bootstrap_execute_requires_snapshot_ack(self):
        before = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        p = call('bootstrap', '--execute', ok=False)
        after = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('snapshot', p.stderr.lower())
        self.assertEqual(before, after, 'refusal must happen before any write')

    def test_23_bootstrap_rejects_bad_profile(self):
        profile = HOME / 'bad-profile.json'
        profile.write_text(json.dumps({
            'format': 1,
            'name': 'bad',
            'target': {'os_id': 'ubuntu', 'os_version': '26.04',
                       'gnome_prefix': 'GNOME Shell 50.', 'session_types': ['wayland'],
                       'shell_theme': 'WhiteSur-MacOS-test'},
            'modules': ['not-a-module'],
            'extensions': {'x': 'y'},
        }))
        before = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        p = call('bootstrap', '--dry-run', '--profile', str(profile), ok=False)
        after = sorted(str(x) for x in STATE.rglob('*')) if STATE.exists() else None
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('modules', p.stderr)
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main(verbosity=2)
