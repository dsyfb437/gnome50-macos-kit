#!/usr/bin/env python3
"""Translate curated global-menu labels in place; --dry-run by default.

Only the JSON data shipped with the extension is touched. Reload the extension
(disable/enable global-menu@unmade.space) afterwards; no Shell restart needed.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path.home() / '.local/share/gnome-shell/extensions/global-menu@unmade.space'
APPS = ROOT / 'shortcuts/apps'
TABLE = Path(__file__).resolve().parent.parent / 'data/menu-zh.json'
ACCEL = ('Ctrl', 'Alt', 'Shift', 'Super', 'Page', 'Plus', 'Minus', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12')


def split_accel(label):
    if label.endswith(')') and ' (' in label:
        base, suffix = label.rsplit(' (', 1)
        if any(key in suffix for key in ACCEL):
            return base, ' (' + suffix
    return label, ''


def translate(label, table):
    base, suffix = split_accel(label)
    return table.get(base, base) + suffix


def walk(menu, table, changes):
    if 'label' in menu:
        new = translate(menu['label'], table)
        if new != menu['label']:
            changes.append((menu['label'], new))
            menu['label'] = new
    for item in menu.get('items', []):
        if item.get('label'):
            new = translate(item['label'], table)
            if new != item['label']:
                changes.append((item['label'], new))
                item['label'] = new


def main():
    p = argparse.ArgumentParser(description='默认干运行；把 curated 菜单标签改成中文。')
    p.add_argument('apps', nargs='*', default=['chrome'], help='不含 .json 的应用名，默认 chrome')
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    table = json.loads(TABLE.read_text())
    total = 0
    for name in a.apps:
        path = APPS / (name + '.json')
        if not path.is_file():
            print(f'skip {name}: {path} missing', file=sys.stderr)
            continue
        data = json.loads(path.read_text())
        changes = []
        for menu in data.get('menus', []):
            walk(menu, table, changes)
        print(f'{name}: {len(changes)} label(s) translated')
        for old, new in changes[:6]:
            print(f'  {old} -> {new}')
        total += len(changes)
        if a.execute and changes:
            backup = path.with_suffix('.json.bak-20261031')
            if not backup.exists():
                shutil.copy2(path, backup)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'total: {total}; execute={a.execute}')
    if not a.execute:
        print('DRY-RUN: add --execute to write (a .bak-20261031 backup is kept)')


if __name__ == '__main__':
    main()
