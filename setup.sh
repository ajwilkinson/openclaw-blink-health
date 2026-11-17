#!/bin/sh
# One-off setup: creates a private Python environment next to this script and installs blinkpy
# into it, so nothing is added to the system Python. Safe to run again (it just updates).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "python3 with the venv module is needed (on Debian/Ubuntu: sudo apt install python3-venv)." >&2
    exit 1
fi
[ -x "$here/.venv/bin/python" ] || python3 -m venv "$here/.venv"
"$here/.venv/bin/python" -m pip install --quiet --upgrade pip
"$here/.venv/bin/python" -m pip install --quiet -r "$here/requirements.txt"
echo "Ready. Next, log in to Blink: $here/.venv/bin/python $here/blink_health.py login"
