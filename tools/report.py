#!/usr/bin/env python3
"""Build the HTML performance execution report for one run.
Usage: python tools/report.py <project_dir> [--run RUN_ID]
Reads: brd.yaml, environments.yaml, k6/requirement-map.yaml, runs/<run-id>/{run.json,summary.json,k6-output.txt}
Writes: runs/<run-id>/report.html (self-contained; open in a browser, print to PDF from there).
Every figure is read from the k6 files; nothing is typed in by hand. Requires PyYAML.
"""
import sys, os, re, json, html, hashlib, argparse, datetime, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf

esc = lambda x: html.escape(str(x if x is not None else ""))
def blank(v): return v is None or v == "" or v == [] or v == {}
def ms(v): return f"{v:,.0f} ms" if v >= 10 else f"{v:,.1f} ms"
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] if os.path.exists(p) else "missing"

def pick_run(d, run_id, env_name):
    rd = os.path.join(d, "runs")
    if not os.path.isdir(rd): sys.exit("No runs/ folder yet. Run a test first with tools/runk6.py.")
    runs = []
    for r in sorted(os.listdir(rd)):
        f = os.path.join(rd, r, "run.json")
        if os.path.exists(f): runs.append((r, json.load(open(f))))
    if run_id:
        for r, j in runs:
            if r == run_id: return r, j
        sys.exit(f"Run '{run_id}' not found.")
    loads = [x for x in runs if x[1].get("profile") == "load" and x[1].get("env") == env_name] or [x for x in runs if x[1].get("profile") == "load"] or runs
    if not loads: sys.exit("No recorded runs found.")
    return loads[-1]

THR = re.compile(r"(p\(\d+(?:\.\d+)?\)|rate|avg|med|max|min)(<=|<)([\d.]+)")
def parse_thr(t):
    m = THR.fullmatch(str(t).replace(" ", ""))
    return (m.group(1), m.group(2), float(m.group(3))) if m else None

def evaluate(reqs, rmap, metrics, run, peak):
    out = []
    by = {}
    for m in rmap or []:
        if isinstance(m, dict): by.setdefault(m.get("requirement"), []).append(m)
    for r in reqs:
        res = {"r": r, "status": "", "measured": "", "evidence": "", "note": ""}
        if "deferred" in str(r.get("notes", "")).lower():
            res.update(status="Deferred", note=r.get("notes", "")); out.append(res); continue
        entries = by.get(r["id"])
        if not entries: res.update(status="Not measured", note=("Resource requirements are shown in the server resources section but not judged automatically yet." if re.search(r"cpu|memory|resource", str(r.get("metric", "")), re.I) else "No k6 metric is mapped to this requirement.")); out.append(res); continue
        vals, ok_all, evid, missing = [], True, [], False
        for e in entries:
            met = metrics.get(e.get("k6_metric")); p = parse_thr(e.get("threshold", ""))
            if met is None or p is None: missing = True; continue
            stat, op, lim = p
            v = met.get("value") if stat == "rate" else met.get(stat)
            if v is None: missing = True; continue
            ok = v < lim if op == "<" else v <= lim
            ok_all &= ok; vals.append((v, stat, lim, e["k6_metric"], ok))
            evid.append(f"{e['k6_metric']}  {e['threshold']}  measured {v:.4g}")
        if missing or not vals: res.update(status="Not measured", note="The mapped k6 metric has no data in this run."); out.append(res); continue
        def show(v, stat): return f"{v*100:.2f}%" if stat == "rate" else ms(v)
        parts = []
        for m in vals:
            tg = re.search(r"transaction:(\w+)", m[3])
            parts.append((tg.group(1) + ": " if tg and len(vals) > 1 else "") + show(m[0], m[1]))
        shown = "; ".join(parts)
        res["evidence"] = "<br>".join(esc(x) for x in evid)
        below_peak = run.get("profile") != "load" or (peak and run.get("vus", 0) < peak)
        if below_peak:
            res.update(status="Not measured at peak load", measured=shown,
                       note=f"Indicative only: {'within' if ok_all else 'outside'} the target at {run.get('vus')} user(s); the requirement applies at {peak or 'peak'} users.")
        else:
            res.update(status="Met" if ok_all else "Not met", measured=shown)
        out.append(res)
    return out


PAL = ["#2a6f97", "#d1495b", "#edae49", "#00798c", "#66a182", "#8d6a9f"]
def line_chart(samples, key, unit, names, tmax, band):
    W, L, R, T, B = 760, 56, 12, 10, 28
    H = 190
    vals = [s[key] for s in samples if s.get(key) is not None]
    if not vals: return ""
    top = max(vals) * 1.15 or 1
    x = lambda t: L + (W - L - R) * t / (tmax or 1); y = lambda v: T + (H - T - B) * (1 - v / top)
    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="{esc(unit)} over time">']
    if band: s.append(f'<rect x="{x(band[0]):.1f}" y="{T}" width="{max(x(band[1])-x(band[0]),1):.1f}" height="{H-T-B}" fill="#2a6f97" opacity="0.07"/>')
    for g in (0, 0.5, 1):
        s.append(f'<line x1="{L}" x2="{W-R}" y1="{y(top*g):.1f}" y2="{y(top*g):.1f}" stroke="#dde3ea"/><text x="{L-6}" y="{y(top*g)+4:.1f}" text-anchor="end" class="ax">{top*g:.0f}</text>')
    s.append(f'<text x="{L}" y="{H-8}" class="ax">0 s</text><text x="{W-R}" y="{H-8}" text-anchor="end" class="ax">{tmax:.0f} s</text><text x="{L}" y="{T+2}" class="ax" dy="-1">{esc(unit)}</text>')
    for i, n in enumerate(names):
        pts = [(x(p["t_s"]), y(p[key])) for p in samples if p["series"] == n and p.get(key) is not None]
        if pts: s.append(f'<polyline fill="none" stroke="{PAL[i % len(PAL)]}" stroke-width="2" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>')
    s.append("</svg>")
    s.append("<p class='muted legend'>" + "".join(f'<span class="sw" style="background:{PAL[i % len(PAL)]}"></span>{esc(n)} ' for i, n in enumerate(names)) + ("&nbsp; Shaded: steady-state phase." if band else "") + "</p>")
    return "".join(s)

def monitoring_html(mon, run, env):
    m = env.get("monitoring") or {}
    if mon and mon.get("samples"):
        names = sorted({p["series"] for p in mon["samples"]}, key=lambda n: (n.startswith("k6"), n))
        sm = mon.get("summary") or {}
        h = [f"<p>Source: <b>{esc(mon.get('source'))}</b>, sampled about every {esc(mon.get('interval_seconds'))} s while the test ran. CPU % follows Docker: 100% = one full core. Averages and p95 cover the steady phase of the load profile; the maximum covers the whole run.</p>"]
        h.append("<table><tr><th>Component</th><th class='n'>CPU avg</th><th class='n'>CPU p95</th><th class='n'>CPU max</th><th class='n'>Memory avg</th><th class='n'>Memory max</th><th class='n'>Samples</th></tr>")
        f = lambda v, u: f"{v:,.1f} {u}" if v is not None else "&ndash;"
        for n in names:
            r = sm.get(n) or {}
            h.append(f"<tr><td>{esc(n)}</td><td class='n'>{f(r.get('cpu_avg'), '%')}</td><td class='n'>{f(r.get('cpu_p95'), '%')}</td><td class='n'>{f(r.get('cpu_max_run'), '%')}</td><td class='n'>{f(r.get('mem_avg_mib'), 'MiB')}</td><td class='n'>{f(r.get('mem_max_mib'), 'MiB')}</td><td class='n'>{esc(r.get('samples'))}</td></tr>")
        h.append("</table>")
        tmax, band = mon.get("duration_s") or max(p["t_s"] for p in mon["samples"]), mon.get("steady_window_s")
        h.append("<h3>CPU over time</h3>" + line_chart(mon["samples"], "cpu_pct", "CPU %", names, tmax, band))
        h.append("<h3>Memory over time</h3>" + line_chart(mon["samples"], "mem_mib", "Memory MiB", names, tmax, band))
        h.append("<p class='muted'>The load generator (k6) is shown so you can tell whether it, and not the application, was the bottleneck.</p>")
        return "".join(h)
    st = (run.get("monitoring") or {})
    if st.get("status") == "unavailable": return f"<p class='muted'>Configured source <b>{esc(st.get('source'))}</b> could not be collected: {esc(st.get('note'))}</p>"
    if st.get("status") == "not_built": return f"<p class='muted'>{esc(st.get('note'))}. No server-side data was collected.</p>"
    return f"<p class='muted'>Not collected in this run (monitoring source: {esc(m.get('source') or 'none')}). {esc(m.get('detail'))}</p>"

def bar_chart(rows):
    """Bars show how much of each target is used (100% line = the target). Rows without a target are listed in the table only."""
    items = []
    for r in rows:
        for k in ("95", "99"):
            t = r.get("t" + k)
            if t: items.append((f"{r['label']} p{k}", r["p" + k], t))
    if not items: return "<p class='muted'>No targets are mapped to transaction timings, so the table below lists the measured values.</p>"
    W, L, R, H = 760, 80, 230, 30
    h = H * len(items) + 40
    scale = lambda v: (W - L - R) * min(v, 1.5) / 1.5
    s = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="Share of each response-time target used" class="chart">']
    s.append(f'<line x1="{L+scale(1):.1f}" x2="{L+scale(1):.1f}" y1="4" y2="{h-26}" class="tgt"><title>100% = the target</title></line>')
    s.append(f'<text x="{L+scale(1):.1f}" y="{h-10}" text-anchor="middle" class="ax">target (100%)</text><text x="{L}" y="{h-10}" class="ax">0%</text>')
    for i, (lab, v, t) in enumerate(items):
        y = 8 + i * H; frac = v / t; bad = frac > 1
        s.append(f'<text x="{L-10}" y="{y+13}" text-anchor="end" class="lbl">{esc(lab)}</text>')
        s.append(f'<rect x="{L}" y="{y}" width="{max(scale(frac),2):.1f}" height="18" rx="3" class="{"bbad" if bad else "b95"}"/>')
        s.append(f'<text x="{L+max(scale(frac),2)+8:.1f}" y="{y+13}" class="val">{esc(ms(v))} of {esc(ms(t))} ({frac*100:.0f}%)</text>')
    s.append("</svg>")
    s.append("<p class='muted legend'>Each bar shows the measured value as a share of its target. A bar that reaches the dashed line has used the whole target.</p>")
    return "".join(s)

CSS = """
:root{--bg:#fff;--fg:#1d2733;--mut:#5b6877;--line:#dde3ea;--card:#f6f8fb;--ok:#1e7a46;--okbg:#e6f4ec;--warn:#8a5a00;--warnbg:#fff3d6;--bad:#a3262a;--badbg:#fde8e8;--acc:#2a6f97}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1020px;margin:0 auto;padding:32px 24px 60px}h1{font-size:26px;margin:0 0 4px}h3{font-size:15px;margin:18px 0 6px}h2{font-size:18px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.muted{color:var(--mut);font-size:13px}.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:16px 0}
.meta div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.meta b{display:block;font-size:12px;color:var(--mut);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.banner{border-radius:10px;padding:14px 16px;margin:18px 0;border:1px solid;font-size:16px}.banner.ok{background:var(--okbg);border-color:var(--ok);color:var(--ok)}.banner.warn{background:var(--warnbg);border-color:var(--warn);color:var(--warn)}.banner.bad{background:var(--badbg);border-color:var(--bad);color:var(--bad)}
.banner small{display:block;color:var(--fg);font-size:14px;margin-top:4px}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:14px}td:first-child{white-space:nowrap}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:var(--card);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}.pill{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}
.pill.met{background:var(--okbg);color:var(--ok)}.pill.notmet{background:var(--badbg);color:var(--bad)}.pill.nm{background:var(--warnbg);color:var(--warn)}.pill.def{background:#e9edf2;color:var(--mut)}
.chart{width:100%;height:auto}.chart .lbl{font-size:13px;fill:var(--fg);font-weight:600}.chart .val{font-size:11px;fill:var(--mut)}.chart .ax{font-size:11px;fill:var(--mut)}.chart .b95{fill:#2a6f97}.chart .b99{fill:#7fb3cf}.chart .tgt{stroke:#a3262a;stroke-width:2;stroke-dasharray:3 2}.chart .bbad{fill:#a3262a}
.legend .sw{display:inline-block;width:11px;height:11px;border-radius:2px;margin:0 4px 0 12px;vertical-align:-1px}.sw.b95{background:#2a6f97}.sw.b99{background:#7fb3cf}.sw.tg{background:#a3262a}
ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}details{margin:8px 0}summary{cursor:pointer;color:var(--acc);font-weight:600}code{font:12px ui-monospace,Menlo,Consolas,monospace;background:var(--card);padding:1px 5px;border-radius:4px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.kpis div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.kpis b{display:block;font-size:20px}.kpis span{font-size:12px;color:var(--mut)}
a{color:var(--acc)}footer{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
@media print{main{padding:0}details{display:block}details>summary{display:none}h2{break-after:avoid}table,.kpis{break-inside:avoid}}
"""

def build(d, run_id=None):
    """Compute everything for one run. Returns (report_html, facts). Writes nothing."""
    d = d.rstrip("/")
    brd = yaml.safe_load(open(os.path.join(d, "brd.yaml"), encoding="utf-8")) or {}
    cfg = envconf.load(d) or {}
    rid, run = pick_run(d, run_id, cfg.get("active"))
    rdir = os.path.join(d, "runs", rid)
    summ = json.load(open(os.path.join(rdir, "summary.json"))); M = summ["metrics"]
    env = (cfg.get("environments") or {}).get(run.get("env")) or {}
    rmap_path = os.path.join(d, "k6", "requirement-map.yaml")
    rmap = yaml.safe_load(open(rmap_path, encoding="utf-8")) if os.path.exists(rmap_path) else []
    meta, wl = brd.get("meta") or {}, brd.get("workload") or {}
    pm = re.search(r"\d[\d,]*", str(wl.get("peak_concurrent_users", ""))); peak = int(pm.group(0).replace(",", "")) if pm else 0
    reqs = [r for r in (brd.get("requirements") or []) if r.get("id") and r.get("metric")]
    res = evaluate(reqs, rmap, M, run, peak)
    cnt = lambda s: sum(1 for x in res if x["status"] == s)
    musts = [x for x in res if str(x["r"].get("priority", "")).lower() == "must" and x["status"] != "Deferred"]
    passed_run = run.get("outcome") == "passed"
    if run.get("outcome") == "error":
        errline = ""
        try:
            for ln in open(os.path.join(rdir, "k6-output.txt"), encoding="utf-8", errors="replace"):
                m = re.search(r'level=error msg="(.*?)"( hint|$)', ln.strip())
                if m: errline = m.group(1).replace("\\n", " ").replace("\\t", " ")[:220]; break
        except OSError: pass
        vcls, vtxt, vsub = "bad", "The run failed before it produced results", f"k6 stopped with an error (exit code {run.get('exit_code')}), so no requirement could be judged. " + (f"First error: {errline}. " if errline else "") + "Typical causes: the target was not reachable, or the script could not start. See k6-output.txt in the run folder."
    elif not passed_run: vcls, vtxt, vsub = "bad", f"The run did not pass: {run.get('outcome')}", "A safety rule stopped the run or a threshold was crossed. See the run details below."
    elif cnt("Not met"): vcls, vtxt, vsub = "bad", f"{cnt('Not met')} requirement(s) not met", "At the load level of this run."
    elif cnt("Not measured at peak load"): vcls, vtxt, vsub = "warn", f"The run passed every k6 threshold at {run.get('vus')} user(s), but the requirements apply at {peak} users", f"{cnt('Not measured at peak load')} requirement(s) cannot be judged yet. Their figures are shown as indicative only."
    else: vcls, vtxt, vsub = "ok", "All active requirements were met", f"At {run.get('vus')} concurrent users."
    if cnt("Deferred") and vcls != "bad" or (cnt("Deferred") and run.get("outcome") == "passed"):
        dm = sum(1 for x in res if x["status"] == "Deferred" and str(x["r"].get("priority", "")).lower() == "must")
        vsub += f" {cnt('Deferred')} requirement(s) ({dm} Must) are deferred to a later phase and were not tested."
    # rows for chart / table
    tx_names = {t.get("id"): t.get("name") for t in (brd.get("transactions") or [])}
    share = {t.get("id"): t.get("traffic_share") for t in (brd.get("transactions") or [])}
    targets = {}
    for e in rmap or []:
        m = re.search(r"transaction:(\w+)", str(e.get("k6_metric", ""))); p = parse_thr(e.get("threshold", ""))
        if m and p and p[0].startswith("p("): targets.setdefault(m.group(1), {})["t" + re.search(r"\d+", p[0]).group(0)] = p[2]
    rows = []
    for k, v in M.items():
        m = re.fullmatch(r"transaction_duration\{transaction:(\w+)\}", k)
        if m and "p(95)" in v: rows.append({"id": m.group(1), "label": m.group(1), "p95": v["p(95)"], "p99": v.get("p(99)", v["p(95)"]), **targets.get(m.group(1), {})})
    rows.sort(key=lambda r: r["id"])
    g = lambda k, f="value": (M.get(k) or {}).get(f)
    dash = os.path.exists(os.path.join(rdir, "dashboard.html"))
    mp = os.path.join(rdir, "monitoring.json"); mon = json.load(open(mp)) if os.path.exists(mp) else None
    P = []
    P.append(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Performance test execution report - {esc(meta.get('application'))} - {esc(rid)}</title><style>{CSS}</style></head><body><main>")
    P.append(f"<h1>Performance test execution report</h1><p class='muted'>{esc(meta.get('application'))} &middot; {esc(meta.get('client'))}</p>")
    P.append("<div class='meta'>" + "".join(f"<div><b>{esc(k)}</b>{esc(v)}</div>" for k, v in [
        ("Run", rid), ("Test window (UTC)", f"{run.get('start_utc')} to {run.get('end_utc')}"), ("Load", f"{run.get('vus')} user(s), {run.get('profile')}"),
        ("Profile", f"ramp-up {run.get('ramp_up')}, steady {run.get('steady')}, ramp-down {run.get('ramp_down')}" if run.get("profile") == "load" else "1 user, 1 pass"),
        ("Environment", f"{run.get('env')} ({run.get('env_type')})"), ("Target", run.get("target")), ("BRD", f"v{meta.get('version')} ({meta.get('status')})"), ("Tool", run.get("k6_version", "").split(" (")[0])]) + "</div>")
    P.append(f"<div class='banner {vcls}'><b>{esc(vtxt)}</b><small>{esc(vsub)}</small></div>")
    P.append(f"<h2>1. Requirement results</h2><p class='muted'>Must requirements: {sum(1 for x in musts if x['status']=='Met')} met, {sum(1 for x in musts if x['status']=='Not met')} not met, {sum(1 for x in musts if x['status']=='Not measured at peak load' or x['status']=='Not measured')} not measured. Deferred requirements are outside this phase.</p>")
    cls = {"Met": "met", "Not met": "notmet", "Not measured at peak load": "nm", "Not measured": "nm", "Deferred": "def"}
    P.append("<table><tr><th>ID</th><th>Transaction</th><th>Requirement</th><th>Load condition</th><th>Priority</th><th>Result</th><th>Measured</th></tr>")
    for x in res:
        r = x["r"]
        P.append(f"<tr><td>{esc(r['id'])}</td><td>{esc(r.get('transaction'))}</td><td>{esc(r.get('metric'))} {esc(r.get('target'))}" + (f" at {esc(r.get('percentile'))}" if r.get("percentile") not in (None, "", "n/a") else "") + f"</td><td>{esc(r.get('load_condition'))}</td><td>{esc(r.get('priority'))}</td><td><span class='pill {cls.get(x['status'],'nm')}'>{esc(x['status'])}</span></td><td>{esc(x['measured']) or '&ndash;'}" + (f"<br><span class='muted'>{esc(x['note'])}</span>" if x["note"] else "") + "</td></tr>")
    P.append("</table>")
    P.append("<details><summary>Evidence behind each result</summary><table><tr><th>ID</th><th>k6 metric, threshold and measured value</th></tr>" + "".join(f"<tr><td>{esc(x['r']['id'])}</td><td><code>{x['evidence'] or 'no data'}</code></td></tr>" for x in res if x["status"] != "Deferred") + "</table></details>")
    P.append("<h2>2. Response times per transaction</h2>" + bar_chart(rows))
    P.append("<table><tr><th>Transaction</th><th class='n'>Traffic share</th><th class='n'>Average</th><th class='n'>Median</th><th class='n'>p90</th><th class='n'>p95</th><th class='n'>p99</th><th class='n'>Max</th></tr>")
    for r in rows:
        v = M[f"transaction_duration{{transaction:{r['id']}}}"]
        P.append(f"<tr><td>{esc(r['id'])} {esc(tx_names.get(r['id'],''))}</td><td class='n'>{esc(share.get(r['id'],'&ndash;'))}</td>" + "".join(f"<td class='n'>{esc(ms(v[k])) if k in v else '&ndash;'}</td>" for k in ("avg", "med", "p(90)", "p(95)", "p(99)", "max")) + "</tr>")
    P.append("</table><p class='muted'>A transaction is timed from its first request to the last response, as defined in the BRD. All timings are measured by the load tool (client side).</p>")
    P.append("<h2>3. Load and stability</h2><div class='kpis'>" + "".join(f"<div><b>{esc(b)}</b><span>{esc(s)}</span></div>" for b, s in [
        (f"{g('http_reqs','count'):,}" if g('http_reqs','count') is not None else "n/a", "requests sent"),
        (f"{g('http_reqs','rate'):.1f}/s" if g('http_reqs','rate') is not None else "n/a", "average request rate"),
        (f"{(g('http_req_failed') or 0)*100:.2f}%", "requests failed"),
        (f"{int(g('blocked_responses','count') or 0)}", "blocked or throttled (429/503)"),
        (f"{int(g('iterations','count') or 0):,}", "user journeys completed"),
        (f"{int(g('vus_max') or 0)}", "peak virtual users"),
        (f"{(g('checks') or 0)*100:.1f}%", "checks passed")]) + "</div>")
    mix = ", ".join(f"{k} {v}" for k, v in share.items() if v)
    P.append(f"<p>Traffic mix: {esc(mix) or 'n/a'}. Think time: {esc(wl.get('think_time'))}.</p>")
    P.append("<h2>4. Server resources (CPU and memory)</h2>" + monitoring_html(mon, run, env))
    lim = []
    if run.get("profile") != "load" or (peak and run.get("vus", 0) < peak): lim.append(f"This run used {run.get('vus')} user(s). The requirements apply at {peak or 'peak'} users, so they are reported as not measured at peak load.")
    if re.search(r"localhost|127\.0\.0\.1", str(run.get("target", ""))): lim.append("The load tool and the application ran on the same machine, so they competed for CPU and the timings are not representative of a separate production setup.")
    if not (mon and mon.get("samples")): lim.append("No server-side CPU or memory data was collected.")
    else:
        lim.append("CPU and memory come from Docker's own statistics (sampled every few seconds); treat them as indicative, not exact host usage.")
        k6s = (mon.get("summary") or {}).get("k6 (load generator)") or {}
        if (k6s.get("cpu_max_run") or 0) >= 100: lim.append(f"The load generator (k6) peaked at {k6s['cpu_max_run']:.0f}% CPU (more than one full core); check that the machine had spare cores, or the timings may be affected.")
    if str(wl.get("basis", "")).lower() == "assumed": lim.append("The load model and the targets are assumptions of the test lead, not figures agreed with a business owner.")
    if env.get("verified", {}).get("note"): lim.append("Environment check: " + str(env["verified"]["note"]) + ".")
    P.append("<h2>5. Limitations of this report</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in lim) + "</ul>")
    so = brd.get("scope_out") or []
    if so: P.append("<h2>6. Out of scope in this phase</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in so) + "</ul>")
    oi = [o for o in (brd.get("open_items") or []) if str(o.get("status", "")).lower() == "open" and o.get("question")]
    if oi: P.append("<h2>7. Open items</h2><ul>" + "".join(f"<li>{esc(o['question'])}</li>" for o in oi) + "</ul>")
    ab = brd.get("abort_conditions") or []
    P.append("<h2>8. Safety rules and outcome</h2><p>Run outcome: <b>" + esc(run.get("outcome")) + "</b> (exit code " + esc(run.get("exit_code")) + "). Authorisation to test this environment: <b>" + esc(run.get("authorisation")) + "</b>.</p>" + ("<table><tr><th>Stop condition</th><th>Threshold</th><th>Action</th></tr>" + "".join(f"<tr><td>{esc(x.get('condition'))}</td><td>{esc(x.get('threshold'))}</td><td>{esc(x.get('action'))}</td></tr>" for x in ab) + "</table>" if ab else ""))
    P.append("<h2>9. Evidence files</h2><table><tr><th>File</th><th>SHA-256 (first 16)</th></tr>" + "".join(f"<tr><td><code>runs/{esc(rid)}/{f}</code></td><td><code>{sha(os.path.join(rdir, f))}</code></td></tr>" for f in ("run.json", "summary.json", "k6-output.txt")) + "</table>" + (f"<p>Detailed k6 charts: <a href='dashboard.html'>dashboard.html</a> (open from the same folder).</p>" if dash else "") + f"<details><summary>Command used</summary><p><code>{esc(run.get('command'))}</code></p></details>")
    P.append(f"<footer>Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC by tools/report.py. Figures are read directly from the k6 output files; nothing is edited by hand. Prepared by: {esc(meta.get('prepared_by')) or 'not stated'}.</footer></main></body></html>")
    facts = {"brd": brd, "meta": meta, "run": run, "rid": rid, "rdir": rdir, "res": res, "vcls": vcls, "vtxt": vtxt, "vsub": vsub, "peak": peak,
             "lim": lim, "rows": rows, "share": share, "tx_names": tx_names, "env": env, "mon": mon, "M": M, "dash": dash}
    return "\n".join(P), facts

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--run"); a = ap.parse_args()
    page, f = build(a.project, a.run)
    out = os.path.join(f["rdir"], "report.html"); open(out, "w", encoding="utf-8").write(page); print("Wrote", out)

if __name__ == "__main__": main()
