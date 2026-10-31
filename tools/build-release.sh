#!/bin/sh
# Build a clean source archive from the committed tree (no .git, caches or private files).
set -eu
cd "$(dirname "$0")/.."
version=$(python3 -c 'import desktop; print(desktop.KIT_VERSION)')
name="gnome50-macos-kit-$version"
mkdir -p dist
rm -rf "dist/$name" "dist/$name.tar.gz" "dist/$name.tar.gz.sha256"
mkdir -p "dist/$name"
git archive --format=tar HEAD | tar -x -C "dist/$name"
tar -C dist -czf "dist/$name.tar.gz" "$name"
rm -rf "dist/$name"
(cd dist && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")
printf '%s\n' "dist/$name.tar.gz" "dist/$name.tar.gz.sha256"
