#!/usr/bin/env python3
"""BRD helper. Usage:
  python tools/brd.py check  <brd.yaml>   list missing must-have parameters (exit 1 if any)
  python tools/brd.py render <brd.yaml>   write brd.md next to the yaml
Requires PyYAML (pip install pyyaml).
"""
import sys, os, re, math, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf

NP = "[NOT PROVIDED]"
RAG_RULES = {
    "green": "Every Must requirement is met at the agreed peak load.",
    "amber": "All Must requirements are met, but a non-Must requirement is not met or an agreed warning condition applies.",
    "red": "A Must requirement is not met or an abort threshold fires.",
    "grey": "A Must requirement has no valid peak-load evidence.",
}
PROFILE_PARAMETERS = {
    "baseline": [
        ("users", "user count"),
        ("repeat_runs", "number of repeated runs"),
        ("max_variance_pct", "maximum allowed variance (%)"),
        ("flows", "selected flow IDs"),
    ],
    "load": [
        ("steps", "user counts for each load step"),
        ("step_hold", "hold duration for each step"),
        ("peak_hold", "hold duration at peak"),
        ("ramp_down", "ramp-down duration"),
        ("flows", "selected flow IDs"),
    ],
    "stress": [
        ("start_users", "starting user count"),
        ("step_size", "user increase per step"),
        ("step_hold", "hold duration for each step"),
        ("stop_rule", "stop rule"),
        ("recovery_observation", "recovery observation period"),
        ("ramp_down", "ramp-down duration"),
        ("flows", "selected flow IDs"),
    ],
    "spike": [
        ("base_users", "base user count"),
        ("spike_users", "spike user count"),
        ("spike_duration", "spike duration"),
        ("recovery_window", "recovery observation window"),
        ("autoscaling_config", "autoscaling configuration (or explicitly state unknown)"),
        ("ramp_down", "ramp-down duration"),
        ("flows", "selected flow IDs"),
    ],
    "endurance": [
        ("users", "user count"),
        ("duration", "test duration"),
        ("ramp_down", "ramp-down duration"),
        ("flows", "selected flow IDs"),
    ],
}
PROFILE_LABELS = {
    "baseline": "Baseline (single user)",
    "load": "Load (stepped ramp)",
    "stress": "Stress",
    "spike": "Spike",
    "endurance": "Endurance (soak)",
    "scalability": "Scalability",
}

def blank(v):
    return v is None or (isinstance(v, str) and not v.strip()) or v == [] or v == {}

def yes_no(value):
    if value is True or str(value).strip().lower() in ("yes", "y", "true"):
        return True
    if value is False or str(value).strip().lower() in ("no", "n", "false"):
        return False
    return None

def positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0

def duration_value(value):
    return bool(re.fullmatch(r"\d+(?:s|m)", str(value or "")))

def profile_key(value):
    name = re.sub(r"[^a-z]", "", str(value).lower())
    if name.startswith("baseline"): return "baseline"
    if name.startswith("load"): return "load"
    if name.startswith("stress"): return "stress"
    if name.startswith("spike"): return "spike"
    if name.startswith("endurance") or name.startswith("soak"): return "endurance"
    if name.startswith("scalability"): return "scalability"
    return ""

def rows(lst, keys):
    return [r for r in (lst or []) if isinstance(r, dict) and any(not blank(r.get(k)) for k in keys)]

def has_evidence(d, field):
    return any(isinstance(item, dict) and item.get("field") == field and not blank(item.get("source"))
               for item in (d.get("evidence") or []))


def apply_env(d, folder):
    """If environments.yaml exists, its active environment is the source of truth for the environment fields."""
    name, e = envconf.get_env(folder)
    if e is None: return d
    env = d.setdefault("environment", {}) if isinstance(d.get("environment"), dict) else d.__setitem__("environment", {}) or d["environment"]
    mon = e.get("monitoring") or {}
    env["target"] = f"{name}: {e.get('description', '')} - {e.get('base_url', '')}".strip(" -:") if e.get("base_url") else ""
    env["owner"] = e.get("owner", "")
    auth = e.get("authorisation", "")
    env["authorisation"] = (auth + (f" - {e['authorisation_note']}" if e.get("authorisation_note") else "")) if auth else ""
    for k in ("comparison_with_production", "third_party_services", "test_data", "test_windows"): env[k] = e.get(k, "")
    endurance = e.get("endurance")
    if not isinstance(endurance, dict): endurance = {}
    env["_endurance_test_window"] = endurance.get("test_window", "")
    env["_endurance_data_volume"] = endurance.get("data_volume", "")
    env["monitoring_access"] = (f"{mon.get('source')}" + (f": {mon.get('detail')}" if mon.get("detail") else "")) if mon.get("source") else ""
    env["_auth_status"] = auth; env["_env_name"] = name
    return d

def check(d):
    m = []
    g = lambda *p: _get(d, p)
    for p, label in [(("meta", "client"), "Client name"), (("meta", "application"), "Application name"),
                     (("purpose",), "Purpose: why testing is needed now"),
                     (("scope_in",), "In-scope applications / journeys"),
                     (("workload", "peak_window"), "Peak window and duration"),
                     (("workload", "think_time"), "User think time / pacing"),
                     (("workload", "basis"), "Workload basis (measured / forecast / assumed)"),
                     (("environment", "target"), "Target environment"),
                     (("environment", "owner"), "Environment owner"),
                     (("environment", "test_data"), "Test data needs"),
                     (("environment", "personal_data_confirmation"), "Confirmation that no real personal/payment data is used"),
                     (("environment", "monitoring_access"), "Monitoring access (tool and who grants it)"),
                     (("environment", "test_windows"), "Allowed test windows")]:
        if blank(g(*p)): m.append(label)
    if blank(g("workload", "peak_concurrent_users")) and blank(g("workload", "peak_tps")):
        m.append("Peak load: concurrent users or transactions per second (state sitewide or per transaction)")
    st = g("environment", "_auth_status")
    if st == "not_confirmed": m.append(f"Authorisation to test the active environment '{g('environment', '_env_name')}' (status: not_confirmed)")
    tx = rows(d.get("transactions"), ["name"])
    if not tx: m.append("At least one business transaction")
    for t in tx:
        if blank(t.get("traffic_share")): m.append(f"Traffic share for transaction {t.get('id') or t.get('name')}")
        if blank(t.get("measure_start_end")): m.append(f"Response-time start/end point for transaction {t.get('id') or t.get('name')}")
    rq = rows(d.get("requirements"), ["metric", "target"])
    if not rq: m.append("At least one measurable performance requirement")
    for r in rq:
        for k, lab in [("target", "target"), ("percentile", "percentile"), ("load_condition", "load condition")]:
            if blank(r.get(k)) and not (k == "percentile" and str(r.get("metric", "")).lower() in ("error rate", "throughput", "availability")):
                m.append(f"Requirement {r.get('id') or r.get('metric')}: {lab}")
    test_types = [t for t in (d.get("test_types") or []) if isinstance(t, dict)]
    selected_profiles = []
    seen_profiles = set()
    for index, t in enumerate(test_types):
        flag = yes_no(t.get("needed"))
        name = t.get("type") or "unnamed"
        key = profile_key(name)
        if not key:
            m.append(f"Test type '{name}': profile is not recognised by the harness")
            continue
        if key in seen_profiles:
            m.append(f"Test profile '{name}' is listed more than once")
        seen_profiles.add(key)
        if flag is None:
            m.append(f"Test type '{name}': confirm whether it is needed (yes/no)")
            continue
        if not has_evidence(d, f"test_types[{index}].needed"):
            m.append(f"Evidence for test_types[{index}].needed")
        if not flag:
            continue
        selected_profiles.append((key, name, t))
        if key == "scalability":
            m.append("Scalability is marked needed, but is not supported by this harness release; agree an alternative or record it as out of scope")
            continue
        params = t.get("parameters") if isinstance(t.get("parameters"), dict) else {}
        for field, label in PROFILE_PARAMETERS.get(key, []):
            if blank(params.get(field)):
                m.append(f"{name} profile: {label}")
            elif not has_evidence(d, f"test_types[{index}].parameters.{field}"):
                m.append(f"Evidence for test_types[{index}].parameters.{field}")
        if key in PROFILE_PARAMETERS and params.get("flows") and (
                not isinstance(params.get("flows"), list) or not all(isinstance(x, str) and x.strip() for x in params["flows"])):
            m.append(f"{name} profile: flows must be a list of catalogue flow IDs")
        if (key in PROFILE_PARAMETERS and isinstance(params.get("flows"), list)
                and all(isinstance(x, str) for x in params["flows"])
                and len(set(params["flows"])) != len(params["flows"])):
            m.append(f"{name} profile: flows must not contain duplicates")
        if key == "baseline":
            if not positive_int(params.get("repeat_runs")) or params.get("repeat_runs", 0) < 2:
                m.append(f"{name} profile: repeat_runs must be a whole number of at least 2")
            try: variance = float(params.get("max_variance_pct"))
            except (TypeError, ValueError): variance = 0
            if not math.isfinite(variance) or variance <= 0: m.append(f"{name} profile: max_variance_pct must be greater than 0")
        if key == "load" and not isinstance(params.get("steps"), list):
            m.append(f"{name} profile: steps must be a list of user counts")
        if key == "load" and isinstance(params.get("steps"), list):
            steps = params["steps"]
            if not steps or not all(positive_int(step) for step in steps) or steps != sorted(set(steps)):
                m.append(f"{name} profile: steps must be unique, increasing positive whole numbers")
            if any(not duration_value(params.get(field)) for field in ("step_hold", "peak_hold", "ramp_down")):
                m.append(f"{name} profile: step_hold, peak_hold and ramp_down must use seconds or minutes (for example 30s or 3m)")
        if key == "stress":
            for field in ("start_users", "step_size"):
                if not positive_int(params.get(field)): m.append(f"{name} profile: {field} must be a positive whole number")
            if any(not duration_value(params.get(field)) for field in ("step_hold", "recovery_observation", "ramp_down")):
                m.append(f"{name} profile: step_hold, recovery_observation and ramp_down must use seconds or minutes")
        if key == "spike":
            for field in ("base_users", "spike_users"):
                if not positive_int(params.get(field)): m.append(f"{name} profile: {field} must be a positive whole number")
            if any(not duration_value(params.get(field)) for field in ("spike_duration", "recovery_window", "ramp_down")):
                m.append(f"{name} profile: spike_duration, recovery_window and ramp_down must use seconds or minutes")
        if key == "endurance":
            if not positive_int(params.get("users")): m.append(f"{name} profile: users must be a positive whole number")
            if not duration_value(params.get("duration")) or not duration_value(params.get("ramp_down")):
                m.append(f"{name} profile: duration and ramp_down must use seconds or minutes")
    if not any(yes_no(t.get("needed")) is True for t in test_types):
        m.append("Test types needed (at least one marked yes)")
    for key, name, _ in selected_profiles:
        if key == "endurance":
            if blank(g("environment", "_endurance_test_window")):
                m.append("Endurance test window in environments.yaml")
            if blank(g("environment", "_endurance_data_volume")):
                m.append("Endurance data volume in environments.yaml")
        if key in ("stress", "spike"):
            safety = d.get("operational_safety") or {}
            for field, label in [
                ("abort_owner", "abort decision owner"),
                ("rollback_owner", "rollback owner"),
                ("rollback_procedure", "rollback procedure"),
                ("on_call_contact", "on-call contact"),
            ]:
                if blank(safety.get(field)):
                    m.append(f"{name} profile: {label}")
                elif not has_evidence(d, f"operational_safety.{field}"):
                    m.append(f"Evidence for operational_safety.{field}")
        if key in PROFILE_PARAMETERS:
            criterion_index, criteria = next(((i, c) for i, c in enumerate(d.get("exit_criteria") or [])
                                              if isinstance(c, dict) and profile_key(c.get("profile")) == key), (None, None))
            if not criteria or blank(criteria.get("start_when")) or blank(criteria.get("finish_when")):
                m.append(f"{name} profile: entry and exit criteria (start_when and finish_when)")
            else:
                for field in ("start_when", "finish_when"):
                    if not has_evidence(d, f"exit_criteria[{criterion_index}].{field}"):
                        m.append(f"Evidence for exit_criteria[{criterion_index}].{field}")
    for key, name in PROFILE_LABELS.items():
        if key not in seen_profiles:
            m.append(f"Test type '{name}': confirm whether it is needed (yes/no)")
    rag = d.get("rag_rules") or {}
    if rag:
        for field in ("green", "amber", "red", "grey"):
            if blank(rag.get(field)):
                m.append(f"RAG rule definition: {field} status")
        if not isinstance(rag.get("amber_warning_conditions", []), list):
            m.append("RAG amber_warning_conditions must be a list")
        elif rag.get("amber_warning_conditions"):
            if not has_evidence(d, "rag_rules.amber_warning_conditions"):
                m.append("Evidence for rag_rules.amber_warning_conditions")
        active_warnings = rag.get("active_amber_warnings", [])
        if not isinstance(active_warnings, list):
            m.append("RAG active_amber_warnings must be a list")
        else:
            if any(warning not in (rag.get("amber_warning_conditions") or []) for warning in active_warnings):
                m.append("RAG active amber warnings must match agreed amber_warning_conditions")
            if active_warnings and not has_evidence(d, "rag_rules.active_amber_warnings"):
                m.append("Evidence for rag_rules.active_amber_warnings")
    ab = rows(d.get("abort_conditions"), ["threshold", "action"])
    if not ab: m.append("Abort (stop) conditions agreed with operations")
    else:
        for a in d.get("abort_conditions") or []:
            if blank(a.get("threshold")) or blank(a.get("action")):
                m.append(f"Abort condition '{a.get('condition')}': threshold and action")
    return m

def _get(d, path):
    for p in path:
        d = d.get(p) if isinstance(d, dict) else None
    return d

def v(x): return NP if blank(x) else str(x)

def table(headers, data, keys, blank_as_empty=()):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in data:
        cells = ["" if (k in blank_as_empty and blank(r.get(k))) else v(r.get(k)) for k in keys]
        out.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    if not data: out.append("| " + " | ".join([NP] * len(headers)) + " |")
    return out

def render(d):
    m = d.get("meta") or {}
    w = d.get("workload") or {}
    e = d.get("environment") or {}
    mr = d.get("monitoring_reporting") or {}
    L = ["# Business Requirements Document: Performance Testing", "",
         "| Field | Value |", "|---|---|"]
    for lab, k in [("Client / business unit", "client"), ("Application / system", "application"), ("Document version", "version"),
                   ("Date", "date"), ("Client BRD owner", "brd_owner"), ("Prepared by", "prepared_by"), ("Status", "status")]:
        L.append(f"| {lab} | {v(m.get(k))} |")
    L += ["", "## 1. Purpose and background", v(d.get("purpose")), "",
          "This BRD states the business transactions in scope and the performance expectations that the test must prove. It does not describe how the test is built.", "",
          "## 2. Objectives and scope", "", "Objectives"]
    L += [f"{i}. {o}" for i, o in enumerate(d.get("objectives") or [], 1)] or [NP]
    L += ["", "In scope: " + ("; ".join(d.get("scope_in") or []) or NP), "Out of scope: " + ("; ".join(d.get("scope_out") or []) or NP), "",
          "## 3. Stakeholders and approvers", ""]
    L += table(["Role", "Name", "Responsibility"], d.get("stakeholders") or [], ["role", "name", "responsibility"])
    L += ["", "## 4. Business transactions in scope", ""]
    L += table(["ID", "Transaction", "User type", "Criticality", "Share of traffic", "Response-time start/end", "Notes"],
               rows(d.get("transactions"), ["name"]) or [{}], ["id", "name", "user_type", "criticality", "traffic_share", "measure_start_end", "notes"])
    L += ["", "## 5. Workload model", ""]
    L += table(["Item", "Value"], [{"i": lab, "v": w.get(k)} for lab, k in [
        ("Peak concurrent users", "peak_concurrent_users"), ("Peak requests or transactions per second", "peak_tps"),
        ("Peak window and duration", "peak_window"), ("Average daily volume", "avg_daily_volume"),
        ("Expected growth over 12 months", "growth_12m"), ("User think time and pacing", "think_time"),
        ("Geographic distribution of users", "geography"), ("Data volumes in the system", "data_volumes"),
        ("Basis of figures (measured / forecast / assumed)", "basis")]], ["i", "v"])
    L += ["", "## 6. Performance requirements", ""]
    L += table(["ID", "Transaction", "Metric", "Target", "Percentile", "Load condition", "Priority", "Notes"],
               rows(d.get("requirements"), ["metric", "target"]) or [{}],
               ["id", "transaction", "metric", "target", "percentile", "load_condition", "priority", "notes"],
               blank_as_empty=("notes",))
    L += ["", "## 7. Test types required", ""]
    L += table(["Test type", "Needed?", "Notes"], d.get("test_types") or [], ["type", "needed", "notes"])
    for test in d.get("test_types") or []:
        if not isinstance(test, dict) or yes_no(test.get("needed")) is not True:
            continue
        key = profile_key(test.get("type"))
        parameters = test.get("parameters") or {}
        if key not in PROFILE_PARAMETERS or not isinstance(parameters, dict):
            continue
        L += ["", f"### {test.get('type')}", ""]
        L += table(["Profile parameter", "Agreed value"],
                   [{"field": label, "value": parameters.get(field)} for field, label in PROFILE_PARAMETERS[key]],
                   ["field", "value"])
    L += ["", "## 8. Test environment and data", ""]
    L += table(["Item", "Detail"], [{"i": lab, "v": e.get(k)} for lab, k in ([("Authorisation to test", "authorisation")] if e.get("authorisation") else []) + [
        ("Target environment", "target"), ("Environment owner", "owner"), ("Comparison with production", "comparison_with_production"),
        ("Third-party services", "third_party_services"), ("Test data needs", "test_data"),
        ("No real personal or payment data (confirmation)", "personal_data_confirmation"),
        ("Monitoring access", "monitoring_access"), ("Allowed test windows", "test_windows"),
        ("Endurance test window", "_endurance_test_window"), ("Endurance data volume", "_endurance_data_volume")]], ["i", "v"])
    L += ["", "## 9. Test stop (abort) conditions", "", "Agree these with the operations team before the test is approved.", ""]
    L += table(["Condition", "Threshold", "Action"], d.get("abort_conditions") or [], ["condition", "threshold", "action"])
    safety = d.get("operational_safety") or {}
    L += ["", "Operational safety contacts and procedure", ""]
    L += table(["Item", "Agreed detail"], [
        {"item": "Abort decision owner", "detail": safety.get("abort_owner")},
        {"item": "Rollback owner", "detail": safety.get("rollback_owner")},
        {"item": "Rollback procedure", "detail": safety.get("rollback_procedure")},
        {"item": "On-call contact", "detail": safety.get("on_call_contact")},
    ], ["item", "detail"])
    L += ["", "## 10. Monitoring and reporting", f"Metrics collected: {v(mr.get('metrics'))}", f"Tools: {v(mr.get('tools'))}",
          f"Interim updates: {v(mr.get('interim_updates'))}", f"Final report: {v(mr.get('final_report'))}", "",
          "The report states each requirement ID as met, not met or not measured, with evidence. Standard results include p50/p90/p95/p99, TPS, error rate, CPU and memory; database metrics are shown only when collected.", "",
          "RAG rules (fixed harness standard; each metric is compared with its exact BRD target):"]
    rag = d.get("rag_rules") or RAG_RULES
    L += [f"- {label}: {v(rag.get(key))}" for key, label in [
        ("green", "Green"), ("amber", "Amber"), ("red", "Red"), ("grey", "Grey / not assessed")]]
    amber_warnings = rag.get("amber_warning_conditions") or []
    if amber_warnings:
        L += ["", "Client-agreed amber warning conditions:"] + [f"- {v(item)}" for item in amber_warnings]
    L += ["",
          "## 11. Assumptions, constraints, dependencies and risks", ""]
    L += table(["Type", "Description", "Owner", "Impact if wrong"], rows(d.get("risks"), ["description"]) or [{}], ["type", "description", "owner", "impact"])
    L += ["", "## 12. Acceptance and exit criteria", "", "The test is accepted when:"]
    criteria = [c for c in (d.get("exit_criteria") or []) if isinstance(c, dict)]
    if criteria:
        L += table(["Profile", "Entry criteria", "Exit criteria"], criteria, ["profile", "start_when", "finish_when"])
    else:
        L += [f"{i}. {c}" for i, c in enumerate(d.get("exit_criteria") or [], 1)] or [NP]
    L += ["", "## 13. Open items", ""]
    L += table(["#", "Question", "Owner", "Due", "Status"],
               [dict(r, n=i) for i, r in enumerate(rows(d.get("open_items"), ["question"]), 1)] or [{}], ["n", "question", "owner", "due", "status"])
    L += ["",     "## 14. Analysis findings", "",
    "The tool supplies observations and evidence. Layer, hypothesis and finding wording is included in reports only when a human records the wording and approval details below.", ""]
    L += table(["Run IDs", "Layer", "Hypothesis", "Evidence reference", "Finding", "Approved by", "Approved date"],
          d.get("analysis_findings") or [],
          ["run_ids", "layer", "hypothesis", "evidence", "finding", "approved_by", "approved_date"])
    L += ["", "## 15. Approval", ""]
    L += table(["Name", "Role", "Decision", "Date"], d.get("approvals") or [], ["name", "role", "decision", "date"])
    return "\n".join(L) + "\n"

def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "render"):
        sys.exit(__doc__)
    path = sys.argv[2]
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    d = apply_env(d, os.path.dirname(os.path.abspath(path)))
    if sys.argv[1] == "check":
        miss = check(d)
        if miss:
            print(f"MISSING must-have parameters ({len(miss)}):")
            for i, x in enumerate(miss, 1): print(f"  {i}. {x}")
            sys.exit(1)
        print("OK: all must-have parameters present.")
    else:
        out = os.path.join(os.path.dirname(os.path.abspath(path)), "brd.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(render(d))
        print("Wrote", out)

if __name__ == "__main__":
    main()
