---
mode: agent
description: Check that this machine is ready to run the harness (Python, PyYAML, k6, pandoc, docker)
---
Run `python tools/doctor.py` (use `.venv/bin/python` if plain `python` is not available or cannot import `yaml`) and show me the result.

1. For every FAIL or WARN, tell me in one line what is wrong, which stage needs it, and the exact command to fix it.
2. If PyYAML is missing, tell me to run `./setup.sh` (macOS/Linux) or `setup.ps1` (Windows). Do not install packages yourself.
3. Do not touch any project file and do not send any request.
