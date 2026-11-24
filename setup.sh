#!/usr/bin/env bash
# One-time setup for macOS/Linux: creates .venv, installs requirements.txt, runs the doctor.
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "python3 not found. Install Python 3.9+ first."; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
.venv/bin/python tools/doctor.py
echo
echo "Done. In VS Code choose the interpreter .venv/bin/python, open Copilot Chat in Agent mode and type /run-end-to-end."
