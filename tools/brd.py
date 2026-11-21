#!/usr/bin/env python3
"""BRD helper. Usage:
  python tools/brd.py check  <brd.yaml>   list missing must-have parameters (exit 1 if any)
  python tools/brd.py render <brd.yaml>   write brd.md next to the yaml
Requires PyYAML (pip install pyyaml).
"""
import sys, os, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf

NP = "[NOT PROVIDED]"

def blank(v):
    return v is None or (isinstance(v, str) and not v.strip()) or v == [] or v == {}

def rows(lst, keys):
    return [r for r in (lst or []) if isinstance(r, dict) and any(not blank(r.get(k)) for k in keys)]


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
    if not any((t.get("needed") is True or str(t.get("needed", "")).strip().lower() in ("yes", "y", "true")) for t in (d.get("test_types") or []) if isinstance(t, dict)):
        m.append("Test types needed (at least one marked yes)")
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
    L += ["", "## 8. Test environment and data", ""]
    L += table(["Item", "Detail"], [{"i": lab, "v": e.get(k)} for lab, k in ([("Authorisation to test", "authorisation")] if e.get("authorisation") else []) + [
        ("Target environment", "target"), ("Environment owner", "owner"), ("Comparison with production", "comparison_with_production"),
        ("Third-party services", "third_party_services"), ("Test data needs", "test_data"),
        ("No real personal or payment data (confirmation)", "personal_data_confirmation"),
        ("Monitoring access", "monitoring_access"), ("Allowed test windows", "test_windows")]], ["i", "v"])
    L += ["", "## 9. Test stop (abort) conditions", "", "Agree these with the operations team before the test is approved.", ""]
    L += table(["Condition", "Threshold", "Action"], d.get("abort_conditions") or [], ["condition", "threshold", "action"])
    L += ["", "## 10. Monitoring and reporting", f"Metrics collected: {v(mr.get('metrics'))}", f"Tools: {v(mr.get('tools'))}",
          f"Interim updates: {v(mr.get('interim_updates'))}", f"Final report: {v(mr.get('final_report'))}", "",
          "The report states each requirement ID as met, not met or not measured, with evidence.", "",
          "## 11. Assumptions, constraints, dependencies and risks", ""]
    L += table(["Type", "Description", "Owner", "Impact if wrong"], rows(d.get("risks"), ["description"]) or [{}], ["type", "description", "owner", "impact"])
    L += ["", "## 12. Acceptance and exit criteria", "", "The test is accepted when:"]
    L += [f"{i}. {c}" for i, c in enumerate(d.get("exit_criteria") or [], 1)] or [NP]
    L += ["", "## 13. Open items", ""]
    L += table(["#", "Question", "Owner", "Due", "Status"],
               [dict(r, n=i) for i, r in enumerate(rows(d.get("open_items"), ["question"]), 1)] or [{}], ["n", "question", "owner", "due", "status"])
    L += ["", "## 14. Approval", ""]
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
