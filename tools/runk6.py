#!/usr/bin/env python3
"""Run the project's k6 script safely and record the run.
Usage: python tools/runk6.py <project_dir> --profile smoke|baseline|load|stress|spike|endurance [--vus N]
                             [--force-step] [--env NAME] [--open]
Writes projects/<client>/<app>/runs/<run-id>/{run.json, summary.json, k6-output.txt}. Requires PyYAML and k6.
All profile parameters and flow selections come from brd.yaml. The environment supplies the target, VU/time caps and endurance reservation.
"""
import sys, os, re, json, shutil, subprocess, argparse, datetime, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf, brd as brdtool

def secs(s):
    m = re.fullmatch(r"(\d+)(s|m)", s)
    if not m: sys.exit(f"Bad duration '{s}', use e.g. 30s or 3m")
    return int(m.group(1)) * (60 if m.group(2) == "m" else 1)

def utcnow(): return datetime.datetime.now(datetime.timezone.utc)
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def profile_entry(brd, profile):
    return next((p for p in (brd.get("test_types") or [])
                 if isinstance(p, dict) and brdtool.profile_key(p.get("type")) == profile), None)

def duration_seconds(value, label):
    try: return secs(str(value))
    except SystemExit: raise ValueError(f"{label} must be a duration such as 30s or 3m")

def positive_int(value, label):
    try: n = int(value)
    except (TypeError, ValueError): raise ValueError(f"{label} must be a positive whole number")
    if n <= 0: raise ValueError(f"{label} must be a positive whole number")
    return n

def flow_ids(project, selected):
    cat = yaml.safe_load(open(os.path.join(project, "api-catalogue.yaml"), encoding="utf-8")) or {}
    known = {str(f.get("transaction")) for f in (cat.get("flows") or []) if isinstance(f, dict) and f.get("transaction")}
    if not isinstance(selected, list) or not selected:
        raise ValueError("The profile must select at least one flow in brd.yaml.")
    unknown = sorted(set(map(str, selected)) - known)
    if unknown: raise ValueError("Unknown profile flow ID(s) in brd.yaml: " + ", ".join(unknown))
    return sorted(set(map(str, selected)))

def profile_config(project, brd, profile, env, requested_vus):
    entry = profile_entry(brd, profile)
    if profile != "smoke" and (entry is None or brdtool.yes_no(entry.get("needed")) is not True):
        raise ValueError(f"Profile '{profile}' is not marked needed: yes in brd.yaml.")
    params = (entry or {}).get("parameters") or {}
    cap = int(env["max_vus"])
    if profile == "smoke":
        active_tx = {str(t.get("id")) for t in (brd.get("transactions") or []) if isinstance(t, dict) and t.get("id")}
        cat = yaml.safe_load(open(os.path.join(project, "api-catalogue.yaml"), encoding="utf-8")) or {}
        flows = sorted({str(f.get("transaction")) for f in (cat.get("flows") or [])
                        if isinstance(f, dict) and str(f.get("transaction")) in active_tx})
        if 120 > int(env["max_run_minutes"]) * 60:
            raise ValueError(f"Smoke profile maximum duration 120s exceeds max_run_minutes={env['max_run_minutes']}.")
        return {"vus": 1, "flows": flows, "stages": [], "duration": 120, "params": {}}
    flows = flow_ids(project, params.get("flows"))
    cfg = {"flows": flows, "params": params, "stages": [], "duration": 0}
    if profile == "baseline":
        cfg["vus"] = positive_int(params.get("users"), "Baseline user count")
        cfg["duration"] = 120
    elif profile == "load":
        steps = params.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("Load profile steps must be a non-empty list in brd.yaml.")
        values = [positive_int(v, "Load step") for v in steps]
        if values != sorted(set(values)):
            raise ValueError("Load profile steps must be unique and strictly increasing.")
        if requested_vus is None or requested_vus not in values:
            raise ValueError(f"--vus must select one of the BRD load steps: {values}.")
        values = [v for v in values if v <= requested_vus]
        hold = duration_seconds(params.get("step_hold"), "Load step_hold")
        peak_hold = duration_seconds(params.get("peak_hold"), "Load peak_hold")
        ramp_down = duration_seconds(params.get("ramp_down"), "Load ramp_down")
        cfg["stages"] = [(v, hold) for v in values] + [(requested_vus, peak_hold), (0, ramp_down)]
        cfg["vus"] = requested_vus
        cfg["start_vus"] = 0
        cfg["ramp_down"] = ramp_down
        cfg["duration"] = sum(d for _, d in cfg["stages"])
    elif profile == "stress":
        if requested_vus is None:
            raise ValueError("Stress requires an explicit --vus maximum for this run.")
        start = positive_int(params.get("start_users"), "Stress start_users")
        step = positive_int(params.get("step_size"), "Stress step_size")
        hold = duration_seconds(params.get("step_hold"), "Stress step_hold")
        recovery = duration_seconds(params.get("recovery_observation"), "Stress recovery_observation")
        ramp_down = duration_seconds(params.get("ramp_down"), "Stress ramp_down")
        if start > requested_vus:
            raise ValueError("Stress --vus cannot be below the BRD start_users.")
        targets = list(range(start, requested_vus + 1, step))
        if targets[-1] != requested_vus: targets.append(requested_vus)
        cfg["stages"] = [(v, hold) for v in targets] + [(start, recovery), (0, ramp_down)]
        cfg["vus"] = requested_vus
        cfg["start_vus"] = start
        cfg["ramp_down"] = ramp_down
        cfg["duration"] = sum(d for _, d in cfg["stages"])
        if not params.get("stop_rule"): raise ValueError("Stress stop_rule is required in brd.yaml.")
    elif profile == "spike":
        base = positive_int(params.get("base_users"), "Spike base_users")
        peak = positive_int(params.get("spike_users"), "Spike spike_users")
        spike_duration = duration_seconds(params.get("spike_duration"), "Spike spike_duration")
        recovery = duration_seconds(params.get("recovery_window"), "Spike recovery_window")
        ramp_down = duration_seconds(params.get("ramp_down"), "Spike ramp_down")
        cfg["stages"] = [(peak, spike_duration), (base, recovery), (0, ramp_down)]
        cfg["vus"] = peak
        cfg["start_vus"] = base
        cfg["ramp_down"] = ramp_down
        cfg["duration"] = sum(d for _, d in cfg["stages"])
    elif profile == "endurance":
        cfg["vus"] = positive_int(params.get("users"), "Endurance user count")
        run_duration = duration_seconds(params.get("duration"), "Endurance duration")
        ramp_down = duration_seconds(params.get("ramp_down"), "Endurance ramp_down")
        cfg["execution_duration"] = run_duration
        cfg["duration"] = run_duration + ramp_down
        cfg["ramp_down"] = ramp_down
        endurance = env.get("endurance") or {}
        if not endurance.get("test_window") or not endurance.get("data_volume"):
            raise ValueError("Endurance requires the active environment's reserved test_window and data_volume.")
    else:
        raise ValueError(f"Unsupported profile: {profile}")
    if cfg["vus"] > cap:
        raise ValueError(f"{cfg['vus']} users exceeds max_vus={cap} of the active environment.")
    if profile in ("stress", "spike"):
        safety = brd.get("operational_safety") or {}
        missing = [k for k in ("rollback_procedure", "on_call_contact") if not safety.get(k)]
        if missing: raise ValueError("Stress and spike require BRD operational_safety fields: " + ", ".join(missing))
        if not (brd.get("abort_conditions") or []):
            raise ValueError("Stress and spike require agreed abort_conditions in brd.yaml.")
    if cfg["duration"] > int(env["max_run_minutes"]) * 60:
        raise ValueError(f"Total run time {cfg['duration']}s exceeds max_run_minutes={env['max_run_minutes']} of the active environment.")
    return cfg

def baseline_is_signed_off(project, env_name, brd):
    path = os.path.join(project, "baseline-check.json")
    if not os.path.isfile(path): return False
    result = json.load(open(path, encoding="utf-8"))
    sign_off = result.get("sign_off") or {}
    baseline = profile_entry(brd, "baseline") or {}
    try: current_limit = float((baseline.get("parameters") or {}).get("max_variance_pct"))
    except (TypeError, ValueError): current_limit = None
    return bool(result.get("consistent") and result.get("environment") == env_name
                and result.get("max_variance_pct") == current_limit
                and sign_off.get("run_ids") == result.get("run_ids")
                and sign_off.get("max_variance_pct") == result.get("max_variance_pct")
                and sign_off.get("by") and sign_off.get("date"))

def check_run_guards(project, profile, cfg, brd, env_name, past, force_step=False):
    if profile != "smoke" and not any(p.get("profile") == "smoke" and p.get("outcome") == "passed" for p in past):
        raise ValueError("A passed smoke run is required before any non-smoke profile. Run --profile smoke first.")
    baseline = profile_entry(brd, "baseline")
    if profile == "load" and baseline and brdtool.yes_no(baseline.get("needed")) is True:
        if not baseline_is_signed_off(project, env_name, brd):
            raise ValueError("A consistent baseline must be checked and explicitly signed off before the stepped ramp.")
    if profile == "load":
        steps = [v for v, _ in cfg["stages"]]
        best = max([p["vus"] for p in past if p.get("profile") == "load" and p.get("outcome") == "passed"] or [0])
        target_limit = 5 if best == 0 else best * 2
        if cfg["vus"] > target_limit and not force_step:
            raise ValueError(f"{cfg['vus']} users is too big a step (limit now {target_limit}: first load run max 5, then at most 2x the highest passed run). Step up gradually, or the user can approve --force-step.")
        previous = best
        for value in steps:
            limit = 5 if previous == 0 else previous * 2
            if value > limit and not force_step:
                raise ValueError(f"{value} users is too big a step (limit now {limit}: first load run max 5, then at most 2x the highest passed run). Step up gradually, or the user can approve --force-step.")
            previous = value
    return True

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--profile", required=True, choices=["smoke", "baseline", "load", "stress", "spike", "endurance"])
    ap.add_argument("--vus", type=int); ap.add_argument("--force-step", action="store_true"); ap.add_argument("--env"); ap.add_argument("--open", action="store_true")
    a = ap.parse_args(); d = a.project.rstrip("/")
    if a.force_step and a.profile != "load":
        sys.exit("--force-step applies only to the stepped-ramp load profile.")
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
    brd_check = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "brd.py"),
                                "check", os.path.join(d, "brd.yaml")], capture_output=True, text=True)
    if brd_check.returncode != 0:
        sys.exit("brd.py check failed, not running:\n" + brd_check.stdout + brd_check.stderr)
    auth = env.get("authorisation")
    if auth == "not_confirmed":
        sys.exit(f"Environment '{ename}': authorisation is 'not_confirmed', so no request is sent. Only the test lead can change that field in {envconf.FILE}.")
    base = str(env["base_url"]).rstrip("/")
    brd_path = os.path.join(d, "brd.yaml")
    brd = yaml.safe_load(open(brd_path, encoding="utf-8")) or {}
    try:
        cfg = profile_config(d, brd, a.profile, env, a.vus)
    except ValueError as exc:
        sys.exit(str(exc))
    runs_dir = os.path.join(d, "runs")
    past = []
    for r in sorted(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else []:
        f = os.path.join(runs_dir, r, "run.json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("env") == ename: past.append(j)
    try:
        check_run_guards(d, a.profile, cfg, brd, ename, past, a.force_step)
    except ValueError as exc:
        sys.exit(str(exc))
    vus = cfg["vus"]
    if a.profile == "baseline":
        mon = env.get("monitoring") or {}
        import monitor
        rows, why = monitor.check_visibility(mon.get("source", "none"), mon.get("containers") or [])
        if why or not rows:
            sys.exit(f"Baseline requires visible monitoring before the run: {why or 'no samples returned'}.")
    os.makedirs(runs_dir, exist_ok=True)
    stamp = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    rid = f"{stamp}-{ename}-{a.profile}-{vus}vu"
    rd = os.path.join(runs_dir, rid); os.makedirs(rd)
    env_values = [
        f"BASE_URL={base}", f"PROFILE={a.profile}", f"MAX_VUS={min(vus, int(env['max_vus']))}",
        f"FLOWS={','.join(cfg['flows'])}",
        f"START_VUS={cfg.get('start_vus', 0)}",
        f"RAMP_DOWN={cfg.get('ramp_down', 0)}s",
        f"LOAD_STAGES={','.join(f'{v}:{s}s' for v, s in cfg['stages']) if a.profile == 'load' else ''}",
        f"STRESS_STAGES={','.join(f'{v}:{s}s' for v, s in cfg['stages']) if a.profile == 'stress' else ''}",
        f"SPIKE_STAGES={','.join(f'{v}:{s}s' for v, s in cfg['stages']) if a.profile == 'spike' else ''}",
        f"ENDURANCE_DURATION={cfg['execution_duration']}s" if a.profile == "endurance" else "ENDURANCE_DURATION=",
    ]
    cmd = [k6, "run"]
    for value in env_values: cmd += ["-e", value]
    cmd += ["--summary-export", os.path.join(rd, "summary.json"), "--summary-trend-stats", "avg,min,med,p(50),p(90),p(95),p(99),max", script]
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
    if a.profile in ("load", "stress", "spike", "endurance"):
        kenv["K6_WEB_DASHBOARD"] = "true"; kenv["K6_WEB_DASHBOARD_EXPORT"] = os.path.join(rd, "dashboard.html")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=kenv)
    if mon_status == "ready": sampler = monitor.DockerSampler(mon_cfg.get("containers") or [], mon_cfg.get("interval_seconds", 5), pid=p.pid).start()
    for line in p.stdout: print(line, end=""); out.write(line); text.append(line)
    rc = p.wait(); end = utcnow(); out.close(); txt = "".join(text)
    mon_samples = 0
    if sampler:
        mdata = sampler.stop(None); mon_samples = len(mdata["samples"]); mon_status = mdata["status"]; mon_note = "; ".join(mdata["errors"])
        json.dump(mdata, open(os.path.join(rd, "monitoring.json"), "w"), indent=1)
        print(f"MONITORING: {mon_samples} samples saved in monitoring.json" + (f" (warnings: {mon_note})" if mon_note else ""))
    outcome = "passed" if rc == 0 else ("aborted_by_threshold" if rc == 99 and "stopping test prematurely" in txt else "thresholds_failed" if rc == 99 else "error")
    run = {"run_id": rid, "profile": a.profile, "vus": vus, "flows": cfg["flows"],
           "profile_parameters": cfg["params"], "stages": cfg["stages"], "duration_seconds": cfg["duration"],
           "env": ename, "env_type": env.get("type"), "authorisation": auth, "target": base,
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
