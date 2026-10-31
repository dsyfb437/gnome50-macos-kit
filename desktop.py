#!/usr/bin/env python3
"""Conservative user desktop configuration manager. Python standard library only."""
import argparse
import ast
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

KIT_VERSION = '1.3.0'
ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share'))
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'gnome50-macos-kit'
# module: schema, dconf path, key, fixed target (GVariant text)
I = 'org.gnome.desktop.interface'
IP = '/org/gnome/desktop/interface/'
SETTINGS = {
 'appearance': [(I, IP, 'gtk-theme', "'WhiteSur-Light'"),
                (I, IP, 'icon-theme', "'WhiteSur'"),
                (I, IP, 'cursor-theme', "'WhiteSur-cursors'"),
                (I, IP, 'cursor-size', '28'),
                (I, IP, 'color-scheme', "'prefer-light'")],
 'font': [(I, IP, 'font-name', "'Inter 11'")],
 'buttons': [('org.gnome.desktop.wm.preferences', '/org/gnome/desktop/wm/preferences/',
              'button-layout', "'close,minimize,maximize:'")],
 'shell-theme': [('org.gnome.shell.extensions.user-theme', '/org/gnome/shell/extensions/user-theme/',
                 'name', "'WhiteSur-MacOS-33ce5241ece02d81'")],
 'panel-blur': [('org.gnome.shell.extensions.blur-my-shell.panel', '/org/gnome/shell/extensions/blur-my-shell/panel/', 'blur', 'true'),
                ('org.gnome.shell.extensions.blur-my-shell.overview', '/org/gnome/shell/extensions/blur-my-shell/overview/', 'blur', 'false')],
}
# Visual modules do not change animation, scaling, favorites or shortcuts.
SETTINGS['macos-dock'] = [
 ('org.gnome.shell.extensions.dhruva', '/org/gnome/shell/extensions/dhruva/', key, value)
 for key, value in [('blur-enabled', 'false'),
                    ('background-color', "'#F1EDE7'"), ('background-opacity', '78'),
                    ('stroke-color', "'#FFFFFF'"), ('stroke-opacity', '30'),
                    ('grid-icon-color', "'#303034'"), ('indicator-color', "'#303034'"),
                    ('separator-color', "'#303034'"), ('running-separator-color', "'#303034'")]] + [
 # Real-time dock blur measured ~17% of one core here, and Blur My Shell would
 # override the Dhruva values, so both blur paths stay off.
 ('org.gnome.shell.extensions.blur-my-shell.dash-to-dock',
  '/org/gnome/shell/extensions/blur-my-shell/dash-to-dock/', 'blur', 'false')]
# Status area: monochrome tray icons and menu-bar type matched to the panel font.
SETTINGS['status-area'] = [
 ('org.gnome.shell.extensions.appindicator', '/org/gnome/shell/extensions/appindicator/',
  'icon-saturation', '1.0'),
 ('org.gnome.shell.extensions.global-menu', '/org/gnome/shell/extensions/global-menu/',
  'menu-font-size', '11'),
 ('org.gnome.shell.extensions.just-perfection',
  '/org/gnome/shell/extensions/just-perfection/', 'panel-indicator-padding-size', '6')]
FILES = {
 'gtk3': [CONFIG / 'gtk-3.0'], 'gtk4': [CONFIG / 'gtk-4.0'],
 'themes': [HOME / '.themes', DATA / 'themes'],
 'icons': [HOME / '.icons', DATA / 'icons'],
 'fonts': [HOME / '.fonts', DATA / 'fonts', CONFIG / 'fontconfig'],
 'extension-files': [DATA / 'gnome-shell/extensions'],
 'input-method': [CONFIG / 'fcitx5', DATA / 'fcitx5', DATA / 'fcitx5/rime'],
 'orbit-files': [CONFIG / 'global-menu'],
 'menu-runtime': [DATA / 'gnome50-macos-kit/orbit-daemon', DATA / 'gnome50-macos-kit/gtk3-appmenu',
                  HOME / '.local/bin/global-menu', HOME / '.local/bin/with-orbit-menu'],
}
# Avoid nested snapshots.
FILES['input-method'] = [CONFIG / 'fcitx5', DATA / 'fcitx5']
TREE = '/org/gnome/shell/extensions/'
MODULES = list(SETTINGS) + list(FILES) + ['extension-settings']
# Visual profile applied by `install`; backup/restore stay per-module.
INSTALL_MODULES = ['appearance', 'font', 'buttons', 'panel-blur', 'status-area',
                   'macos-dock', 'shell-theme']
USER_THEME = 'org.gnome.shell.extensions.user-theme'
REQUIRED_EXTENSIONS = {
 'user-theme@gnome-shell-extensions.gcampax.github.com': 'shell-theme',
 'blur-my-shell@aunetx': 'panel-blur, macos-dock',
 'dhruva@narkagni': 'macos-dock',
 'global-menu@unmade.space': 'status-area',
 'just-perfection-desktop@just-perfection': 'status-area',
 'ubuntu-appindicators@ubuntu.com': 'status-area',
 'spotlight@nin': 'search lifecycle patch',
}


def run(*args, optional=False):
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as e:
        if optional:
            return None
        raise RuntimeError(str(e)) from e
    if p.returncode:
        if optional:
            return None
        raise RuntimeError(f'{args[0]} failed: {p.stderr.strip()}')
    return p.stdout.strip()


def exists(p):
    return p.exists() or p.is_symlink()


def digest(p):
    """Canonical inventory, preserving links without reading their targets."""
    out = {}
    def visit(q, rel):
        if q.is_symlink():
            out[rel] = {'link': os.readlink(q)}
        elif q.is_dir():
            out[rel] = {'dir': True, 'mode': q.stat().st_mode & 0o777}
            for child in sorted(q.iterdir()):
                visit(child, rel + '/' + child.name)
        elif q.is_file():
            h = hashlib.sha256()
            with q.open('rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
            out[rel] = {'sha256': h.hexdigest(), 'mode': q.stat().st_mode & 0o777}
        else:
            raise RuntimeError(f'Unsupported special file: {q}')
    if exists(p):
        visit(p, '.')
    return out


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if src.is_symlink():
        dst.symlink_to(os.readlink(src))
    elif src.is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


def remove(p):
    if p.is_symlink() or p.is_file():
        p.unlink()
    elif p.is_dir():
        shutil.rmtree(p)


def safe_parent(p):
    if not p.is_absolute():
        raise RuntimeError(f'Absolute path required: {p}')
    for parent in p.parents:
        if parent.is_symlink():
            raise RuntimeError(f'Refusing symlink ancestor: {parent}')


def gs(schema):
    base = ['gsettings']
    if schema in (run('gsettings', 'list-schemas', optional=True) or '').splitlines():
        return base
    for root in [DATA / 'gnome-shell/extensions', Path('/usr/share/gnome-shell/extensions')]:
        if root.is_dir():
            for d in sorted(root.glob('*/schemas')):
                names = run('gsettings', '--schemadir', str(d), 'list-schemas', optional=True)
                if names and schema in names.splitlines():
                    return base + ['--schemadir', str(d)]
    raise RuntimeError(f'Missing schema: {schema}; install/compile compatible extension first')


def preflight(modules):
    for module in modules:
        for schema, path, key, target in SETTINGS.get(module, []):
            cmd = gs(schema)
            if key not in run(*cmd, 'list-keys', schema).splitlines():
                raise RuntimeError(f'Missing key: {schema} {key}')
            if run(*cmd, 'writable', schema, key) != 'true':
                raise RuntimeError(f'Key is locked: {schema} {key}')
            # Actual GVariant range/type validation occurs through gsettings set.
    if 'appearance' in modules or 'shell-theme' in modules:
        roots = [HOME / '.themes', DATA / 'themes', Path('/usr/share/themes')]
        for part in (['gtk-3.0/gtk.css'] if 'appearance' in modules else []) + (['gnome-shell/gnome-shell.css'] if 'shell-theme' in modules else []):
            if not any((r / 'WhiteSur-Light' / part).is_file() for r in roots):
                raise RuntimeError(f'Missing WhiteSur-Light/{part}; no installer is run automatically')
    if 'appearance' in modules:
        roots = [HOME / '.icons', DATA / 'icons', Path('/usr/share/icons')]
        for name in ['WhiteSur', 'WhiteSur-cursors']:
            if not any((r / name / 'index.theme').is_file() for r in roots):
                raise RuntimeError(f'Missing icon/cursor theme: {name}')
    if 'font' in modules:
        family = run('fc-match', '-f', '%{family}', 'Inter')
        if 'Inter' not in family.split(','):
            raise RuntimeError(f'Inter is not installed (fallback: {family})')


def get_modules(args, allowed):
    names = args.module or []
    if not names:
        raise RuntimeError('Choose --module explicitly; see --help')
    if 'all' in names:
        if allowed != MODULES:
            raise RuntimeError('apply has no all shortcut; choose each module')
        names = MODULES[:]
    if len(set(names)) != len(names) or any(n not in allowed for n in names):
        raise RuntimeError(f'Invalid/duplicate module; allowed: {", ".join(allowed)}')
    # extension-settings already contains shell-theme and panel-blur paths.
    if 'extension-settings' in names:
        names = [n for n in names if n not in SETTINGS or not all(path.startswith(TREE) for _, path, _, _ in SETTINGS[n])]
    return names


def snapshot(modules):
    for module in modules:
        for path in FILES.get(module, []):
            if STATE.resolve().is_relative_to(path.resolve()):
                raise RuntimeError(f'Backup destination is inside source: {path}')
    # All settings reads finish before creating a destination directory.
    values = {}
    for m in modules:
        if m in SETTINGS:
            values[m] = {path + key: run('dconf', 'read', path + key) or None
                         for _, path, key, _ in SETTINGS[m]}
    tree = run('dconf', 'dump', TREE) if 'extension-settings' in modules else None
    safe_parent(STATE / 'backups')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = STATE / 'backups' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    dest.mkdir(parents=True, mode=0o700)
    manifest = {'format': 1, 'home': str(HOME), 'modules': modules, 'values': values,
                'extension_settings': tree, 'files': {}, 'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'gnome': run('gnome-shell', '--version', optional=True)}
    try:
        for m in modules:
            for idx, path in enumerate(FILES.get(m, [])):
                safe_parent(path)
                label = m + '-' + str(idx)
                before = digest(path)
                if before:
                    copy(path, dest / 'files' / label)
                after = digest(dest / 'files' / label)
                if before != after or before != digest(path):
                    raise RuntimeError(f'Files changed during backup: {path}; close editing applications and retry')
                manifest['files'][label] = {'inventory': after}
        text = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
        (dest / 'manifest.json').write_text(text)
        (dest / 'manifest.sha256').write_text(hashlib.sha256(text.encode()).hexdigest() + '\n')
        print('BACKUP ' + str(dest))
        return dest, manifest
    except BaseException:
        remove(dest)
        raise


def load_backup(source, modules):
    safe_parent(source / 'manifest.json')
    if source.is_symlink() or (source / 'manifest.json').is_symlink():
        raise RuntimeError('Backup root/manifest cannot be symlinks')
    raw = (source / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != (source / 'manifest.sha256').read_text().strip():
        raise RuntimeError('Manifest checksum mismatch')
    b = json.loads(raw)
    if b['format'] != 1 or b['home'] != str(HOME):
        raise RuntimeError('Backup format/home mismatch; migration requires manual review')
    current = run('gnome-shell', '--version', optional=True)
    if (b.get('gnome') or '').split('.')[0] != (current or '').split('.')[0]:
        raise RuntimeError('GNOME major version differs; cross-version restore requires manual review')
    if not set(modules) <= set(b['modules']):
        raise RuntimeError('Requested module is absent from backup')
    for m in modules:
        if m in SETTINGS:
            allowed = {p + k for _, p, k, _ in SETTINGS[m]}
            if set(b['values'][m]) != allowed:
                raise RuntimeError('Unexpected settings paths in backup')
        for idx, path in enumerate(FILES.get(m, [])):
            label = m + '-' + str(idx)
            src = source / 'files' / label
            safe_parent(src)
            if digest(src) != b['files'][label]['inventory']:
                raise RuntimeError(f'Payload checksum mismatch: {label}')
    return b


def restore_data(source, b, modules):
    for m in modules:
        for idx, target in enumerate(FILES.get(m, [])):
            safe_parent(target)
            label = m + '-' + str(idx)
            payload = source / 'files' / label
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            stage = target.parent / ('.' + target.name + '.stage-' + uuid.uuid4().hex)
            old = target.parent / ('.' + target.name + '.old-' + uuid.uuid4().hex)
            try:
                if exists(payload):
                    copy(payload, stage)
                if exists(target):
                    target.rename(old)
                if exists(stage):
                    stage.rename(target)
                if digest(target) != b['files'][label]['inventory']:
                    raise RuntimeError(f'File read-back mismatch: {target}')
            except BaseException:
                if exists(old):
                    remove(target)
                    old.rename(target)
                raise
            finally:
                remove(stage)
            remove(old)
        for path, value in b['values'].get(m, {}).items():
            if value is None:
                run('dconf', 'reset', path)
            else:
                run('dconf', 'write', path, value)
            if (run('dconf', 'read', path) or None) != value:
                raise RuntimeError(f'Settings restore read-back mismatch: {path}')
        if m == 'extension-settings':
            run('dconf', 'reset', '-f', TREE)
            p = subprocess.run(['dconf', 'load', TREE], input=b['extension_settings'] or '', text=True, capture_output=True)
            if p.returncode:
                raise RuntimeError(p.stderr)
            if run('dconf', 'dump', TREE) != (b['extension_settings'] or '').strip():
                raise RuntimeError('Extension settings restore read-back mismatch')


def offline_guard(modules):
    if 'menu-runtime' in modules:
        owner = run('gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
                    '--object-path', '/org/freedesktop/DBus', '--method',
                    'org.freedesktop.DBus.NameHasOwner', 'space.unmade.GlobalMenu', optional=True)
        if owner == '(true,)':
            raise RuntimeError('Stop the Orbit daemon before restoring menu-runtime; disable Orbit temporarily')
    if 'extension-files' in modules and run('pgrep', '-u', str(os.getuid()), '-x', 'gnome-shell', optional=True):
        raise RuntimeError('Extension source restore requires logout of GNOME; use a text console. Hot replacement is refused.')


def collect_status():
    out = {'notice': 'Read-only inventory of this execution environment; visual compatibility is untested',
           'gnome': run('gnome-shell', '--version', optional=True),
           'os': Path('/etc/os-release').read_text(), 'session': os.environ.get('XDG_SESSION_TYPE'),
           'settings': {}, 'extensions': [], 'warnings': [], 'files': {}}
    for m, rows in SETTINGS.items():
        for schema, path, key, target in rows:
            try:
                out['settings'][schema + ':' + key] = {'current': run(*gs(schema), 'get', schema, key), 'target': target}
            except RuntimeError as e:
                out['settings'][schema + ':' + key] = {'unavailable': str(e)}
    enabled_raw = run('gsettings', 'get', 'org.gnome.shell', 'enabled-extensions', optional=True)
    try:
        enabled = ast.literal_eval((enabled_raw or '[]').removeprefix('@as '))
    except (ValueError, SyntaxError):
        enabled = []
    out['enabled_extensions_preference'] = enabled
    owner = run('gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
                '--object-path', '/org/freedesktop/DBus', '--method',
                'org.freedesktop.DBus.NameHasOwner', 'org.gnome.Shell', optional=True)
    out['runtime_extensions'] = (run('gnome-extensions', 'list', '--enabled', optional=True)
                                 if owner == '(true,)' else None)
    validation = run('gsettings', 'get', 'org.gnome.shell', 'disable-extension-version-validation', optional=True)
    out['version_validation_disabled'] = validation
    if validation == 'true':
        out['warnings'].append('Extension version validation is disabled; do not force old extensions to load')
    for root in [DATA / 'gnome-shell/extensions', Path('/usr/share/gnome-shell/extensions')]:
        if not root.is_dir():
            continue
        for meta in sorted(root.glob('*/metadata.json')):
            try:
                obj = json.loads(meta.read_text())
                row = {k: obj.get(k) for k in ['uuid', 'name', 'shell-version', 'version', 'version-name']}
                row.update({'path': str(meta.parent), 'declares_50': '50' in obj.get('shell-version', []), 'enabled_preference': obj.get('uuid') in enabled})
                row['genie_files'] = {str(p.relative_to(meta.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in meta.parent.rglob('GenieEffect.js') if p.is_file()}
                out['extensions'].append(row)
            except (OSError, ValueError) as e:
                out['warnings'].append(f'Cannot read {meta}: {e}')
    names = ' '.join(str(x) for x in enabled).lower()
    if 'dhruva' in names and any(n in names for n in ['dash-to-dock', 'ubuntu-dock', 'macos-dock']):
        out['warnings'].append('Multiple Dock extensions enabled: retain Dhruva only after manual review')
    if 'global-menu' in names and any(n in names for n in ['fildem', 'globalmenu@', 'tpct']):
        out['warnings'].append('Possible duplicate global menus')
    if 'global-menu' in names and any(n in names for n in ['window-title', 'windowtitle', 'window_title']):
        out['warnings'].append('Review duplicate active-window title next to Orbit')
    out['warnings'].append('Conflict heuristics use UUID substrings; review extension names/runtime state manually')
    for m, paths in FILES.items():
        out['files'][m] = [{'path': str(p), 'present': exists(p), 'symlink': os.readlink(p) if p.is_symlink() else None} for p in paths]
    for tool in ['gnome-sushi', 'fcitx5', 'rime_deployer', 'global-menu', 'ulauncher']:
        out.setdefault('tools', {})[tool] = shutil.which(tool)
    return out


def status():
    print(json.dumps(collect_status(), ensure_ascii=False, indent=2))


def doctor():
    """Offline prerequisite report for a fresh machine. Read-only."""
    checks = []

    def check(name, fn, hint=None):
        try:
            checks.append({'name': name, 'ok': True, 'detail': fn()})
        except (RuntimeError, OSError, ValueError, KeyError) as exc:
            row = {'name': name, 'ok': False, 'detail': str(exc)}
            if hint:
                row['hint'] = hint
            checks.append(row)

    def theme_file(name, part):
        for root in (HOME / '.themes', DATA / 'themes', Path('/usr/share/themes')):
            path = root / name / part
            if path.is_file():
                return str(path)
        raise RuntimeError(f'{name}/{part} missing')

    def icon_theme(name):
        for root in (HOME / '.icons', DATA / 'icons', Path('/usr/share/icons')):
            path = root / name / 'index.theme'
            if path.is_file():
                return str(path)
        raise RuntimeError(f'icon/cursor theme {name} missing')

    def font():
        family = run('fc-match', '-f', '%{family}', 'Inter')
        if 'Inter' not in family.split(','):
            raise RuntimeError(f'Inter missing (fallback: {family})')
        return family

    def extension(uuid):
        for root in (DATA / 'gnome-shell/extensions', Path('/usr/share/gnome-shell/extensions')):
            meta = root / uuid / 'metadata.json'
            if meta.is_file():
                data = json.loads(meta.read_text())
                return f"{data.get('name', uuid)} {data.get('version') or ''} at {meta.parent}".strip()
        raise RuntimeError(f'extension {uuid} is not installed')

    def schema(name):
        return ' '.join(gs(name))

    check('gnome-50', lambda: run('gnome-shell', '--version'), 'This kit targets GNOME Shell 50.x only')
    check('theme:gtk3', lambda: theme_file('WhiteSur-Light', 'gtk-3.0/gtk.css'),
          'Install WhiteSur GTK theme; the kit does not run installers')
    check('theme:gtk4', lambda: theme_file('WhiteSur-Light', 'gtk-4.0/gtk.css'),
          'Install WhiteSur GTK theme; the kit does not run installers')
    check('theme:shell', lambda: theme_file('WhiteSur-Light', 'gnome-shell/gnome-shell.css'),
          'Install WhiteSur GTK theme; the kit does not run installers')
    check('icons:WhiteSur', lambda: icon_theme('WhiteSur'), 'Install WhiteSur icon theme')
    check('cursors:WhiteSur-cursors', lambda: icon_theme('WhiteSur-cursors'), 'Install WhiteSur cursor theme')
    check('font:Inter', font, 'Install the Inter font family')
    for uuid in REQUIRED_EXTENSIONS:
        check('extension:' + uuid, lambda u=uuid: extension(u),
              'Install the extension from its upstream project; the kit never runs its installer')
    for name in sorted({schema for rows in SETTINGS.values() for schema, _, _, _ in rows}):
        check('schema:' + name, lambda n=name: schema(n),
              'The schema comes from the extension that owns it; install and enable it first')
    theme_name = ast.literal_eval(SETTINGS['shell-theme'][0][3])
    check('generated-theme:' + theme_name,
          lambda: theme_file(theme_name, 'gnome-shell/gnome-shell.css'),
          'Run style.py --execute to build the panel variant before install')
    for tool in ('gsettings', 'dconf'):
        check('tool:' + tool, lambda t=tool: shutil.which(t) or (_ for _ in ()).throw(RuntimeError(f'{t} not found')))
    report = {'version': KIT_VERSION, 'ok': all(c['ok'] for c in checks),
              'checks': checks,
              'missing': [c['name'] for c in checks if not c['ok']]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


def _enabled_extensions():
    raw = run('gsettings', 'get', 'org.gnome.shell', 'enabled-extensions', optional=True)
    try:
        return ast.literal_eval((raw or '[]').removeprefix('@as '))
    except (ValueError, SyntaxError):
        return []


def verify():
    """Read-only acceptance check. Returns 0 when every check passes."""
    checks = []

    def check(name, fn):
        try:
            checks.append({'name': name, 'ok': True, 'detail': fn()})
        except (RuntimeError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
            checks.append({'name': name, 'ok': False, 'detail': str(exc)})

    def session_bus():
        if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
            raise RuntimeError('no session bus')
        return 'session bus present'

    def gnome_version():
        version = run('gnome-shell', '--version', optional=True) or ''
        if not version.startswith('GNOME Shell 50.'):
            raise RuntimeError(f'expected GNOME Shell 50.x, got {version or "unknown"}')
        return version

    state = {}

    def settings_match():
        state['status'] = collect_status()
        unavailable = [k for k, v in state['status']['settings'].items() if 'unavailable' in v]
        if unavailable:
            raise RuntimeError(f'{len(unavailable)} setting(s) unavailable: ' + ', '.join(unavailable[:4]))
        bad = [k for k, v in state['status']['settings'].items() if str(v['current']) != str(v['target'])]
        if bad:
            raise RuntimeError(f'{len(bad)} setting(s) differ: ' + ', '.join(bad[:6]))
        return f'{len(state["status"]["settings"])} settings match the profile'

    def extensions():
        enabled = set(_enabled_extensions())
        missing = [uuid for uuid in REQUIRED_EXTENSIONS if uuid not in enabled]
        if missing:
            raise RuntimeError('missing or disabled: ' + ', '.join(missing))
        return f'{len(REQUIRED_EXTENSIONS)} required extensions enabled'

    def shell_theme():
        name = run(*gs(USER_THEME), 'get', USER_THEME, 'name').strip().strip("'")
        target = ast.literal_eval(SETTINGS['shell-theme'][0][3])
        if name != target:
            raise RuntimeError(f'selected {name!r}, profile expects {target!r}')
        for root in (HOME / '.themes', DATA / 'themes'):
            if (root / name / 'gnome-shell/gnome-shell.css').is_file():
                return f'{name} present in {root}'
        raise RuntimeError(f'generated theme files missing for {name}')

    def spotlight():
        proc = subprocess.run([sys.executable, str(ROOT / 'verify-after-login.py')],
                              text=True, capture_output=True, timeout=45)
        data = json.loads(proc.stdout)
        if not data.get('patched_files_match'):
            raise RuntimeError('Spotlight patch files changed')
        if not data.get('spotlight_active'):
            raise RuntimeError('Spotlight extension is not active')
        return 'active with patched files matching'

    def menu_dedupe():
        ext = DATA / 'gnome-shell/extensions/global-menu@unmade.space'
        native = (ext / 'nativeMenu.js').read_text()
        install = (ext / 'extension.js').read_text()
        if 'splitBarMenus' not in native or 'setItems(items, this._winTracker.focus_app' not in install:
            raise RuntimeError('app-menu dedupe patch is not installed')
        return 'dedupe patch present in the installed extension'

    def terminal_entry():
        entries = [HOME / '.local/share/applications/org.gnome.Ptyxis.desktop',
                   HOME / '.local/share/applications/com.microsoft.VSCode.desktop']
        leaks = [e.name for e in entries if e.is_file() and 'GTK_THEME' in e.read_text()]
        if leaks:
            raise RuntimeError('desktop entries still export GTK_THEME: ' + ', '.join(leaks))
        present = [e.name for e in entries if e.is_file()]
        return 'no GTK_THEME leak in ' + (', '.join(present) if present else 'checked entries')

    check('session-bus', session_bus)
    check('gnome-50', gnome_version)
    check('settings', settings_match)
    check('extensions', extensions)
    check('shell-theme', shell_theme)
    check('spotlight', spotlight)
    check('menu-dedupe', menu_dedupe)
    check('terminal-env', terminal_entry)

    report = {'version': KIT_VERSION,
              'ok': all(c['ok'] for c in checks),
              'checks': checks,
              'warnings': state.get('status', {}).get('warnings', [])}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


@contextlib.contextmanager
def lock():
    safe_parent(STATE / 'lock')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(STATE / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description='默认只读。apply/restore 默认 dry-run；实际写入必须 --execute。')
    p.add_argument('command', nargs='?', choices=['status', 'doctor', 'install', 'verify', 'apply', 'backup', 'restore'], default='status')
    p.add_argument('--version', action='version', version=f'gnome50-macos-kit {KIT_VERSION}')
    p.add_argument('--module', action='append', help=', '.join(MODULES) + '; repeat option; backup supports all')
    p.add_argument('--from', dest='source', type=Path, help='Backup directory to restore')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true', help='Explicitly write selected modules after automatic backup')
    mode.add_argument('--dry-run', action='store_true', help='No files/settings changes, including no backup creation')
    args = p.parse_args()
    if args.command == 'status':
        status()
        return
    if args.command == 'doctor':
        sys.exit(doctor())
    if args.command == 'verify':
        sys.exit(verify())
    if args.command == 'install':
        modules = INSTALL_MODULES
    else:
        modules = get_modules(args, list(SETTINGS) if args.command == 'apply' else MODULES)
    if args.command == 'restore' and args.source is None:
        raise RuntimeError('restore needs --from')
    source = args.source.absolute() if args.source else None
    b = load_backup(source, modules) if args.command == 'restore' else None
    for m in modules:
        if args.command in ('apply', 'install'):
            rows = SETTINGS[m]
            changed = 0
            for schema, path, key, value in rows:
                current = run(*gs(schema), 'get', schema, key) if args.command == 'install' else (run('dconf', 'read', path + key) or '<unset>')
                if args.command == 'install' and current == value:
                    continue
                changed += 1
                print(f'PLAN {m}: {schema} {key} => {value} (explicit current: {current})')
            if args.command == 'install' and not changed:
                print(f'PLAN {m}: already matches the profile')
        else:
            print(f'PLAN {args.command}: {m}')
    if not args.execute:
        print('DRY-RUN: no writes. Add --execute only after reviewing the plan.')
        return
    if os.geteuid() == 0:
        raise RuntimeError('Do not run as root or with sudo')
    if os.environ.get('GSETTINGS_BACKEND') not in [None, 'dconf']:
        raise RuntimeError('Only the dconf GSettings backend is supported')
    if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise RuntimeError('No session bus; no writes attempted')
    with lock():
        if args.command == 'backup':
            snapshot(modules)
            return
        if args.command in ('apply', 'install'):
            version = run('gnome-shell', '--version')
            if not version.startswith('GNOME Shell 50.'):
                raise RuntimeError('Application is restricted to Shell 50.x; no force flag')
            try:
                preflight(modules)
            except RuntimeError as exc:
                if args.command == 'install':
                    raise RuntimeError(f'{exc}; run "python3 desktop.py doctor" for the prerequisite list') from exc
                raise
            if args.command == 'install':
                theme = ast.literal_eval(SETTINGS['shell-theme'][0][3])
                if not any((r / theme / 'gnome-shell/gnome-shell.css').is_file()
                           for r in (HOME / '.themes', DATA / 'themes')):
                    raise RuntimeError(f'Missing generated theme {theme}; run style.py --execute first')
        else:
            offline_guard(modules)
        safety, prior = snapshot(modules)
        try:
            if args.command in ('apply', 'install'):
                for m in modules:
                    for schema, path, key, value in SETTINGS[m]:
                        run(*gs(schema), 'set', schema, key, value)
                        actual = run(*gs(schema), 'get', schema, key)
                        if actual != value:
                            raise RuntimeError(f'Read-back mismatch: {schema} {key}: {actual}')
            else:
                restore_data(source, b, modules)
        except BaseException:
            print('Operation failed; restoring safety backup', file=sys.stderr)
            try:
                restore_data(safety, prior, modules)
            except BaseException as err:
                print(f'ROLLBACK FAILED: {err}; preserve {safety}', file=sys.stderr)
            raise
        print('DONE. Recovery backup: ' + str(safety))

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(1)
