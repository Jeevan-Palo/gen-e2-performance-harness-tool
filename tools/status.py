#!/usr/bin/env python3
"""Where does a project stand? Works it out from the files and the other tools' checks, and says what to do next.
Usage: python tools/status.py <project_dir> [--json]
Exit code 0 only when every stage is done. Requires PyYAML.
"""
import sys, os, re, json, subprocess, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf
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
    open_items_proceed = str((brd.get("meta") or {}).get("open_items_decision", "")).strip().lower() == "proceed_with_open_items"
    brd_done = ok or open_items_proceed
    add(1, "BRD complete", brd_done, "all must-have parameters present" if ok else ("must-have gaps recorded and user approved proceeding" if open_items_proceed else out.splitlines()[0] + (f" (first: {out.splitlines()[1].strip()})" if len(out.splitlines()) > 1 else "")),
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
    tc_ok = bool(tc and tc.get("environment") == name and tc.get("calls_differ") == 0 and tc.get("calls_ok", 0) > 0 and mtime(tcp) >= mtime(catp))
    add(4, "Target answers the catalogue", tc_ok, ("no check yet" if not tc else f"{tc.get('calls_ok')} ok, {tc.get('calls_differ')} differ, {tc.get('calls_skipped')} skipped on {tc.get('environment')}" + ("; catalogue changed since" if mtime(tcp) < mtime(catp) else "")), f"Terminal: python tools/targetcheck.py {P}")
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
    pm = re.search(r"\d[\d,]*", str((brd.get("workload") or {}).get("peak_concurrent_users", ""))); peak = int(pm.group(0).replace(",", "")) if pm else 0
    cap = int((env or {}).get("max_vus", 0) or 0)
    rp = envconf.plan(env)
    done_outcomes = ("passed", "thresholds_failed") if rp and rp["pack_if_targets_missed"] else ("passed",)
    good = [x for x in runs if x[1]["profile"] == "load" and x[1]["outcome"] in done_outcomes and x[2] >= mtime(scr)]
    best = max([x[1]["vus"] for x in good] or [0]); goal = min(peak or cap, cap) if cap else peak
    missed = any(x[1]["outcome"] == "thresholds_failed" for x in good)
    if rp and rp["load_steps"]:
        goal = rp["load_steps"][-1]; nxt_vus = next((s for s in rp["load_steps"] if s > best), goal)
        hint = f"(approved run plan: steps {rp['load_steps']})"; ru, sd, rdn = rp["ramp_up"], rp["steady"], rp["ramp_down"]
    else:
        nxt_vus = max(1, min(5 if best == 0 else best * 2, goal or 5)); ru, sd, rdn = "30s", "3m", "30s"
        hint = f"(you choose users and durations; the BRD says: {(brd.get('workload') or {}).get('peak_window', 'n/a')})"
    add(7, "Load stepped up to the peak", bool(good) and best >= goal > 0, f"highest completed load run: {best} users" + (" (targets missed; shown as Not met in the report)" if missed else "") + f"; peak in BRD: {peak or 'not stated'}; environment limit: {cap}",
        f"Terminal: python tools/runk6.py {P} --profile load --vus {nxt_vus} --ramp-up {ru} --steady {sd} --ramp-down {rdn}   {hint}")
    top = sorted(good, key=lambda x: (x[1]["vus"], x[0]))[-1] if good else None
    rep = bool(top and os.path.exists(os.path.join(rd, top[0], "report.html")))
    add(8, "Report for the highest run", rep, f"report for {top[0]}" if rep else "no report yet", f"python tools/report.py {P} --run {top[0] if top else '<run-id>'}")
    cp = os.path.join(d, "client-pack")
    pack = bool(top and os.path.isdir(cp) and any(top[0] in x for x in os.listdir(cp)))
    add(9, "Client pack built", pack, "pack exists for the highest run" if pack else "not built", f"Copilot: /build-pack Project: {P.split('projects/')[-1]}  (read the cover before sharing)")
    first = next((s for s in st if not s["done"]), None)
    if as_json: print(json.dumps({"project": d, "environment": name, "stages": st, "next": first}, indent=1)); sys.exit(0 if not first else 1)
    print(f"Project: {d}   Environment: {name or 'none'}")
    for s in st: print(f"  [{'x' if s['done'] else ' '}] {s['n']}. {s['name']}: {s['detail']}")
    print("\nALL STAGES DONE." if not first else f"\nNEXT (stage {first['n']}): {first['next']}")
    sys.exit(0 if not first else 1)

if __name__ == "__main__": main()
