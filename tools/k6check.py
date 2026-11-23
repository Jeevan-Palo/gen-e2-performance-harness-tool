#!/usr/bin/env python3
"""Check a generated k6 script against the BRD and the API catalogue.
Usage: python tools/k6check.py <project_dir>
Expects in <project_dir>: brd.yaml, api-catalogue.yaml, k6/script.js, k6/requirement-map.yaml
requirement-map.yaml: a list of {requirement: PR-01, k6_metric: "transaction_duration{transaction:T2}", threshold: "p(95)<2000"}
(one requirement may appear several times, e.g. once per transaction)
Runs `k6 inspect` too if k6 is installed. Requires PyYAML.
"""
import sys, os, re, shutil, subprocess, yaml
import brd as brdtool

SECRETS = [re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]{20,}"), re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
           re.compile(r"(?i)(password|passwd|secret|api[_-]?key)['\"]?\s*[:=]\s*['\"][^'\"\s]{4,}['\"]")]

def num_ms(target):
    m = re.search(r"([\d.,]+)\s*(ms|s|sec|seconds?)\b", str(target), re.I)
    if not m: return None
    v = float(m.group(1).replace(",", ""))
    return v if m.group(2).lower() == "ms" else v * 1000

def expected(req):
    metric = str(req.get("metric", "")).lower(); tgt = str(req.get("target", "")); pct = str(req.get("percentile", "")).lower()
    if "response" in metric:
        ms, p = num_ms(tgt), re.search(r"p?(\d{2}(?:\.\d+)?)", pct)
        if ms is not None and p: return re.compile(rf"^p\({re.escape(p.group(1))}\)\s*<=?\s*{ms:g}$")
    if "error" in metric:
        m = re.search(r"([\d.]+)\s*%", tgt)
        if m: return re.compile(rf"^rate\s*<=?\s*{float(m.group(1))/100:g}$")
    return None

def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    d = sys.argv[1]; P, W = [], []
    paths = {k: os.path.join(d, v) for k, v in {"brd": "brd.yaml", "cat": "api-catalogue.yaml", "script": "k6/script.js", "map": "k6/requirement-map.yaml"}.items()}
    for k, p in paths.items():
        if not os.path.exists(p): P.append(f"Missing file: {p}")
    if P:
        print(f"ISSUES to fix ({len(P)}):"); [print(f"  {i}. {x}") for i, x in enumerate(P, 1)]; sys.exit(1)
    brd = yaml.safe_load(open(paths["brd"], encoding="utf-8")) or {}
    cat = yaml.safe_load(open(paths["cat"], encoding="utf-8")) or {}
    rmap = yaml.safe_load(open(paths["map"], encoding="utf-8")) or []
    text = open(paths["script"], encoding="utf-8").read()
    code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))

    if "__ENV.BASE_URL" not in code: P.append("Script must read the target from __ENV.BASE_URL")
    if re.search(r"https?://", code): P.append("Script contains a literal URL; use __ENV.BASE_URL")
    for rx in SECRETS:
        if rx.search(code): P.append("Script appears to contain a secret or credential; use __ENV")
    if "abortOnFail" not in code: P.append("No abortOnFail thresholds: abort conditions from the BRD are not implemented")
    if not re.search(r"blocked_responses\s*:", code): P.append("No threshold on blocked_responses (429/503/CDN block should abort the run)")
    if not re.search(r"MAX_VUS\s*=", code): P.append("No MAX_VUS cap defined")
    elif not re.search(r"Math\.min\(", code): W.append("MAX_VUS is not capped with Math.min(...); the environment could raise it")
    if "BASE_URL" in code and "PROFILE" not in code: P.append("No smoke/load PROFILE switch; a smoke run must be possible before a load run")
    if "FLOW_IDS" not in code or "FLOW_IDS.includes" not in code:
        P.append("Script must select the configured per-profile flow IDs from __ENV.FLOWS")

    profile_names = {"baseline": "Baseline", "load": "Load", "stress": "Stress", "spike": "Spike", "endurance": "Endurance"}
    for profile in (brd.get("test_types") or []):
        if not isinstance(profile, dict) or str(profile.get("needed", "")).lower() not in ("yes", "true"):
            continue
        key = brdtool.profile_key(profile.get("type"))
        if key in profile_names and f"PROFILE === '{key}'" not in code:
            P.append(f"BRD profile {profile_names[key]} is needed but has no scenario in the script")
        params = profile.get("parameters") or {}
        flows = params.get("flows") or []
        if key in profile_names and (not isinstance(flows, list) or not flows):
            P.append(f"BRD profile {profile_names[key]} must select at least one flow")
        elif isinstance(flows, list):
            known_flows = {str(f.get("transaction")) for f in (cat.get("flows") or [])
                           if isinstance(f, dict) and f.get("transaction")}
            for flow in flows:
                if str(flow) not in known_flows:
                    P.append(f"BRD profile {profile_names.get(key, key)} selects unknown flow '{flow}'")
    if any(brdtool.profile_key(p.get("type")) in ("stress", "spike")
           and str(p.get("needed", "")).lower() in ("yes", "true")
           for p in (brd.get("test_types") or []) if isinstance(p, dict)):
        if "abortOnFail" not in code or "blocked_responses" not in code:
            P.append("Stress and spike profiles must retain abort and blocked-response thresholds")

    active_tx = {t.get("id") for t in (brd.get("transactions") or []) if t.get("id")}
    ids = {a["id"] for a in cat.get("apis", []) if a.get("transaction") in active_tx}
    flow_ids = {s for f in (cat.get("flows") or []) if f.get("transaction") in active_tx for s in (f.get("steps") or []) + (f.get("parallel") or [])}
    for i in sorted(ids | flow_ids):
        if not re.search(rf"['\"]{re.escape(i)}['\"]", code): P.append(f"Catalogue API {i} is not called in the script (no tag api: '{i}')")
    for t in sorted(active_tx):
        if not re.search(rf"transaction\s*:\s*['\"]{re.escape(t)}['\"]", code): P.append(f"Transaction {t} has no tagged requests in the script")
    for a in cat.get("apis", []):
        if a.get("transaction") in active_tx and a.get("safe_to_load") in ("no", "conditional") and re.search(rf"['\"]{a['id']}['\"]", code):
            P.append(f"{a['id']} is safe_to_load={a.get('safe_to_load')} but the script calls it")

    reqs = [r for r in (brd.get("requirements") or []) if r.get("id") and r.get("metric") and "deferred" not in str(r.get("notes", "")).lower()]
    mapped = {}
    for m in rmap:
        if isinstance(m, dict): mapped.setdefault(m.get("requirement"), []).append(m)
    for r in reqs:
        entries = mapped.get(r["id"])
        if not entries: P.append(f"Requirement {r['id']} has no entry in k6/requirement-map.yaml"); continue
        exp = expected(r)
        if exp is None: W.append(f"{r['id']}: target not machine-checked ({r.get('metric')} {r.get('target')} {r.get('percentile')})")
        for m in entries:  # a requirement may map to several metrics, e.g. one per transaction
            metric, thr = str(m.get("k6_metric", "")), str(m.get("threshold", ""))
            if not metric or metric not in code: P.append(f"{r['id']}: k6_metric '{metric}' not found in the script")
            elif thr not in code: P.append(f"{r['id']}: threshold '{thr}' not found in the script")
            if exp is not None and not exp.match(thr.replace(" ", "")): P.append(f"{r['id']}: BRD says {r.get('target')} {r.get('percentile')} but map threshold is '{thr}'")
    for k in mapped:
        if k not in {r['id'] for r in reqs}: W.append(f"requirement-map has {k}, which is not an active BRD requirement")

    k6 = shutil.which("k6") or os.environ.get("K6_BIN")
    if k6:
        r = subprocess.run([k6, "inspect", paths["script"], "-e", "BASE_URL=http://localhost"], capture_output=True, text=True)
        if r.returncode != 0: P.append("k6 inspect failed: " + (r.stderr or r.stdout).strip().splitlines()[-1][:200])
    else: W.append("k6 not installed here, so the script was not parsed (install with: brew install k6)")

    if P: print(f"ISSUES to fix ({len(P)}):"); [print(f"  {i}. {x}") for i, x in enumerate(P, 1)]
    if W: print(f"Warnings ({len(W)}):"); [print(f"  - {x}") for x in W]
    if not P: print("OK: script matches the BRD and catalogue.")
    sys.exit(1 if P else 0)

if __name__ == "__main__": main()
