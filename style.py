#!/usr/bin/env python3
"""Build a versioned Shell-theme copy; dry-run unless --execute is supplied."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import desktop as d

SCHEMA = 'org.gnome.shell.extensions.user-theme'


def plan(source, overlay):
    source = source.absolute()
    d.safe_parent(source / 'gnome-shell.css')
    if source.is_symlink() or not (source / 'gnome-shell.css').is_file():
        raise RuntimeError('Source must be a local Shell theme directory containing gnome-shell.css')
    inventory = d.digest(source)
    # Copying relative external links to a different theme would break them.
    for rel, row in inventory.items():
        if 'link' in row:
            resolved = (source / rel).resolve()
            if Path(row['link']).is_absolute() or not resolved.is_relative_to(source.resolve()) or not resolved.exists():
                raise RuntimeError(f'External or dangling theme link requires manual review: {rel}')
    css = overlay.read_bytes()
    version = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode() + css).hexdigest()[:16]
    name = 'WhiteSur-MacOS-' + version
    target = d.HOME / '.themes' / name
    d.safe_parent(target / 'gnome-shell')
    return source, inventory, css, name, target


def build(source, inventory, css, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.macos-theme-', dir=target.parent))
    try:
        shutil.copytree(source, stage / 'gnome-shell', symlinks=True)
        if d.digest(source) != inventory or d.digest(stage / 'gnome-shell') != inventory:
            raise RuntimeError('Source changed while preparing theme; retry after editing finishes')
        output = stage / 'gnome-shell/gnome-shell.css'
        output.write_bytes(output.read_bytes() + b'\n' + css)
        # An existing version may be reused only if every byte/link/mode matches.
        if d.exists(target):
            if target.is_symlink() or d.digest(target) != d.digest(stage):
                raise RuntimeError('Existing generated theme has local edits; refusing overwrite')
        else:
            stage.rename(target)
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description='默认干运行；生成独立顶栏主题，不覆盖原主题。')
    p.add_argument('--source', type=Path, default=d.HOME / '.themes/WhiteSur-Light/gnome-shell')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    source, inventory, css, name, target = plan(a.source, d.ROOT / 'styles/panel-light.css')
    print(json.dumps({'source': str(source), 'theme': name, 'target': str(target),
                      'execute': a.execute}, ensure_ascii=False, indent=2))
    if not a.execute:
        return
    if os.geteuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise RuntimeError('Run as the desktop user with a session bus')
    if os.environ.get('GSETTINGS_BACKEND') not in (None, 'dconf'):
        raise RuntimeError('Only dconf backend is supported')
    if not d.run('gnome-shell', '--version').startswith('GNOME Shell 50.'):
        raise RuntimeError('This profile requires GNOME Shell 50.x')
    os.umask(0o077)
    with d.lock():
        gs = d.gs(SCHEMA)
        if d.run(*gs, 'writable', SCHEMA, 'name') != 'true':
            raise RuntimeError('Shell theme setting is not writable')
        safety, prior = d.snapshot(['shell-theme'])
        try:
            build(source, inventory, css, target)
            d.run(*gs, 'set', SCHEMA, 'name', repr(name))
            if d.run(*gs, 'get', SCHEMA, 'name') != repr(name):
                raise RuntimeError('Shell theme setting read-back failed')
        except BaseException:
            d.restore_data(safety, prior, ['shell-theme'])
            raise
        print('Theme selected; visually verify before accepting. Recovery backup: ' + str(safety))

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(1)
