#!/usr/bin/env python3
"""Read-only by default; optional explicit overview exercise after new login."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description='默认只检查 Spotlight 补丁与新会话；--exercise 明确执行 5 轮概览开关')
p.add_argument('--exercise', action='store_true')
a = p.parse_args()
manifest = json.loads((root / 'data/spotlight-patch-manifest.json').read_text())
patch_time = dt.datetime.fromisoformat(manifest['applied_at']).timestamp()
ids = subprocess.check_output(['pgrep', '-u', str(os.getuid()), '-x', 'gnome-shell'], text=True).split()
boot = int(next(x.split()[1] for x in Path('/proc/stat').read_text().splitlines() if x.startswith('btime ')))
start = min(boot + int(Path('/proc', pid, 'stat').read_text().rsplit(')', 1)[1].split()[19]) / os.sysconf('SC_CLK_TCK') for pid in ids)
source = Path.home() / '.local/share/gnome-shell/extensions/spotlight@nin'
hashes_match = all(hashlib.sha256((source / rel).read_bytes()).hexdigest() == row['patched_sha256'] for rel, row in manifest['files'].items())
info = subprocess.check_output(['gdbus', 'call', '--session', '--dest', 'org.gnome.Shell', '--object-path', '/org/gnome/Shell', '--method', 'org.gnome.Shell.Extensions.GetExtensionInfo', 'spotlight@nin'], text=True)
# ExtensionState.ENABLED is 1; GDBus exposes it as a double in this interface.
active = "'state': <1.0>" in info or "'state': <1>" in info
result = {'checked_at': dt.datetime.now().astimezone().isoformat(), 'shell_pids': ids, 'patched_files_match': hashes_match, 'new_shell_since_patch': start > patch_time, 'spotlight_active': active,
          'status': '新会话可验证' if start > patch_time and hashes_match and active else '等待新登录或检查补丁/扩展状态'}
if a.exercise:
    if not (hashes_match and start > patch_time and active):
        result['exercise'] = '未执行：当前尚未满足新会话条件'
    else:
        import gi
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        def prop(method, parameters):
            return bus.call_sync('org.gnome.Shell', '/org/gnome/Shell', 'org.freedesktop.DBus.Properties', method,
                                 parameters, None, Gio.DBusCallFlags.NONE, 4000, None)
        original = prop('Get', GLib.Variant('(ss)', ('org.gnome.Shell', 'OverviewActive'))).unpack()[0]
        began = dt.datetime.now().astimezone().isoformat()
        matched = 0
        try:
            for _ in range(5):
                for value in [True, False]:
                    prop('Set', GLib.Variant('(ssv)', ('org.gnome.Shell', 'OverviewActive', GLib.Variant('b', value))))
                    time.sleep(0.8)
                    actual = prop('Get', GLib.Variant('(ss)', ('org.gnome.Shell', 'OverviewActive'))).unpack()[0]
                    matched += actual == value
        finally:
            prop('Set', GLib.Variant('(ssv)', ('org.gnome.Shell', 'OverviewActive', GLib.Variant('b', original))))
        log = subprocess.check_output(['journalctl', '--user', '-b', '--since', began, '--no-pager', '-o', 'cat', *['_PID=' + pid for pid in ids]], text=True)
        result['exercise'] = {'began_at': began, 'ended_at': dt.datetime.now().astimezone().isoformat(), 'requested_states_matched': matched, 'search_controller_warnings': sum('searchController' in line for line in log.splitlines()),
                              'boundary': 'Checks states and log warnings, not animation FPS or Spotlight query/selection behavior'}
print(json.dumps(result, ensure_ascii=False, indent=2))
