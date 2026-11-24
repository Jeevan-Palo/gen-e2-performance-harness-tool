#!/usr/bin/env python3
"""BRD helper. Usage:
  python tools/brd.py check     <brd.yaml>  list missing must-have parameters (exit 1 if any)
  python tools/brd.py questions <brd.yaml>  list business questions for the client (with copy-paste examples)
  python tools/brd.py advise    <brd.yaml> [--apply] [--skip=key,...]  advised values for technical gaps; --apply writes them
  python tools/brd.py render    <brd.yaml>  write brd.md next to the yaml
  python tools/brd.py provenance <brd.yaml> count values by basis: stated / advised / assumed / not evidenced / open
Requires PyYAML (pip install pyyaml).
"""
import sys, os, re, yaml
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

# Business facts only the client can give. Each example is a realistic answer that can be copied and edited.
QUESTION_MAP = [
    ("purpose", ("purpose",), "purpose", "Why is performance testing needed now?", "Example: Black Friday sale on 28 Nov is expected to triple traffic; checkout slowed down during last year's sale"),
    ("scope_in", ("scope_in",), "scope", "Which applications and user journeys are in scope?", "Example: Web shop (www.shop.com): login, search, product page, add to cart, checkout. Out of scope: admin portal"),
    ("peak_load", ("workload", "peak_concurrent_users"), "peak concurrent", "How many users use the system at the busiest time?", "Example: 800 users online at the same time in the busiest hour (Google Analytics, Black Friday 2025). If unknown, say 'unknown' and we advise a value"),
    ("target", ("environment", "target"), "target environment", "Which environment will be tested?", "Example: UAT, https://uat.shop.com (a copy of production, not used by real customers)"),
    ("owner", ("environment", "owner"), "environment owner", "Who owns the target environment?", "Example: Priya Nair, Platform Lead, Infra team"),
    ("client", ("meta", "client"), "client name", "What is the client or business unit name?", "Example: Acme Retail"),
    ("application", ("meta", "application"), "application name", "What is the application or system name?", "Example: Acme Web Shop"),
    ("transaction", ("transactions", "name"), "business transaction", "Which business transactions are in scope?", "Example: T1 Login, T2 Search product, T3 Add to cart, T4 Checkout (all by registered customers)"),
    ("authorisation", ("environment", "_auth_status"), "authorisation", "Who authorises load testing in the active environment?", "Example: Approved by Priya Nair (environment owner) by email on 20 Nov 2026; only the human may decide"),
]

# Technical parameters clients rarely know. The test lead advises these (industry practice); the user accepts them once.
ADVICE = {
    "peak_window": ("workload.peak_window", "Busiest business hour; tested as 5 min ramp-up, 20 min steady load, 5 min ramp-down"),
    "think_time": ("workload.think_time", "5 seconds between user actions"),
    "basis": ("workload.basis", "assumed"),
    "traffic_share": ("transactions[].traffic_share", "Equal split across the listed transactions"),
    "measurement_point": ("transactions[].measure_start_end", "From the user action (click or page request) until the next page is fully loaded"),
    "requirement": ("requirements", "p95 <= 3 s per transaction and error rate <= 1% at peak load"),
    "test_types": ("test_types", "Baseline (single user) and Load: yes; Stress, Spike, Endurance, Scalability: no"),
    "abort": ("abort_conditions", "Stop if error rate > 5% for 2 min, p95 > 10 s for 2 min, or any 429/503/WAF block"),
    "personal_data": ("environment.personal_data_confirmation", "Yes: only synthetic test data is used; no real personal or payment data"),
    "test_data": ("environments.yaml test_data", "Synthetic test accounts and standard catalogue products; data reset between runs"),
    "test_windows": ("environments.yaml test_windows", "Weekdays 10:00-16:00 client local time, outside releases and batch jobs"),
    "monitoring": ("environments.yaml monitoring", "none: client-side k6 metrics only; server CPU and memory added when APM access is granted"),
    "peak_load": ("workload.peak_concurrent_users", "Up to the environment limit ({cap} concurrent users), stepped; real peak to be confirmed from analytics"),
}
ADVISE_TEXT = {"peak window": "peak_window", "think time": "think_time", "workload basis": "basis", "traffic share": "traffic_share",
               "start/end": "measurement_point", "measurable performance requirement": "requirement", "test types": "test_types",
               "abort": "abort", "personal/payment": "personal_data", "test data": "test_data", "test windows": "test_windows",
               "monitoring access": "monitoring"}

def unresolved_open_items(d):
    return [" ".join(str(v) for v in r.values()).lower()
            for r in (d.get("open_items") or []) if isinstance(r, dict)
            and str(r.get("status", "")).strip().lower() == "open"]

def category(label):
    low = str(label).lower()
    if low.startswith("requirement ") and any(k in low for k in (": target", ": percentile", ": load condition")): return "requirement"
    for key, cat in [("purpose", "purpose"), ("in-scope", "scope_in"), ("peak load", "peak_load"), ("target environment", "target"),
                     ("environment owner", "owner"), ("business transaction", "transaction"), ("authorisation", "authorisation")]:
        if key in low: return cat
    if low.startswith("client name"): return "client"
    if low.startswith("application name"): return "application"
    for key, cat in ADVISE_TEXT.items():
        if key in low: return cat
    return None

def questions(d):
    """Questions for business facts that are still missing (advised parameters are not asked; see advise)."""
    cats = {category(x) for x in check(d)}
    open_text = unresolved_open_items(d)
    return [{"field": ".".join(path), "question": prompt, "format": example}
            for cat, path, open_hint, prompt, example in QUESTION_MAP
            if cat in cats and not any(open_hint in text for text in open_text)]

def advice(d, cap=None):
    """Advised values for missing technical parameters. Peak load is advised only after the client said it is unknown (open item)."""
    cats = {category(x) for x in check(d)}
    out = [{"key": k, "field": ADVICE[k][0], "value": ADVICE[k][1]} for k in ADVICE if k in cats and k != "peak_load"]
    if "peak_load" in cats and cap and any("peak" in x and ("concurrent" in x or "load" in x or "users" in x) for x in unresolved_open_items(d)):
        out.append({"key": "peak_load", "field": ADVICE["peak_load"][0], "value": ADVICE["peak_load"][1].format(cap=cap)})
    return out

def apply_advice(path, items, today):
    """Write accepted advice into brd.yaml (and environment fields into environments.yaml), with evidence and one Assumption risk."""
    folder = os.path.dirname(os.path.abspath(path))
    raw = yaml.safe_load(open(path, encoding="utf-8")) or {}
    src = f"advised by test lead (industry practice), accepted by user {today}"
    ev = raw.setdefault("evidence", []) if isinstance(raw.get("evidence"), list) else raw.__setitem__("evidence", []) or raw["evidence"]
    env_updates = {}
    def setp(keys, value):
        cur = raw
        for k in keys[:-1]: cur = cur.setdefault(k, {}) if isinstance(cur.get(k), dict) else cur.__setitem__(k, {}) or cur[k]
        cur[keys[-1]] = value; ev.append({"field": ".".join(keys), "source": src})
    for it in items:
        k = it["key"]
        if k in ("peak_window", "think_time", "basis", "peak_load"):
            setp(["workload", {"peak_window": "peak_window", "think_time": "think_time", "basis": "basis", "peak_load": "peak_concurrent_users"}[k]], it["value"])
        elif k == "personal_data": setp(["environment", "personal_data_confirmation"], it["value"])
        elif k in ("traffic_share", "measurement_point"):
            tx = rows(raw.get("transactions"), ["name"]); n = len(tx) or 1
            for i, tr in enumerate(tx):
                if k == "traffic_share" and blank(tr.get("traffic_share")):
                    tr["traffic_share"] = f"{100 // n + (1 if i < 100 % n else 0)}%"; ev.append({"field": f"transactions.{tr.get('id')}.traffic_share", "source": src})
                if k == "measurement_point" and blank(tr.get("measure_start_end")):
                    tr["measure_start_end"] = it["value"]; ev.append({"field": f"transactions.{tr.get('id')}.measure_start_end", "source": src})
        elif k == "requirement":
            rq = rows(raw.get("requirements"), ["metric", "target"])
            if not rq:
                tx = rows(raw.get("transactions"), ["name"])
                rq = [{"id": f"PR-{i:02d}", "transaction": t.get("id"), "metric": "Response time", "target": "<= 3 s", "percentile": "p95", "load_condition": "peak load", "priority": "Must"} for i, t in enumerate(tx, 1)]
                rq.append({"id": f"PR-{len(rq) + 1:02d}", "transaction": "All", "metric": "Error rate", "target": "<= 1%", "percentile": "n/a", "load_condition": "peak load", "priority": "Must"})
                raw["requirements"] = rq; ev.append({"field": "requirements", "source": src})
            for r in rq:
                for f, val in (("target", "<= 1%" if "error" in str(r.get("metric", "")).lower() else "<= 3 s"), ("percentile", "p95"), ("load_condition", "peak load")):
                    if blank(r.get(f)) and not (f == "percentile" and str(r.get("metric", "")).lower() in ("error rate", "throughput", "availability")):
                        r[f] = val; ev.append({"field": f"requirements.{r.get('id')}.{f}", "source": src})
        elif k == "test_types":
            tt = [t for t in (raw.get("test_types") or []) if isinstance(t, dict)]
            if not tt: tt = [{"type": x, "needed": "", "notes": ""} for x in ("Baseline (single user)", "Load", "Stress", "Spike", "Endurance (soak)", "Scalability")]
            for t in tt:
                if blank(t.get("needed")): t["needed"] = "yes" if str(t.get("type", "")).lower().startswith(("baseline", "load")) else "no"
            raw["test_types"] = tt; ev.append({"field": "test_types", "source": src})
        elif k == "abort":
            raw["abort_conditions"] = [
                {"condition": "Error rate", "threshold": "> 5% for 2 consecutive minutes", "action": "Stop the test and notify the environment owner"},
                {"condition": "Response time", "threshold": "p95 > 10 s for 2 consecutive minutes", "action": "Stop the test"},
                {"condition": "Throttling or blocking", "threshold": "Any 429, 503 or WAF/CDN block response", "action": "Stop immediately"},
                {"condition": "Request from operations or environment owner", "threshold": "Any stop request", "action": "Stop immediately"}]
            ev.append({"field": "abort_conditions", "source": src})
        elif k in ("test_data", "test_windows"): env_updates[k] = it["value"]
        elif k == "monitoring": env_updates["monitoring"] = {"source": "none", "detail": it["value"].split(": ", 1)[-1]}
    if items:
        raw.setdefault("risks", []).append({"type": "Assumption", "description": "Advised values accepted by the user in place of client figures: " + ", ".join(i["field"] for i in items) + ".",
                                            "owner": "Test lead", "impact": "Results show behaviour under advised settings; confirm with the client before sign-off"})
    with open(path, "w", encoding="utf-8") as f: yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True, width=200)
    if env_updates:
        cfg = envconf.load(folder) or {}; e = (cfg.get("environments") or {}).get(cfg.get("active"))
        if e is not None:
            e.update(env_updates)
            with open(envconf.path(folder), "w", encoding="utf-8") as f: yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True, width=200)

# Basis of each value, worked out from `evidence`. Weakest basis comes last so a row built from several values shows the weakest.
BASES = ("Stated", "Advised", "Assumed", "Not evidenced", "Open")
ENV_FIELDS = ("target", "owner", "comparison_with_production", "third_party_services", "test_data", "monitoring_access", "test_windows", "authorisation")

def _basis_of(source):
    s = str(source).lower()
    if "advised" in s: return "Advised"
    if any(w in s for w in ("assum", "proposed", "sample")): return "Assumed"
    return "Stated"

def _evidence_rank(field, path):
    """3 exact, 2 row range such as 'transactions.T1-T4 traffic_share', 1 ancestor such as 'transactions'; 0 no match."""
    m = re.match(r"[\w.\-\[\]]+", str(field).strip())
    if not m: return 0
    head, rest = m.group(0), str(field).strip()[m.end():].strip()
    if head == path: return 3
    if path.startswith(head + "."): return 1
    hp, pp = head.split("."), path.split(".")
    for i in range(1, min(len(hp), len(pp))):
        if hp[:i] != pp[:i]: break
        r = re.fullmatch(r"([A-Za-z]+-?)(\d+)-(?:[A-Za-z]+-?)?(\d+)", hp[i]) if len(hp) == i + 1 else None
        q = re.fullmatch(r"([A-Za-z]+-?)(\d+)", pp[i])
        if r and q and q.group(1) == r.group(1) and int(r.group(2)) <= int(q.group(2)) <= int(r.group(3)) and (not rest or pp[-1] == rest):
            return 2
    return 0

def _lookup(ev, path, env_name):
    best = None
    for e in ev:
        r = _evidence_rank(e.get("field", ""), path)
        if r and (best is None or r >= best[0]): best = (r, e)
    field = path.split(".")[-1]
    if path.startswith("environment.") and env_name and field in ENV_FIELDS and not (best and best[0] == 3):
        return "Stated", f"environments.yaml ({env_name})"
    if best: return _basis_of(best[1].get("source", "")), str(best[1].get("source", "")).strip()
    return "Not evidenced", ""

def provenance(d):
    """One row per value a client must confirm: section, item, value, basis (Stated/Advised/Assumed/Not evidenced/Open/Optional), source."""
    ev = [e for e in (d.get("evidence") or []) if isinstance(e, dict)]
    env_name = (d.get("environment") or {}).get("_env_name")
    out = []
    def add(section, item, value, paths, required=True):
        if blank(value):
            out.append({"section": section, "item": item, "value": "", "basis": "Open" if required else "Optional", "source": ""}); return
        found = [_lookup(ev, p, env_name) for p in paths]
        basis, source = max(found, key=lambda x: BASES.index(x[0]))
        out.append({"section": section, "item": item, "value": str(value), "basis": basis, "source": source})
    m, w, e, mr = (d.get(k) or {} for k in ("meta", "workload", "environment", "monitoring_reporting"))
    add("1. Purpose and background", "Purpose", d.get("purpose"), ["purpose"])
    for i, o in enumerate(d.get("objectives") or [], 1): add("2. Objectives and scope", f"Objective {i}", o, ["objectives"])
    for i, o in enumerate(d.get("scope_in") or [], 1): add("2. Objectives and scope", f"In scope {i}", o, ["scope_in"])
    if blank(d.get("scope_in")): add("2. Objectives and scope", "In scope", "", [])
    for i, o in enumerate(d.get("scope_out") or [], 1): add("2. Objectives and scope", f"Out of scope {i}", o, ["scope_out"])
    for r in (d.get("stakeholders") or []):
        if isinstance(r, dict): add("3. Stakeholders", r.get("role", ""), r.get("name"), ["stakeholders"], False)
    for i, t in enumerate(rows(d.get("transactions"), ["name"]), 1):
        tid = t.get("id") or f"T{i}"; base = f"transactions.{tid}"
        add("4. Business transactions", f"{tid} {t.get('name')}", t.get("name"), [base + ".name"])
        add("4. Business transactions", f"{tid} share of traffic", t.get("traffic_share"), [base + ".traffic_share"])
        add("4. Business transactions", f"{tid} response-time start/end", t.get("measure_start_end"), [base + ".measure_start_end"])
    if not rows(d.get("transactions"), ["name"]): add("4. Business transactions", "Transactions", "", [])
    one_load = blank(w.get("peak_concurrent_users")) != blank(w.get("peak_tps"))
    for lab, k, req in [("Peak concurrent users", "peak_concurrent_users", not one_load), ("Peak requests or transactions per second", "peak_tps", not one_load),
                        ("Peak window and duration", "peak_window", True), ("Average daily volume", "avg_daily_volume", False),
                        ("Expected growth over 12 months", "growth_12m", False), ("User think time and pacing", "think_time", True),
                        ("Geographic distribution of users", "geography", False), ("Data volumes in the system", "data_volumes", False),
                        ("Basis of figures", "basis", True)]:
        add("5. Workload model", lab, w.get(k), ["workload." + k], req)
    for i, r in enumerate(rows(d.get("requirements"), ["metric", "target"]), 1):
        rid = r.get("id") or f"PR-{i:02d}"; base = f"requirements.{rid}"
        txt = ", ".join(str(r[k]) for k in ("metric", "percentile", "target", "load_condition") if not blank(r.get(k)))
        gap = blank(r.get("target")) or blank(r.get("load_condition"))
        add("6. Performance requirements", f"{rid} ({r.get('transaction') or 'all'})", "" if gap else txt, [base + "." + k for k in ("target", "percentile", "load_condition")])
    if not rows(d.get("requirements"), ["metric", "target"]): add("6. Performance requirements", "Requirements", "", [])
    for t in (d.get("test_types") or []):
        if isinstance(t, dict): add("7. Test types", t.get("type", ""), t.get("needed"), ["test_types"])
    for lab, k, req in [("Target environment", "target", True), ("Environment owner", "owner", True), ("Authorisation to test", "authorisation", False),
                        ("Comparison with production", "comparison_with_production", False), ("Third-party services", "third_party_services", False),
                        ("Test data needs", "test_data", True), ("No real personal or payment data", "personal_data_confirmation", True),
                        ("Monitoring access", "monitoring_access", True), ("Allowed test windows", "test_windows", True)]:
        add("8. Test environment and data", lab, e.get(k), ["environment." + k], req)
    for a in (d.get("abort_conditions") or []):
        if isinstance(a, dict):
            ok = not blank(a.get("threshold")) and not blank(a.get("action"))
            add("9. Stop (abort) conditions", a.get("condition", ""), f"{a.get('threshold')}; {a.get('action')}" if ok else "", ["abort_conditions"])
    for lab, k in [("Metrics collected", "metrics"), ("Tools", "tools"), ("Interim updates", "interim_updates"), ("Final report", "final_report")]:
        add("10. Monitoring and reporting", lab, mr.get(k), ["monitoring_reporting." + k], False)
    for i, c in enumerate(d.get("exit_criteria") or [], 1): add("12. Acceptance and exit criteria", f"Criterion {i}", c, ["exit_criteria"])
    return out

def provenance_counts(rows_):
    return {b: sum(1 for r in rows_ if r["basis"] == b) for b in BASES}

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
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "render", "questions", "advise", "provenance"):
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
    elif sys.argv[1] == "provenance":
        pr = provenance(d); c = provenance_counts(pr)
        print(f"{len(pr) - sum(1 for r in pr if r['basis'] == 'Optional')} values | " + " | ".join(f"{b} {c[b]}" for b in BASES))
        for r in pr:
            if r["basis"] in ("Not evidenced", "Open"): print(f"  {r['basis'].upper()}: {r['section']} / {r['item']}")
    elif sys.argv[1] == "advise":
        _, e = envconf.get_env(os.path.dirname(os.path.abspath(path)))
        items = advice(d, (e or {}).get("max_vus"))
        skip = {x for a in sys.argv[3:] if a.startswith("--skip=") for x in a[7:].split(",")}
        items = [i for i in items if i["key"] not in skip]
        if not items: print("NO ADVICE NEEDED: no advisable parameter is missing."); return
        if "--apply" in sys.argv:
            import datetime
            apply_advice(path, items, datetime.date.today().isoformat())
            print(f"APPLIED {len(items)} advised value(s) with evidence and one Assumption risk: " + ", ".join(i["key"] for i in items))
        else:
            print(f"ADVISED VALUES ({len(items)}); accept all with --apply, or leave some out with --skip=key1,key2:")
            for i in items: print(f"  {i['key']:<18} {i['field']:<40} {i['value']}")
    elif sys.argv[1] == "questions":
        items = questions(d)
        if not items:
            print("NO QUESTIONS: all must-have parameters are present or already marked open.")
        else:
            print(f"QUESTIONS ({len(items)}):")
            for i, item in enumerate(items, 1):
                print(f"{i}. field={item['field']} | {item['question']} | {item['format']}")
    else:
        out = os.path.join(os.path.dirname(os.path.abspath(path)), "brd.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(render(d))
        print("Wrote", out)

if __name__ == "__main__":
    main()
