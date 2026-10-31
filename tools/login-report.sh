#!/bin/sh
# Read-only summary of GDM, fingerprint and keyring state. No root required.
set -u
echo "== GDM config (readable part) =="
if [ -r /etc/gdm3/custom.conf ]; then
    grep -E '^\s*(AutomaticLogin|WaylandEnable)' /etc/gdm3/custom.conf || echo 'no automatic-login/wayland lines'
    stat -c 'modified: %y' /etc/gdm3/custom.conf
else
    echo 'cannot read /etc/gdm3/custom.conf'
fi

echo
echo "== fingerprint enrollment =="
fprintd-list "$USER" 2>&1 | tail -4

echo
echo "== keyring files =="
ls -l "$HOME/.local/share/keyrings" 2>/dev/null || echo 'no keyring directory'

echo
echo "== PAM auth lines (gdm-fingerprint) =="
grep -E '^(auth|password)|pam_fprintd|pam_gnome_keyring' /etc/pam.d/gdm-fingerprint 2>/dev/null || echo 'cannot read gdm-fingerprint'

echo
echo "== recent GDM auth log =="
journalctl -b -u gdm --no-pager -o short-iso 2>/dev/null \
    | grep -av dsh-subprocess \
    | grep -E 'gdm-(fingerprint|password)|gkr-pam|session opened' | tail -10

echo
echo "== recent keyring prompts =="
journalctl -b --no-pager -o short-iso 2>/dev/null \
    | grep -av dsh-subprocess \
    | grep -E 'gcr-prompter.*password prompt' | tail -5 || echo 'none'
