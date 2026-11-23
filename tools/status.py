#!/usr/bin/env python3
"""Where does a project stand? Works it out from the files and the other tools' checks, and says what to do next.
Usage: python tools/status.py <project_dir> [--json]
Exit code 0 only when every stage is done. Requires PyYAML.
"""
import sys, os, re, json, subprocess, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf, brd as brdtool
T = os.path.dirname(os.path.abspath(__file__))

def run(tool, *args):
    r = subprocess.run([sys.executable, os.path.join(T, tool), *args], capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()

def mtime(p): return os.path.getmtime(p) if os.path.exists(p) else 0

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    d = sys.argv[1].rstrip("/"); as_json = "--json" in sys.argv; P = d
    st = []
    add = lambda n, name, ok, detail, nxt: st.append({"n": n, "name": name, "done": ok, "detail": detail, "next": nxt})
    brdp = os.path.join(d, "brd.yaml"); brd = yaml.safe_load(open(brdp, encoding="utf-8")) or {} if os.path.exists(brdp) else {}
    ok, out = run("brd.py", "check", brdp) if os.path.exists(brdp) else (False, "brd.yaml does not exist")
    add(1, "BRD complete", ok, "all must-have parameters present" if ok else out.splitlines()[0] + (f" (first: {out.splitlines()[1].strip()})" if len(out.splitlines()) > 1 else ""),
        f"Copilot: /start-project (new project), then \"Sources are ready. Run requirements-intake, then brd-builder.\"" if not os.path.exists(brdp) else "Copilot: continue requirements-intake and answer its questions, then run brd-builder")
    name, env = envconf.get_env(d) if os.path.exists(envconf.path(d)) else (None, None)
    if env is None: add(2, "Environment defined", False, "environments.yaml missing or no active environment", "Copy templates/environments.template.yaml to environments.yaml and fill it in; only you set authorisation")
    else:
        ok, out = run("envconf.py", "check", d); blocked = env.get("authorisation") in (None, "", "not_confirmed")
        add(2, "Environment defined", ok and not blocked, f"{name}: {env.get('base_url')}, authorisation {env.get('authorisation')}, monitoring {(env.get('monitoring') or {}).get('source')}" + ("; runs are BLOCKED until authorisation is set by you" if blocked else ""),
            "Fix environments.yaml (python tools/envconf.py check " + P + "); only you change the authorisation value")
    catp = os.path.join(d, "api-catalogue.yaml")
    ok, out = run("catalogue.py", "check", catp) if os.path.exists(catp) else (False, "api-catalogue.yaml does not exist")
    add(3, "API catalogue ready", ok, "catalogue passes its checks" if ok else out.splitlines()[0], f"Copilot: /build-catalogue Project: {P.split('projects/')[-1]}")
    tcp = os.path.join(d, "target-check.json"); tc = json.load(open(tcp)) if os.path.exists(tcp) else None
    url_matches = bool(tc and str(tc.get("base_url", "")).rstrip("/") == str((env or {}).get("base_url", "")).rstrip("/"))
    tc_ok = bool(tc and tc.get("environment") == name and url_matches and tc.get("calls_differ") == 0 and tc.get("calls_ok", 0) > 0 and mtime(tcp) >= mtime(catp))
    add(4, "Target answers the catalogue", tc_ok, ("no check yet" if not tc else f"{tc.get('calls_ok')} ok, {tc.get('calls_differ')} differ, {tc.get('calls_skipped')} skipped on {tc.get('environment')}" + ("; environment URL changed since check" if not url_matches else "") + ("; catalogue changed since" if mtime(tcp) < mtime(catp) else "")), f"Terminal: python tools/targetcheck.py {P}")
    scr = os.path.join(d, "k6", "script.js"); ok, out = run("k6check.py", d) if os.path.exists(scr) else (False, "k6/script.js does not exist")
    add(5, "k6 script matches BRD and catalogue", ok, "script passes k6check" if ok else out.splitlines()[0], f"Copilot: /build-script Project: {P.split('projects/')[-1]}")
    runs = []
    rd = os.path.join(d, "runs")
    for r in sorted(os.listdir(rd)) if os.path.isdir(rd) else []:
        f = os.path.join(rd, r, "run.json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("env") == name: runs.append((r, j, mtime(f)))
    sm = [x for x in runs if x[1]["profile"] == "smoke" and x[1]["outcome"] == "passed" and x[2] >= mtime(scr)]
    add(6, "Smoke run passed (current script)", bool(sm), f"{len(sm)} passed smoke run(s) after the latest script" if sm else "none yet", f"Terminal: python tools/runk6.py {P} --profile smoke")
    baseline_entry = next((t for t in (brd.get("test_types") or [])
                           if isinstance(t, dict) and brdtool.profile_key(t.get("type")) == "baseline"), {})
    baseline_needed = brdtool.yes_no(baseline_entry.get("needed")) is True
    baseline_path = os.path.join(d, "baseline-check.json")
    baseline_record = json.load(open(baseline_path, encoding="utf-8")) if os.path.exists(baseline_path) else {}
    baseline_signoff = baseline_record.get("sign_off") or {}
    baseline_params = baseline_entry.get("parameters") or {}
    try: baseline_repeat_runs = int(baseline_params.get("repeat_runs"))
    except (TypeError, ValueError): baseline_repeat_runs = 0
    try: baseline_variance = float(baseline_params.get("max_variance_pct"))
    except (TypeError, ValueError): baseline_variance = None
    current_baseline_ids = [r for r, j, _ in runs if j.get("profile") == "baseline"][-baseline_repeat_runs:] if baseline_repeat_runs else []
    signoff_ok = bool(baseline_record.get("consistent") and baseline_record.get("environment") == name
                       and baseline_record.get("run_ids") == current_baseline_ids
                       and baseline_signoff.get("run_ids") == current_baseline_ids
                       and baseline_record.get("max_variance_pct") == baseline_variance
                       and baseline_signoff.get("max_variance_pct") == baseline_record.get("max_variance_pct")
                       and baseline_signoff.get("by") and baseline_signoff.get("date"))
    baseline_done = not baseline_needed or signoff_ok
    if baseline_needed:
        detail = "consistent and signed off" if signoff_ok else "not consistent/signed off for the latest baseline runs"
        next_baseline = f"Terminal: python tools/baseline.py check {P}; after review, sign off with --by and --date"
    else:
        detail, next_baseline = "not required by the BRD", "No baseline profile is required"
    add(7, "Baseline consistent and signed off", baseline_done, detail, next_baseline)
    pm = re.search(r"\d[\d,]*", str((brd.get("workload") or {}).get("peak_concurrent_users", ""))); peak = int(pm.group(0).replace(",", "")) if pm else 0
    cap = int((env or {}).get("max_vus", 0) or 0)
    load_entry = next((t for t in (brd.get("test_types") or [])
                       if isinstance(t, dict) and brdtool.profile_key(t.get("type")) == "load"), {})
    load_params = load_entry.get("parameters") or {}
    load_steps = load_params.get("steps") if isinstance(load_params.get("steps"), list) else []
    valid_load_steps = [v for v in load_steps if isinstance(v, int) and not isinstance(v, bool) and v > 0]
    good = [x for x in runs if x[1]["profile"] == "load" and x[1]["outcome"] == "passed" and x[2] >= mtime(scr)]
    best = max([x[1]["vus"] for x in good] or [0]); goal = max(valid_load_steps or [0])
    step_limit = 5 if best == 0 else best * 2
    next_steps = [v for v in valid_load_steps if best < v <= min(step_limit, cap)]
    nxt_vus = next_steps[0] if next_steps else 0
    load_done = bool(good) and best >= goal > 0
    load_next = (f"Terminal: python tools/runk6.py {P} --profile load --vus {nxt_vus}"
                 if nxt_vus and baseline_done else
                 "Complete and sign off the baseline first" if not baseline_done else
                 "No configured BRD load step is within the environment max_vus" if valid_load_steps and min(valid_load_steps) > cap else
                 "No configured load step is within the 2x guard; review the explicit BRD step list")
    add(8, "Load stepped ramp reaches the BRD peak step", load_done and baseline_done,
        f"highest passed load run: {best} users; BRD step peak: {goal or 'not stated'}; environment limit: {cap}",
        load_next)
    top = sorted(good, key=lambda x: (x[1]["vus"], x[0]))[-1] if good else None
    rep = bool(top and os.path.exists(os.path.join(rd, top[0], "report.html")))
    add(9, "Report for the highest run", rep, f"report for {top[0]}" if rep else "no report yet", f"python tools/report.py {P} --run {top[0] if top else '<run-id>'}")
    cp = os.path.join(d, "client-pack")
    pack = bool(top and os.path.isdir(cp) and any(top[0] in x for x in os.listdir(cp)))
    add(10, "Client pack built", pack, "pack exists for the highest run" if pack else "not built", f"Copilot: /build-pack Project: {P.split('projects/')[-1]}  (read the cover before sharing)")
    first = next((s for s in st if not s["done"]), None)
    if as_json: print(json.dumps({"project": d, "environment": name, "stages": st, "next": first}, indent=1)); sys.exit(0 if not first else 1)
    print(f"Project: {d}   Environment: {name or 'none'}")
    for s in st: print(f"  [{'x' if s['done'] else ' '}] {s['n']}. {s['name']}: {s['detail']}")
    print("\nALL STAGES DONE." if not first else f"\nNEXT (stage {first['n']}): {first['next']}")
    sys.exit(0 if not first else 1)

if __name__ == "__main__": main()
