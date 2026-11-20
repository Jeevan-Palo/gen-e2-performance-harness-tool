#!/usr/bin/env python3
"""Build the client pack: a folder and zip with a cover page, the BRD, every run's report and the evidence.
Usage: python tools/clientpack.py <project_dir> [--run RUN_ID] [--allow-incomplete] [--open]
Output: <project_dir>/client-pack/<app>-<run-id>/ (index.html is the cover) and a .zip next to it. Nothing is sent anywhere.
Refuses to build if the BRD has missing must-have parameters, no passed load run exists, or a secret-like string is found. Requires PyYAML.
"""
import sys, os, re, json, shutil, hashlib, zipfile, argparse, datetime, html, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf, brd as brdtool, report as rep
esc = rep.esc
SECRETS = [re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]{20,}"), re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
           re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)['\"]?\s*[:=]\s*['\"]?(?!<redacted>|\$\{|\{\{|<|\s)[A-Za-z0-9_\-/+=]{8,}")]
sha256 = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
now = lambda: datetime.datetime.now(datetime.timezone.utc)

def md_to_html(md):
    out, lines, i, ol = [], md.splitlines(), 0, False
    cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
    while i < len(lines):
        l = lines[i]
        if ol and not re.match(r"\d+\. ", l): out.append("</ol>"); ol = False
        if l.startswith("# "): out.append(f"<h1>{esc(l[2:])}</h1>")
        elif l.startswith("## "): out.append(f"<h2>{esc(l[3:])}</h2>")
        elif l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"): rows.append(lines[i]); i += 1
            t = ["<table><tr>" + "".join(f"<th>{esc(c)}</th>" for c in cells(rows[0])) + "</tr>"]
            for r in rows[2:]: t.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells(r)) + "</tr>")
            out.append("".join(t) + "</table>"); continue
        elif re.match(r"\d+\. ", l):
            if not ol: out.append("<ol>"); ol = True
            out.append(f"<li>{esc(re.sub(r'^\\d+\\. ', '', l))}</li>")
        elif l.strip(): out.append(f"<p>{esc(l)}</p>")
        i += 1
    if ol: out.append("</ol>")
    return "\n".join(out)

def page(title, body, css_extra=""):
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)}</title><style>{rep.CSS}{css_extra}ol{{margin:6px 0 6px 22px}}</style></head><body><main>{body}</main></body></html>"

def list_runs(d, env_name):
    rd, out = os.path.join(d, "runs"), []
    for r in sorted(os.listdir(rd)) if os.path.isdir(rd) else []:
        f = os.path.join(rd, r, "run.json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("env") == env_name: out.append((r, j))
    return out

def choose(runs, peak, wanted):
    if wanted:
        for r, j in runs:
            if r == wanted: return r, j
        sys.exit(f"Run '{wanted}' not found for the active environment.")
    ok = [x for x in runs if x[1].get("profile") == "load" and x[1].get("outcome") == "passed"]
    if not ok: sys.exit("No passed load run exists for the active environment. Run a load test first.")
    peak_ok = [x for x in ok if peak and x[1].get("vus", 0) >= peak]
    pool = peak_ok or ok
    return sorted(pool, key=lambda x: (x[1].get("vus", 0), x[0]))[-1]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--run"); ap.add_argument("--allow-incomplete", action="store_true"); ap.add_argument("--open", action="store_true")
    a = ap.parse_args(); d = a.project.rstrip("/")
    cfg = envconf.load(d) or {}; active = cfg.get("active")
    raw = yaml.safe_load(open(os.path.join(d, "brd.yaml"), encoding="utf-8")) or {}
    brd = brdtool.apply_env(yaml.safe_load(open(os.path.join(d, "brd.yaml"), encoding="utf-8")) or {}, d)
    missing = brdtool.check(brd)
    if missing and not a.allow_incomplete: sys.exit("The BRD still has missing must-have parameters, so no client pack is built:\n  - " + "\n  - ".join(missing))
    pm = re.search(r"\d[\d,]*", str((brd.get("workload") or {}).get("peak_concurrent_users", ""))); peak = int(pm.group(0).replace(",", "")) if pm else 0
    runs = list_runs(d, active)
    rid, run = choose(runs, peak, a.run)
    page_main, F = rep.build(d, rid)
    meta, res = F["meta"], F["res"]; app = re.sub(r"[^A-Za-z0-9]+", "-", str(meta.get("application", "app"))).strip("-").lower()[:24].strip("-")
    root = os.path.join(d, "client-pack", f"{app}-{rid}")
    if os.path.exists(root): shutil.rmtree(root)
    if os.path.exists(root + ".zip"): os.remove(root + ".zip")   # a failed build must not leave an older zip behind
    os.makedirs(os.path.join(root, "runs"))
    warns = []
    if str(meta.get("status", "")).lower() != "approved": warns.append(f"BRD status is '{meta.get('status')}': the client will see that status.")
    if not meta.get("prepared_by"): warns.append("meta.prepared_by is empty, so the pack says 'not stated'.")
    # per-run folders (reports rebuilt with the current tool so all are consistent)
    hist, excluded = [], 0
    for r, j in runs:
        src = os.path.join(d, "runs", r)
        if not os.path.exists(os.path.join(src, "summary.json")): excluded += 1; continue
        dst = os.path.join(root, "runs", r); os.makedirs(dst)
        for f in ("run.json", "summary.json", "k6-output.txt", "monitoring.json", "dashboard.html"):
            if os.path.exists(os.path.join(src, f)): shutil.copy(os.path.join(src, f), dst)
        pg, f = rep.build(d, r); open(os.path.join(dst, "report.html"), "w", encoding="utf-8").write(pg)
        M = json.load(open(os.path.join(src, "summary.json")))["metrics"]
        hist.append((r, j, M))
    # BRD
    brd_html = page("Business requirements document", "<p><a href='index.html'>&larr; Back to the summary</a></p>" + md_to_html(brdtool.render(brd)))
    open(os.path.join(root, "brd.html"), "w", encoding="utf-8").write(brd_html)
    # cover
    run_, env = F["run"], F["env"]; mon = F["mon"]; M = F["M"]
    fval = lambda k, f="value": (M.get(k) or {}).get(f)
    tx_ids = [r["id"] for r in F["rows"]]
    h = [f"<h1>Performance test results</h1><p class='muted'>{esc(meta.get('application'))} &middot; {esc(meta.get('client'))}</p>"]
    h.append("<div class='meta'>" + "".join(f"<div><b>{esc(k)}</b>{esc(v)}</div>" for k, v in [
        ("Result based on run", rid), ("Test window (UTC)", f"{run_.get('start_utc')} to {run_.get('end_utc')}"), ("Load", f"{run_.get('vus')} concurrent users"),
        ("Environment", f"{run_.get('env')} ({run_.get('env_type')})"), ("BRD", f"v{meta.get('version')} ({meta.get('status')})"),
        ("Prepared by", meta.get("prepared_by") or "not stated"), ("Pack created", now().strftime("%Y-%m-%d %H:%M UTC"))]) + "</div>")
    h.append(f"<div class='banner {F['vcls']}'><b>{esc(F['vtxt'])}</b><small>{esc(F['vsub'])}</small></div>")
    dur = f"ramp-up {run_.get('ramp_up')}, steady {run_.get('steady')}, ramp-down {run_.get('ramp_down')}"
    h.append(f"<h2>Summary</h2><p>The test ran {esc(run_.get('vus'))} concurrent users ({esc(dur)}) against the <b>{esc(run_.get('env'))}</b> environment. It sent {int(fval('http_reqs','count') or 0):,} requests; {(fval('http_req_failed') or 0)*100:.2f}% failed and {int(fval('blocked_responses','count') or 0)} were blocked or throttled. Every figure below is read directly from the load tool's output files.</p>")
    h.append("<h2>Requirement results</h2><table><tr><th>ID</th><th>Requirement</th><th>Priority</th><th>Result</th><th>Measured</th></tr>")
    cls = {"Met": "met", "Not met": "notmet", "Not measured at peak load": "nm", "Not measured": "nm", "Deferred": "def"}
    for x in res:
        r = x["r"]; req = f"{r.get('transaction')}: {r.get('metric')} {r.get('target')}" + (f" at {r.get('percentile')}" if r.get("percentile") not in (None, "", "n/a") else "") + f" (peak load: {peak or 'n/a'} users)"
        h.append(f"<tr><td>{esc(r['id'])}</td><td>{esc(req)}</td><td>{esc(r.get('priority'))}</td><td><span class='pill {cls.get(x['status'],'nm')}'>{esc(x['status'])}</span></td><td>{esc(x['measured']) or '&ndash;'}" + (f"<br><span class='muted'>{esc(x['note'])}</span>" if x['note'] and x['status'] != 'Deferred' else "") + "</td></tr>")
    h.append("</table>")
    h.append("<h2>Response times at this load</h2><table><tr><th>Transaction</th><th class='n'>Share of traffic</th><th class='n'>Average</th><th class='n'>p95</th><th class='n'>p99</th><th class='n'>Max</th></tr>")
    for t in tx_ids:
        v = M[f"transaction_duration{{transaction:{t}}}"]
        h.append(f"<tr><td>{esc(t)} {esc(F['tx_names'].get(t,''))}</td><td class='n'>{esc(F['share'].get(t,''))}</td>" + "".join(f"<td class='n'>{esc(rep.ms(v[k])) if k in v else '&ndash;'}</td>" for k in ("avg", "p(95)", "p(99)", "max")) + "</tr>")
    h.append("</table>")
    h.append("<h2>How the load was stepped up</h2><table><tr><th>Run (UTC start)</th><th class='n'>Users</th><th>Profile</th><th>Outcome</th><th class='n'>Requests</th><th class='n'>Failed</th>" + "".join(f"<th class='n'>{esc(t)} p95</th>" for t in tx_ids) + "<th>Report</th></tr>")
    for r, j, MM in sorted(hist, key=lambda x: x[1].get("start_utc", "")):
        h.append(f"<tr><td>{esc(j.get('start_utc'))}</td><td class='n'>{esc(j.get('vus'))}</td><td>{esc(j.get('profile'))}</td><td>{esc(j.get('outcome'))}</td><td class='n'>{int((MM.get('http_reqs') or {}).get('count') or 0):,}</td><td class='n'>{((MM.get('http_req_failed') or {}).get('value') or 0)*100:.2f}%</td>" + "".join(f"<td class='n'>{esc(rep.ms(MM[f'transaction_duration{{transaction:{t}}}']['p(95)'])) if f'transaction_duration{{transaction:{t}}}' in MM else '&ndash;'}</td>" for t in tx_ids) + f"<td><a href='runs/{esc(r)}/report.html'>open</a></td></tr>")
    h.append("</table>" + (f"<p class='muted'>{excluded} run(s) that failed before producing results are not listed.</p>" if excluded else ""))
    if mon and mon.get("samples"):
        h.append("<h2>Server resources during the selected run</h2><p class='muted'>CPU % follows Docker: 100% = one full core. Averages cover the steady phase.</p><table><tr><th>Component</th><th class='n'>CPU avg</th><th class='n'>CPU p95</th><th class='n'>CPU max</th><th class='n'>Memory avg</th><th class='n'>Memory max</th></tr>")
        for n, v in sorted((mon.get("summary") or {}).items(), key=lambda kv: (kv[0].startswith("k6"), kv[0])):
            f1 = lambda x, u: f"{x:,.1f} {u}" if x is not None else "&ndash;"
            h.append(f"<tr><td>{esc(n)}</td><td class='n'>{f1(v.get('cpu_avg'),'%')}</td><td class='n'>{f1(v.get('cpu_p95'),'%')}</td><td class='n'>{f1(v.get('cpu_max_run'),'%')}</td><td class='n'>{f1(v.get('mem_avg_mib'),'MiB')}</td><td class='n'>{f1(v.get('mem_max_mib'),'MiB')}</td></tr>")
        h.append("</table>")
    h.append("<h2>What this result does and does not show</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in F["lim"]) + "</ul>")
    so = F["brd"].get("scope_out") or []
    if so: h.append("<h2>Not covered in this phase</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in so) + "</ul>")
    oi = [o for o in (F["brd"].get("open_items") or []) if str(o.get("status", "")).lower() == "open" and o.get("question")]
    if oi: h.append("<h2>Open items</h2><ul>" + "".join(f"<li>{esc(o['question'])}</li>" for o in oi) + "</ul>")
    h.append("<h2>Documents in this pack</h2><ul><li><a href='brd.html'>Business requirements document</a> (what was agreed to be tested)</li>" + f"<li><a href='runs/{esc(rid)}/report.html'>Full execution report of the selected run</a>" + ("" if not F['dash'] else f" and its <a href='runs/{esc(rid)}/dashboard.html'>detailed charts</a>") + "</li><li>The report of every other run and the raw evidence files are in the <code>runs/</code> folder.</li><li><code>manifest.json</code> lists every file with a fingerprint (SHA-256).</li></ul>")
    ap_rows = F["brd"].get("approvals") or []
    h.append("<h2>Sign-off</h2><table><tr><th>Role</th><th>Name</th><th>Decision</th><th>Date</th></tr>" + "".join(f"<tr><td>{esc(x.get('role'))}</td><td>{esc(x.get('name')) or '&nbsp;'}</td><td>{esc(x.get('decision')) or '&nbsp;'}</td><td>{esc(x.get('date')) or '&nbsp;'}</td></tr>" for x in ap_rows) + "</table>")
    open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(page(f"Performance test results - {meta.get('application')}", "".join(h)))
    # secret scan over everything text
    hits = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            if f.endswith((".html", ".json", ".txt")):
                t = open(p, encoding="utf-8", errors="replace").read()
                pats = SECRETS[:2] if f == "dashboard.html" else SECRETS   # k6's own page contains minified code with words like 'token'; only strict token patterns apply to it
                if any(rx.search(t) for rx in pats): hits.append(os.path.relpath(p, root))
    if hits:
        shutil.rmtree(root); sys.exit("Secret-like text found, so no pack was built. Check these files in the runs: " + ", ".join(hits))
    # manifest + zip
    files = sorted(os.path.relpath(os.path.join(dp, f), root) for dp, _, fs in os.walk(root) for f in fs)
    man = {"created_utc": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "application": meta.get("application"), "client": meta.get("client"), "selected_run": rid,
           "brd_version": meta.get("version"), "brd_status": meta.get("status"), "environment": run_.get("env"), "tool": run_.get("k6_version"),
           "runs_included": [r for r, _, _ in hist], "runs_excluded_no_results": excluded, "files": [{"path": f, "sha256": sha256(os.path.join(root, f))} for f in files if f != "manifest.json"]}
    json.dump(man, open(os.path.join(root, "manifest.json"), "w"), indent=1)
    zp = root + ".zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fs in os.walk(root):
            for f in fs: z.write(os.path.join(dp, f), os.path.relpath(os.path.join(dp, f), os.path.dirname(root)))
    for w in warns: print("WARNING:", w)
    print(f"CLIENT PACK: {root}/index.html\nZIP: {zp}\nSelected run: {rid} ({run_.get('vus')} users). Runs included: {len(hist)}. Nothing was sent anywhere.")
    if a.open:
        import webbrowser; webbrowser.open("file://" + os.path.abspath(os.path.join(root, "index.html")))

if __name__ == "__main__": main()
