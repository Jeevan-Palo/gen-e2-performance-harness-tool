#!/usr/bin/env python3
"""The single next action for a project, and whether a human must decide first. Works for any project.
Usage: python tools/next.py <project_dir> [--json]
Builds on tools/status.py (which stage is next) and adds the human gates, so the orchestrating agent does not have to remember them.
Exit code: 0 = every stage done, 1 = the next action can proceed without asking, 2 = a human decision is needed first (see `gate` and `ask`).
Read-only: sends no request and writes no file. Requires PyYAML.
"""
import sys, os, json, subprocess, yaml
T = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, T)
import envconf

# Every gate is a point where only the user may decide. Each id must be described in .github/skills/end-to-end/SKILL.md (lint checks).
GATES = {
    "sources": "Add the client's files to sources/ (or tell me there are none).",
    "business_facts": "Answer the business facts from `python tools/brd.py questions <brd.yaml>`, reply 'accept' or change the advised values from `brd.py advise`, and approve the run plan (load steps, durations, discovery actions).",
    "environment": "Give the environment URL and owner, and fill environments.yaml (python tools/envconf.py check).",
    "authorisation": "Only you can state whether this environment may be tested. Say so in chat and I will record your statement and the date in authorisation_note.",
    "credentials": "Export the variables named in credentials_env_vars in your own terminal and run the command yourself (the check sends one login POST).",
    "run_plan": "Approve a run plan (load_steps, ramp_up, steady, ramp_down, discovery_actions, pack_if_targets_missed), or tell me the users and durations for each run.",
    "failed_run": "The latest run was aborted, errored or failed to start. Decide: fix and rebuild the script, change the plan, or run it again yourself. I will not retry on my own.",
    "targets_missed": "The latest load run completed but missed targets and the plan does not allow packing missed targets. Decide: set pack_if_targets_missed, change the plan, or stop.",
}
# A reply the user can copy and paste for each gate (sample wording only; the user changes it to their own decision).
GATE_EXAMPLES = {
    "sources": "Files added to sources/",
    "business_facts": "accept; load steps 2, 4, 5 users; ramp 30s, steady 3m, ramp-down 30s; pack if targets missed",
    "environment": "URL https://staging.example.com, owner Jane Doe (QA lead)",
    "authorisation": "Yes, I confirm testing the <environment name> environment is authorised",
    "credentials": "Exported; I will run the check myself",
    "run_plan": "load_steps 2, 4, 5; ramp_up 30s; steady 3m; ramp_down 30s; pack_if_targets_missed true",
    "failed_run": "Fix the script and rebuild it; I will start the run myself",
    "targets_missed": "Set pack_if_targets_missed to true",
}
STAGE_SKILL = {1: "requirements-intake, then brd-builder", 2: None, 3: "api-source-selector", 4: None, 5: "k6-script-builder", 6: "k6-run", 7: "k6-run, monitoring-evidence", 8: "report-builder", 9: "client-pack"}

def status(d):
    r = subprocess.run([sys.executable, os.path.join(T, "status.py"), d, "--json"], capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except ValueError: sys.exit("status.py did not return JSON:\n" + (r.stdout + r.stderr).strip()[:500])

def latest_run(d, env_name, since):
    rd = os.path.join(d, "runs"); best = None
    for r in sorted(os.listdir(rd)) if os.path.isdir(rd) else []:
        f = os.path.join(rd, r, "run.json")
        if not os.path.exists(f) or os.path.getmtime(f) < since: continue
        try: j = json.load(open(f, encoding="utf-8"))
        except ValueError: continue
        if j.get("env") == env_name: best = (r, j)
    return best

def load_yaml(p):
    try: return yaml.safe_load(open(p, encoding="utf-8")) or {} if os.path.exists(p) else {}
    except yaml.YAMLError: return {}

def decide(d):
    d = d.rstrip("/"); s = status(d); nxt = s.get("next")
    out = {"project": d, "environment": s.get("environment"), "done": nxt is None, "stage": None, "actor": None, "skill": None,
           "command": None, "gate": None, "needs_human": False, "ask": None, "example": None, "reason": None}
    if nxt is None:
        out.update(actor="copilot", reason="All stages are done. Tell the user where the pack is and to read its cover page before sharing; never share it.")
        return out
    n = nxt["n"]; out["stage"] = {"n": n, "name": nxt["name"]}; out["skill"] = STAGE_SKILL.get(n); out["command"] = nxt["next"]
    out["actor"] = "tool" if nxt["next"].startswith(("Terminal:", "python ")) else "copilot"
    gate = lambda g, why: out.update(gate=g, needs_human=True, actor="human", ask=GATES[g], example=GATE_EXAMPLES[g], reason=why)
    name, env = envconf.get_env(d) if os.path.exists(envconf.path(d)) else (None, None)
    blocked = env is not None and env.get("authorisation") in (None, "", "not_confirmed")
    src = os.path.join(d, "sources")
    if n == 1:
        files = [f for f in os.listdir(src) if not f.startswith(".")] if os.path.isdir(src) else []
        brd = load_yaml(os.path.join(d, "brd.yaml"))
        if "brdexport.py" in nxt["next"]: return out
        if blocked: gate("authorisation", f"environment '{name}' has authorisation not_confirmed, which is a BRD must-have")
        elif not files: gate("sources", "sources/ is empty")
        elif not brd.get("evidence"): out["reason"] = "Sources are present and intake has not recorded any evidence yet: read them (requirements-intake) before asking anything."
        else: gate("business_facts", "must-have parameters are missing after intake; ask once, in one message")
    elif n == 2:
        if env is None: gate("environment", "environments.yaml is missing or has no active environment")
        elif blocked: gate("authorisation", f"environment '{name}' has authorisation not_confirmed")
        else: gate("environment", "environments.yaml does not pass `envconf.py check`")
    elif n == 3 and blocked: gate("authorisation", f"environment '{name}' is not authorised, so it must not be browsed")
    elif n == 4:
        if blocked: gate("authorisation", f"environment '{name}' is not authorised, so no request may be sent")
        else:
            import targetcheck
            needs_login = any((a.get("auth") not in (None, "", "none")) for a in (load_yaml(os.path.join(d, "api-catalogue.yaml")).get("apis") or []))
            if needs_login and not targetcheck.credentials(env): gate("credentials", "the catalogue has calls that need a login and credentials_env_vars are not set in the shell")
    elif n in (6, 7):
        scr = os.path.join(d, "k6", "script.js"); since = os.path.getmtime(scr) if os.path.exists(scr) else 0
        rp = envconf.plan(env) if env else None
        last = latest_run(d, name, since)
        if blocked: gate("authorisation", f"environment '{name}' is not authorised, so runs are refused")
        elif last and last[1].get("outcome") in ("aborted_by_threshold", "error"): gate("failed_run", f"latest run {last[0]} ended {last[1].get('outcome')}")
        elif last and last[1].get("outcome") == "thresholds_failed" and not (rp and rp["pack_if_targets_missed"]): gate("targets_missed", f"latest run {last[0]} missed targets")
        elif last and last[1].get("profile") == "smoke" and last[1].get("outcome") != "passed": gate("failed_run", f"smoke run {last[0]} did not pass")
        elif n == 7 and not rp: gate("run_plan", "no approved run plan (approved_note is empty)")
    return out

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    out = decide(sys.argv[1])
    if "--json" in sys.argv: print(json.dumps(out, indent=1))
    elif out["done"]: print("ALL STAGES DONE.\n" + out["reason"])
    elif out["needs_human"]: print(f"STOP (stage {out['stage']['n']} {out['stage']['name']}): {out['gate']}\n  why: {out['reason']}\n  ask: {out['ask']}\n  example reply: {out['example']}")
    else: print(f"PROCEED (stage {out['stage']['n']} {out['stage']['name']}), actor {out['actor']}" + (f", skill {out['skill']}" if out["skill"] else "") + f"\n  do: {out['command']}" + (f"\n  note: {out['reason']}" if out["reason"] else ""))
    sys.exit(0 if out["done"] else 2 if out["needs_human"] else 1)

if __name__ == "__main__": main()
