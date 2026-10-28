#!/usr/bin/env python3
"""Fetch only locked source for review; never run source code or install it."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile


def main():
    p = argparse.ArgumentParser(description='仅准备固定提交的源码；默认 dry-run，不运行上游脚本')
    p.add_argument('--repo', required=True, help='Exact owner/repository from upstreams.lock.json')
    p.add_argument('--dest', required=True, type=Path, help='New review directory; must not exist')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    rows = json.loads((Path(__file__).parent / 'upstreams.lock.json').read_text())
    row = next((r for r in rows if r['repository'] == args.repo), None)
    if row is None:
        raise ValueError('Repository is not in lockfile')
    print(f"FETCH {row['url']} @ {row['commit']} => {args.dest}")
    if not args.execute:
        print('DRY-RUN: no downloads or directory creation')
        return
    dest = args.dest.absolute()
    if dest.exists() or dest.is_symlink():
        raise ValueError('Destination already exists')
    if not dest.parent.is_dir() or any(x.is_symlink() for x in dest.parents):
        raise ValueError('Destination needs an existing parent without symlinks')
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='.source-review-', dir=dest.parent) as tmp:
        root = Path(tmp) / 'repo'
        # No checkout from a mutable branch. Empty template avoids local Git hooks.
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'init', '--template=', str(root)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', 'fetch', '--depth=1', row['url'] + '.git', row['commit']], check=True, timeout=180)
        actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'FETCH_HEAD'], text=True).strip()
        if actual != row['commit']:
            raise ValueError('Commit mismatch')
        subprocess.run(['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', 'checkout', '--detach', actual], check=True, capture_output=True)
        for rel, wanted in row['files'].items():
            key = PurePosixPath(rel)
            if key.is_absolute() or '..' in key.parts:
                raise ValueError('Unsafe lockfile path')
            file = root / rel
            if not file.resolve().is_relative_to(root.resolve()):
                raise ValueError('Unexpected source symlink')
            if hashlib.sha256(file.read_bytes()).hexdigest() != wanted:
                raise ValueError('Source file mismatch: ' + rel)
        shutil.move(str(root), dest)
    print('VERIFIED source only. No installation performed.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        sys.exit(1)
