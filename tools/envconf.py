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

def secs(s):
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(s or ""))
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)] if m else None

def plan(e):
    """The environment's approved run plan, or None when no plan or no approval note exists."""
    rp = (e or {}).get("run_plan") or {}
    if not isinstance(rp, dict) or blank(str(rp.get("approved_note") or "").strip()): return None
    return {"approved_note": rp["approved_note"], "discovery_actions": list(rp.get("discovery_actions") or []),
            "load_steps": list(rp.get("load_steps") or []), "ramp_up": str(rp.get("ramp_up") or "30s"), "steady": str(rp.get("steady") or "3m"),
            "ramp_down": str(rp.get("ramp_down") or "30s"), "pack_if_targets_missed": rp.get("pack_if_targets_missed") is True}

def plan_problems(n, e):
    P = []; rp = plan(e)
    if rp is None: return P
    steps = rp["load_steps"]
    if not all(isinstance(s, int) and s > 0 for s in steps): return [f"{n}: run_plan.load_steps must be positive whole numbers"]
    for i, s in enumerate(steps):
        if isinstance(e.get("max_vus"), int) and s > e["max_vus"]: P.append(f"{n}: run_plan.load_steps {s} exceeds max_vus={e['max_vus']}")
        if i == 0 and s > 5: P.append(f"{n}: run_plan.load_steps must start at 5 users or fewer")
        if i > 0 and not steps[i - 1] < s <= steps[i - 1] * 2: P.append(f"{n}: run_plan.load_steps must increase by at most 2x each step ({steps[i - 1]} -> {s})")
    d = [secs(rp[k]) for k in ("ramp_up", "steady", "ramp_down")]
    if None in d: P.append(f"{n}: run_plan durations must look like 30s, 3m or 1h")
    elif isinstance(e.get("max_run_minutes"), int) and sum(d) > e["max_run_minutes"] * 60: P.append(f"{n}: run_plan durations ({sum(d)}s) exceed max_run_minutes={e['max_run_minutes']}")
    return P

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
        mon = e.get("monitoring") or {}
        if mon.get("source") not in MON: P.append(f"{n}: monitoring.source must be one of {sorted(MON)}")
        if mon.get("source") == "docker_stats":
            cs = mon.get("containers")
            if not isinstance(cs, list) or not cs or not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", str(c)) for c in cs): P.append(f"{n}: monitoring.containers must be a list of container names for docker_stats")
            iv = mon.get("interval_seconds", 5)
            if not isinstance(iv, int) or not 2 <= iv <= 60: P.append(f"{n}: monitoring.interval_seconds must be a whole number from 2 to 60")
        if e.get("authorisation") == "accepted_by_test_lead" and blank(e.get("authorisation_note")):
            P.append(f"{n}: accepted_by_test_lead needs an authorisation_note (the test lead's own statement and date)")
        if e.get("authorisation") == "not_required" and e.get("type") in ("public", "production"):
            P.append(f"{n}: a {e.get('type')} system cannot be 'not_required'; it needs owner confirmation or an explicit test-lead acceptance")
        for v in e.get("credentials_env_vars") or []:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(v)): P.append(f"{n}: credentials_env_vars must hold variable NAMES (like APP_USER), not values")
        if re.search(r"(?i)(password|secret|token|api[_-]?key)\s*:", yaml.safe_dump(e).replace("credentials_env_vars", "")): P.append(f"{n}: looks like a credential key; store only env var names")
        P += plan_problems(n, e)
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
