#!/bin/bash
# Issuer Intelligence Hub: double-click to start (macOS). Opens http://127.0.0.1:8600 in the browser.
# Needs: Python 3, the data/ folder (from the team's OneDrive) and, for the AI, the .env file (sent privately).
cd "$(dirname "$0")" || exit 1
if [ ! -f data/daily_features.parquet ]; then
  echo "The data/ folder is missing. Copy it from the team's OneDrive into: $(pwd)/data"; read -r -p "Press Enter to close."; exit 1
fi
[ -f .env ] || echo "No .env file: the app runs, but the AI uses fixed-rule answers (template mode)."
if [ ! -x .venv/bin/python ]; then
  echo "First start: installing the Python packages (needs internet, about 1-2 minutes) ..."
  python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements.txt || { read -r -p "Installation failed. Press Enter to close."; exit 1; }
fi
(sleep 6; open "http://127.0.0.1:8600") &
echo "Starting ... the browser opens by itself. Keep this window open during the demo; close it to stop."
.venv/bin/python web/server.py "$@"
