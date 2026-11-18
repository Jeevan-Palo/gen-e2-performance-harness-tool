#!/usr/bin/env python3
"""Environment definitions for a project (projects/<client>/<app>/environments.yaml).
Usage:
  python tools/envconf.py check <project_dir>          validate every environment
  python tools/envconf.py show  <project_dir> [name]   show one environment (default: the active one)
  python tools/envconf.py use   <project_dir> <name>   switch the active environment
Requires PyYAML. Never put passwords, tokens or keys in this file: list only the NAMES of environment variables.
"""
import sys, os, re, yaml

FILE = "environments.yaml"
TYPES = {"local", "test", "staging", "production", "public"}
AUTH = {"not_required", "confirmed_by_owner", "accepted_by_test_lead", "not_confirmed"}
MON = {"docker_stats", "azure", "dynatrace", "client_apm", "none"}

def blank(v): return v is None or v == "" or v == [] or v == {}
def path(d): return os.path.join(d, FILE)

def load(d):
    p = path(d)
    return yaml.safe_load(open(p, encoding="utf-8")) or {} if os.path.exists(p) else None

def get_env(d, name=None):
    """Return (name, env dict) for the named or active environment, or (None, None)."""
    cfg = load(d)
    if cfg is None: return None, None
    name = name or cfg.get("active")
    return name, (cfg.get("environments") or {}).get(name)

def problems(cfg):
    P, W = [], []
    envs = cfg.get("environments") or {}
    if not envs: P.append("No environments defined")
    if blank(cfg.get("active")): P.append("'active' is empty")
    elif cfg["active"] not in envs: P.append(f"active environment '{cfg['active']}' is not defined")
    for n, e in envs.items():
        e = e or {}
        bu = str(e.get("base_url", ""))
        if not re.match(r"^https?://[^/\s@]+(:\d+)?(/\S*)?$", bu): P.append(f"{n}: base_url must look like http(s)://host[:port] with no user:password")
        if e.get("type") not in TYPES: P.append(f"{n}: type must be one of {sorted(TYPES)}")
        if e.get("authorisation") not in AUTH: P.append(f"{n}: authorisation must be one of {sorted(AUTH)}")
        if blank(e.get("owner")): P.append(f"{n}: owner is empty")
        for k in ("max_vus", "max_run_minutes"):
            if not isinstance(e.get(k), int) or e.get(k) <= 0: P.append(f"{n}: {k} must be a positive whole number")
        if (e.get("monitoring") or {}).get("source") not in MON: P.append(f"{n}: monitoring.source must be one of {sorted(MON)}")
        if e.get("authorisation") == "accepted_by_test_lead" and blank(e.get("authorisation_note")):
            P.append(f"{n}: accepted_by_test_lead needs an authorisation_note (the test lead's own statement and date)")
        if e.get("authorisation") == "not_required" and e.get("type") in ("public", "production"):
            P.append(f"{n}: a {e.get('type')} system cannot be 'not_required'; it needs owner confirmation or an explicit test-lead acceptance")
        for v in e.get("credentials_env_vars") or []:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(v)): P.append(f"{n}: credentials_env_vars must hold variable NAMES (like APP_USER), not values")
        if re.search(r"(?i)(password|secret|token|api[_-]?key)\s*:", yaml.safe_dump(e).replace("credentials_env_vars", "")): P.append(f"{n}: looks like a credential key; store only env var names")
        if e.get("authorisation") == "not_confirmed": W.append(f"{n}: authorisation is not_confirmed, so runs are blocked on it")
    return P, W

def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("check", "show", "use"): sys.exit(__doc__)
    d = a[1]; cfg = load(d)
    if cfg is None: sys.exit(f"No {FILE} in {d}")
    if a[0] == "check":
        P, W = problems(cfg)
        if P: print(f"ISSUES to fix ({len(P)}):"); [print(f"  {i}. {x}") for i, x in enumerate(P, 1)]
        if W: print(f"Warnings ({len(W)}):"); [print(f"  - {x}") for x in W]
        if not P: print(f"OK: environments valid. Active: {cfg.get('active')}")
        sys.exit(1 if P else 0)
    if a[0] == "show":
        n, e = get_env(d, a[2] if len(a) > 2 else None)
        if e is None: sys.exit("Unknown environment")
        print(f"Environment '{n}'" + (" (active)" if n == cfg.get("active") else "")); print(yaml.safe_dump(e, sort_keys=False, allow_unicode=True))
        return
    if len(a) != 3 or a[2] not in (cfg.get("environments") or {}): sys.exit(f"Usage: use <project_dir> <name>; known: {sorted((cfg.get('environments') or {}))}")
    p = path(d); s = open(p, encoding="utf-8").read()
    s2, n = re.subn(r"(?m)^active:.*$", f"active: {a[2]}", s, count=1)
    if n != 1: sys.exit("Could not find the 'active:' line")
    open(p, "w", encoding="utf-8").write(s2)
    e = cfg["environments"][a[2]]
    print(f"Active environment is now '{a[2]}' ({e.get('base_url')}), authorisation: {e.get('authorisation')}")
    if e.get("authorisation") == "not_confirmed": print("NOTE: authorisation is not_confirmed, so runs on it will be refused until the test lead changes that field.")

if __name__ == "__main__": main()
