#!/usr/bin/env bash
# Optional integration tests against installed extension sources.
# Both directories are upstream code and are intentionally not vendored here.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
GM="${1:-$HOME/.local/share/gnome-shell/extensions/global-menu@unmade.space}"
SP="${2:-$HOME/.local/share/gnome-shell/extensions/spotlight@nin}"

if ! command -v node >/dev/null 2>&1; then
	echo "node is required for extension tests" >&2
	exit 1
fi

if [ -d "$GM" ]; then
	node "$ROOT/tests/test_menu_dedupe.cjs" "$GM"
	node "$ROOT/tests/test_native_menu_dedupe.cjs" "$GM"
else
	echo "SKIP global-menu tests: $GM not installed"
fi

if [ -d "$SP" ]; then
	node "$ROOT/tests/test_spotlight_lifecycle.cjs" "$SP"
else
	echo "SKIP Spotlight tests: $SP not installed"
fi
