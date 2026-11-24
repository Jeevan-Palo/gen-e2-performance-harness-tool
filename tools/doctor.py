#!/usr/bin/env python3
"""Check that this machine can run the harness. Usage: python tools/doctor.py   (from anywhere; exit 1 on a FAIL)
FAIL = nothing will work until fixed (Python version, PyYAML, repo files). WARN = one stage will not work (k6, pandoc, docker).
Uses only the standard library so it still runs when PyYAML is missing.
"""
import sys, os, shutil, subprocess, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(".venv", "Scripts" if os.name == "nt" else "bin", "python")
SETUP = "setup.ps1" if os.name == "nt" else "./setup.sh"

def version_of(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return ((r.stdout or r.stderr).strip().splitlines() or [""])[0]
    except Exception:
        return ""

def checks():
    out = []
    add = lambda level, name, detail, fix="": out.append((level, name, detail, fix))
    v = sys.version_info
    if v < (3, 9): add("FAIL", "Python 3.9+", f"found {v.major}.{v.minor}", "Install Python 3.9 or newer, then run " + SETUP)
    else: add("OK", "Python 3.9+", f"{v.major}.{v.minor}.{v.micro} ({sys.executable})")
    try:
        import yaml
        add("OK", "PyYAML", yaml.__version__)
    except ImportError:
        add("FAIL", "PyYAML", "not installed for this Python", f"Run {SETUP} (creates .venv and installs requirements.txt), then use {VENV_PY}")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv: add("WARN", "virtual environment", "not running inside a venv", f"Use {VENV_PY} or activate .venv (VS Code does this for new terminals)")
    for rel in (".github/copilot-instructions.md", "templates/brd.template.yaml", "tools/status.py"):
        if not os.path.exists(os.path.join(ROOT, rel)): add("FAIL", "repo files", f"{rel} is missing", "Clone the whole repository; do not copy single folders")
    n = len(glob.glob(os.path.join(ROOT, ".github", "skills", "*", "SKILL.md")))
    add("OK" if n else "FAIL", "skills", f"{n} found in .github/skills", "" if n else "The .github folder is incomplete; clone the whole repository")
    k6 = shutil.which("k6") or os.environ.get("K6_BIN")
    add("OK" if k6 else "WARN", "k6", version_of([k6, "version"]) if k6 else "not found", "" if k6 else "Needed for stages 5-7 (check and runs). Install: https://grafana.com/docs/k6/latest/set-up/install-k6/ (macOS: brew install k6)")
    pd = shutil.which("pandoc")
    add("OK" if pd else "WARN", "pandoc", version_of([pd, "--version"]) if pd else "not found", "" if pd else "Needed for the client Word file (stage 1). Install: https://pandoc.org/installing.html (macOS: brew install pandoc)")
    dk = shutil.which("docker")
    if not dk: add("WARN", "docker", "not found", "Only needed when monitoring source is docker_stats (stage 7). Install Docker Desktop or Rancher Desktop")
    else:
        up = subprocess.run([dk, "info"], capture_output=True, text=True, timeout=20).returncode == 0
        add("OK" if up else "WARN", "docker", "running" if up else "installed but not running", "" if up else "Start Docker before runs that use docker_stats")
    return out

def main():
    res = checks()
    for level, name, detail, fix in res:
        print(f"{level:4} {name}: {detail}")
        if fix: print(f"     -> {fix}")
    fails = sum(1 for r in res if r[0] == "FAIL"); warns = sum(1 for r in res if r[0] == "WARN")
    print(f"DOCTOR: {'FAILED' if fails else 'OK'} ({fails} fail, {warns} warn)")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
