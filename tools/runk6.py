#!/usr/bin/env python3
"""Run the project's k6 script safely and record the run.
Usage: python tools/runk6.py <project_dir> --profile smoke|load [--vus N] [--ramp-up 30s] [--steady 3m] [--ramp-down 30s]
                             [--force-step] [--env NAME] [--open]
Writes projects/<client>/<app>/runs/<run-id>/{run.json, summary.json, k6-output.txt}. Requires PyYAML and k6.
Guards: k6check must pass; target and limits come from environments.yaml (active environment or --env); runs on an environment whose authorisation is not_confirmed are refused; a passed smoke run is needed before load;
first load run max 5 users, later at most 2x the highest passed load run (unless --force-step); total run max 20 min.
"""
import sys, os, re, json, shutil, subprocess, argparse, datetime, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf

def secs(s):
    m = re.fullmatch(r"(\d+)(s|m)", s)
    if not m: sys.exit(f"Bad duration '{s}', use e.g. 30s or 3m")
    return int(m.group(1)) * (60 if m.group(2) == "m" else 1)

def utcnow(): return datetime.datetime.now(datetime.timezone.utc)
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--profile", required=True, choices=["smoke", "load"])
    ap.add_argument("--vus", type=int, default=5); ap.add_argument("--ramp-up", default="30s"); ap.add_argument("--steady", default="3m")
    ap.add_argument("--ramp-down", default="30s"); ap.add_argument("--force-step", action="store_true"); ap.add_argument("--env"); ap.add_argument("--open", action="store_true")
    a = ap.parse_args(); d = a.project.rstrip("/")
    k6 = shutil.which("k6") or os.environ.get("K6_BIN")
    if not k6: sys.exit("k6 is not installed. Tell the user; on macOS the command is: brew install k6 (run it only with the user's approval).")
    k6ver = subprocess.run([k6, "version"], capture_output=True, text=True).stdout.strip()
    script = os.path.join(d, "k6", "script.js")
    chk = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "k6check.py"), d], capture_output=True, text=True, env={**os.environ, "K6_BIN": k6})
    if chk.returncode != 0: sys.exit("k6check failed, not running:\n" + chk.stdout)
    ename, env = envconf.get_env(d, a.env)
    if env is None: sys.exit(f"No environments.yaml, or unknown environment '{a.env or ''}'. Define it in {envconf.FILE} (template: templates/environments.template.yaml).")
    P, _ = envconf.problems(yaml.safe_load(open(envconf.path(d), encoding="utf-8")))
    if P: sys.exit("environments.yaml has issues, not running:\n  " + "\n  ".join(P))
    auth = env.get("authorisation")
    if auth == "not_confirmed":
        sys.exit(f"Environment '{ename}': authorisation is 'not_confirmed', so no request is sent. Only the test lead can change that field in {envconf.FILE}.")
    base = str(env["base_url"]).rstrip("/")
    cap_vus, cap_min = int(env["max_vus"]), int(env["max_run_minutes"])
    if a.vus > cap_vus and a.profile == "load": sys.exit(f"{a.vus} users exceeds max_vus={cap_vus} of environment '{ename}'.")
    total = secs(a.ramp_up) + secs(a.steady) + secs(a.ramp_down)
    if a.profile == "load" and total > cap_min * 60: sys.exit(f"Total run time {total}s exceeds max_run_minutes={cap_min} of environment '{ename}'")
    runs_dir = os.path.join(d, "runs"); os.makedirs(runs_dir, exist_ok=True)
    past = []
    for r in sorted(os.listdir(runs_dir)):
        f = os.path.join(runs_dir, r, "run.json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("env") == ename: past.append(j)
    if a.profile == "load":
        if not any(p["profile"] == "smoke" and p["outcome"] == "passed" for p in past):
            sys.exit("A passed smoke run is required before a load run. Run --profile smoke first.")
        best = max([p["vus"] for p in past if p["profile"] == "load" and p["outcome"] == "passed"] or [0])
        limit = 5 if best == 0 else best * 2
        if a.vus > limit and not a.force_step:
            sys.exit(f"{a.vus} users is too big a step (limit now {limit}: first load run max 5, then at most 2x the highest passed run). Step up gradually, or the user can approve --force-step.")
    vus = 1 if a.profile == "smoke" else a.vus
    rid = f"{utcnow().strftime('%Y%m%dT%H%M%SZ')}-{ename}-{a.profile}-{vus}vu"
    rd = os.path.join(runs_dir, rid); os.makedirs(rd)
    cmd = [k6, "run", "-e", f"BASE_URL={base}", "-e", f"PROFILE={a.profile}", "-e", f"MAX_VUS={min(vus, cap_vus)}", "-e", f"RAMP_UP={a.ramp_up}", "-e", f"STEADY={a.steady}",
           "-e", f"RAMP_DOWN={a.ramp_down}", "--summary-export", os.path.join(rd, "summary.json"), "--summary-trend-stats", "avg,min,med,max,p(90),p(95),p(99)", script]
    mon_cfg = env.get("monitoring") or {}; mon_src = mon_cfg.get("source", "none"); sampler = None; mon_status, mon_note = "none", ""
    if mon_src == "docker_stats":
        import monitor
        ok, why = monitor.docker_ready(mon_cfg.get("containers") or [])
        mon_status, mon_note = ("ready", "") if ok else ("unavailable", why)
        print("MONITORING: docker_stats ready" if ok else f"MONITORING: docker_stats NOT available ({why}); the run continues without server-side data")
    elif mon_src != "none":
        mon_status, mon_note = "not_built", f"collector for '{mon_src}' is not built yet"
        print(f"MONITORING: source '{mon_src}' is configured but its collector is not built yet; nothing is collected")
    print(f"Run {rid} -> {ename} {base}  ({a.profile}, {vus} user(s)), authorisation: {auth}"); start = utcnow()
    out = open(os.path.join(rd, "k6-output.txt"), "w", encoding="utf-8"); text = []
    kenv = dict(os.environ)
    if a.profile == "load":  # k6's built-in dashboard: live at http://localhost:5665 during the run, saved as dashboard.html (skipped by k6 for very short runs)
        kenv["K6_WEB_DASHBOARD"] = "true"; kenv["K6_WEB_DASHBOARD_EXPORT"] = os.path.join(rd, "dashboard.html")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=kenv)
    if mon_status == "ready": sampler = monitor.DockerSampler(mon_cfg.get("containers") or [], mon_cfg.get("interval_seconds", 5), pid=p.pid).start()
    for line in p.stdout: print(line, end=""); out.write(line); text.append(line)
    rc = p.wait(); end = utcnow(); out.close(); txt = "".join(text)
    mon_samples = 0
    if sampler:
        win = [secs(a.ramp_up), secs(a.ramp_up) + secs(a.steady)] if a.profile == "load" else None
        mdata = sampler.stop(win); mon_samples = len(mdata["samples"]); mon_status = mdata["status"]; mon_note = "; ".join(mdata["errors"])
        json.dump(mdata, open(os.path.join(rd, "monitoring.json"), "w"), indent=1)
        print(f"MONITORING: {mon_samples} samples saved in monitoring.json" + (f" (warnings: {mon_note})" if mon_note else ""))
    outcome = "passed" if rc == 0 else ("aborted_by_threshold" if rc == 99 and "stopping test prematurely" in txt else "thresholds_failed" if rc == 99 else "error")
    run = {"run_id": rid, "profile": a.profile, "vus": vus, "ramp_up": a.ramp_up, "steady": a.steady, "ramp_down": a.ramp_down, "env": ename, "env_type": env.get("type"), "authorisation": auth, "target": base,
           "start_utc": iso(start), "end_utc": iso(end), "k6_version": k6ver, "exit_code": rc, "outcome": outcome,
           "command": " ".join(c if not c.startswith("BASE_URL=") else "BASE_URL=" + base for c in cmd)}
    run["monitoring"] = {"source": mon_src, "status": mon_status, "samples": mon_samples, "note": mon_note}
    json.dump(run, open(os.path.join(rd, "run.json"), "w"), indent=2)
    print(f"\nOUTCOME: {outcome} (k6 exit {rc}). Window {run['start_utc']} to {run['end_utc']}. Saved in {rd}")
    # the report is built automatically after every run (also aborted ones); a report problem never changes the run outcome
    rp = os.path.join(rd, "report.html")
    if os.path.exists(os.path.join(rd, "summary.json")):
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.py"), d, "--run", rid], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(rp):
            print(f"REPORT: {rp}")
            if a.open:
                import webbrowser; webbrowser.open("file://" + os.path.abspath(rp))
        else: print("REPORT: could not be built: " + (r.stderr or r.stdout).strip().splitlines()[-1][:200])
    else: print("REPORT: skipped, k6 wrote no summary.json for this run")
    sys.exit(0 if rc == 0 else 1)

if __name__ == "__main__": main()
