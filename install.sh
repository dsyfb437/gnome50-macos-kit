#!/usr/bin/env bash
# One entry point for the scoped bootstrap. Default is dry-run.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi
exec python3 desktop.py bootstrap "$@"
