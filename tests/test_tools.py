"""Tests for the harness tools. Run from the repo root:  python -m unittest discover -s tests -v
Uses only the standard library and PyYAML. Tests that need k6 are skipped when k6 is not installed (set K6_BIN or put k6 on PATH)."""
import os, sys, json, shutil, subprocess, tempfile, threading, unittest, yaml, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
K6 = shutil.which("k6") or os.environ.get("K6_BIN")
SKELETON = os.path.join(ROOT, ".github", "skills", "k6-script-builder", "reference-skeleton.js")

def tool(name, *args, env=None):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, name), *args], capture_output=True, text=True, env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr)

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True); open(path, "w", encoding="utf-8").write(text)

def metric(p95, p99=None): return {"avg": p95 / 2, "min": 1, "med": p95 / 2, "max": p95 * 3, "p(90)": p95 * 0.9, "p(95)": p95, "p(99)": p99 or p95 * 1.3}

def make_project(tmp, runs=(), auth="not_required", peak="10 concurrent users", script=True):
    """A small complete project. runs: list of (id, profile, vus, outcome, p95_ms)."""
    d = os.path.join(tmp, "projects", "Acme", "demo"); os.makedirs(d)
    write(os.path.join(d, "brd.yaml"), f"""
meta: {{client: Acme, application: Demo App, version: "0.1", status: Draft, prepared_by: QA}}
purpose: practice
scope_in: [Demo]
transactions:
  - {{id: T1, name: Browse, traffic_share: "44%", measure_start_end: a to b}}
  - {{id: T2, name: Search, traffic_share: "31%", measure_start_end: a to b}}
  - {{id: T3, name: Detail, traffic_share: "25%", measure_start_end: a to b}}
workload: {{peak_concurrent_users: "{peak}", peak_window: n/a, think_time: 1-3 s, basis: assumed}}
requirements:
  - {{id: PR-01, transaction: T2, metric: response time, target: "<= 2 s", percentile: p95, load_condition: peak, priority: Must, notes: ""}}
  - {{id: PR-02, transaction: T2, metric: response time, target: "<= 4 s", percentile: p99, load_condition: peak, priority: Must, notes: ""}}
  - {{id: PR-03, transaction: All, metric: error rate, target: "< 1%", percentile: n/a, load_condition: peak, priority: Must, notes: ""}}
  - {{id: PR-04, transaction: T9, metric: response time, target: "<= 3 s", percentile: p95, load_condition: peak, priority: Must, notes: "T9 deferred to a later phase"}}
test_types: [{{type: Load, needed: yes, notes: ""}}]
abort_conditions: [{{condition: Error rate, threshold: "> 2%", action: stop}}]
environment: {{personal_data_confirmation: synthetic data only}}
scope_out: [T9 deferred]
approvals: [{{role: Business owner, name: "", decision: "", date: ""}}]
open_items: []
""")
    write(os.path.join(d, "environments.yaml"), f"""
active: local
environments:
  local: {{description: test app, type: local, base_url: "http://127.0.0.1:1", owner: me, authorisation: {auth}, max_vus: 20, max_run_minutes: 10,
          test_windows: any, test_data: synthetic, monitoring: {{source: none, detail: ""}}, verified: {{date: "", by: "", note: ""}}}}
""")
    apis = "\n".join(f"  - {{id: API-00{i}, transaction: T{t}, safe_to_load: 'yes', method: GET, path: /x{i}, auth: none, response: {{status: 200}}, evidence: {{source_type: browser, source: s}}}}" for i, t in [(1, 1), (2, 1), (3, 1), (4, 2), (5, 3), (6, 3)])
    write(os.path.join(d, "api-catalogue.yaml"), f"meta: {{application: Demo, base_url: x}}\napis:\n{apis}\nflows:\n  - {{transaction: T1, steps: [API-001, API-002, API-003]}}\n  - {{transaction: T2, steps: [API-004]}}\n  - {{transaction: T3, steps: [API-005, API-006]}}\n")
    if script:
        s = open(SKELETON, encoding="utf-8").read()
        s = s.replace("    'transaction_duration{transaction:T1}'", "    'transaction_duration{transaction:T3}': ['p(95)<2000'],\n    'transaction_duration{transaction:T1}'", 1)
        write(os.path.join(d, "k6", "script.js"), s)
        write(os.path.join(d, "k6", "requirement-map.yaml"), """
- {requirement: PR-01, k6_metric: "transaction_duration{transaction:T2}", threshold: "p(95)<2000"}
- {requirement: PR-02, k6_metric: "transaction_duration{transaction:T2}", threshold: "p(99)<4000"}
- {requirement: PR-03, k6_metric: "http_req_failed", threshold: "rate<0.01"}
""")
    for rid, profile, vus, outcome, p95 in runs:
        rd = os.path.join(d, "runs", rid)
        write(os.path.join(rd, "run.json"), json.dumps({"run_id": rid, "profile": profile, "vus": vus, "ramp_up": "30s", "steady": "3m", "ramp_down": "30s", "env": "local", "env_type": "local",
            "authorisation": auth, "target": "http://127.0.0.1:1", "start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-01-01T00:05:00Z", "k6_version": "k6 v1.0.0 (test)", "exit_code": 0 if outcome == "passed" else 99,
            "outcome": outcome, "command": "k6 run", "monitoring": {"source": "none", "status": "none", "samples": 0, "note": ""}}))
        write(os.path.join(rd, "summary.json"), json.dumps({"metrics": {f"transaction_duration{{transaction:T{i}}}": metric(p95) for i in (1, 2, 3)} | {"http_req_failed": {"value": 0.0, "passes": 0, "fails": 100},
            "http_reqs": {"count": 100, "rate": 5.0}, "iterations": {"count": 40}, "vus_max": {"value": vus}, "blocked_responses": {"count": 0}, "checks": {"value": 1.0}}}))
        write(os.path.join(rd, "k6-output.txt"), "k6 output\n")
    return d


class TestLint(unittest.TestCase):
    def test_start_project_continues_to_client_pack(self):
        prompt = open(os.path.join(ROOT, ".github", "prompts", "start-project.prompt.md"), encoding="utf-8").read()
        self.assertIn("continue end to end through the client pack", prompt)
        self.assertIn("tools/status.py", prompt)
        self.assertIn("brd.py advise", prompt); self.assertIn("run plan", prompt)

    def test_repo_is_clean(self):
        rc, out = tool("lint.py"); self.assertEqual(rc, 0, out)

    def test_doctor_reports_prerequisites(self):
        import doctor
        res = doctor.checks(); names = {r[1] for r in res}
        self.assertTrue({"Python 3.9+", "PyYAML", "k6", "pandoc"} <= names)
        self.assertEqual([r for r in res if r[1] == "PyYAML"][0][0], "OK")  # this test run imports yaml
        rc, out = tool("doctor.py"); self.assertEqual(rc, 0, out); self.assertIn("DOCTOR: OK", out)

    def test_lint_flags_old_step_numbers_and_missing_requirements(self):
        import lint
        tmp = tempfile.mkdtemp(); old = lint.ROOT
        try:
            for sub in (".github", "tools", "templates"): shutil.copytree(os.path.join(ROOT, sub), os.path.join(tmp, sub))
            write(os.path.join(tmp, "README.md"), "Step 7: k6 script\n")
            lint.ROOT = tmp; problems = "\n".join(lint.lint())
            self.assertIn("old step numbering", problems); self.assertIn("requirements.txt", problems)
        finally: lint.ROOT = old; shutil.rmtree(tmp)

    def test_detects_problems(self):
        import lint
        tmp = tempfile.mkdtemp(); old = lint.ROOT
        try:
            for sub in (".github", "tools", "templates"): shutil.copytree(os.path.join(ROOT, sub), os.path.join(tmp, sub))
            write(os.path.join(tmp, "README.md"), "see tools/doesnotexist.py\n")
            sk = os.path.join(tmp, ".github", "skills", "end-to-end", "SKILL.md")
            t = open(sk, encoding="utf-8").read().split("\n"); t[2] = "description: Loop on status: do the next stage"; open(sk, "w", encoding="utf-8").write("\n".join(t))
            ci = os.path.join(tmp, ".github", "copilot-instructions.md"); open(ci, "a").write("\n3. duplicate rule number\n")
            lint.ROOT = tmp; problems = "\n".join(lint.lint())
            self.assertIn("frontmatter does not parse", problems); self.assertIn("doesnotexist.py", problems); self.assertIn("rule numbers", problems)
        finally: lint.ROOT = old; shutil.rmtree(tmp)


class TestBrdAndEnv(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp)
    def test_template_reports_missing(self):
        rc, out = tool("brd.py", "check", os.path.join(ROOT, "templates", "brd.template.yaml")); self.assertEqual(rc, 1); self.assertIn("MISSING", out)
    def test_complete_project_passes_and_renders(self):
        d = make_project(self.tmp); rc, out = tool("brd.py", "check", os.path.join(d, "brd.yaml")); self.assertEqual(rc, 0, out)
        rc, out = tool("brd.py", "render", os.path.join(d, "brd.yaml")); md = open(os.path.join(d, "brd.md"), encoding="utf-8").read()
        self.assertIn("## 6. Performance requirements", md); self.assertIn("Authorisation to test", md)
    def test_provenance_uses_most_specific_and_latest_evidence(self):
        import brd as brdtool
        d = {"purpose": "p", "workload": {"think_time": "5 s", "basis": "assumed", "peak_window": ""},
             "transactions": [{"id": "T1", "name": "Login", "traffic_share": "50%"}, {"id": "T2", "name": "Search", "traffic_share": "50%"}],
             "abort_conditions": [{"condition": "Error rate", "threshold": "> 5%", "action": "stop"}],
             "evidence": [{"field": "purpose", "source": "user answer, 2026-11-23"},
                          {"field": "workload.basis", "source": "user answer, 2026-11-23"}, {"field": "workload.basis", "source": "sample assumption supplied by Copilot"},
                          {"field": "transactions", "source": "user answer, 2026-11-23"}, {"field": "transactions.T1-T2 traffic_share", "source": "advised by test lead"},
                          {"field": "abort_conditions", "source": "advised by test lead"}]}
        got = {r["item"]: r["basis"] for r in brdtool.provenance(d)}
        self.assertEqual((got["Purpose"], got["Basis of figures"], got["Peak window and duration"]), ("Stated", "Assumed", "Open"))
        self.assertEqual((got["T1 Login"], got["T2 share of traffic"], got["T1 response-time start/end"]), ("Stated", "Advised", "Open"))
        self.assertEqual(got["Error rate"], "Advised"); self.assertEqual(got["User think time and pacing"], "Not evidenced")
    @unittest.skipUnless(shutil.which("pandoc"), "pandoc not installed")
    def test_brdexport_builds_word_file_with_answer_columns_and_blank_signoff(self):
        import zipfile
        d = make_project(self.tmp); rc, out = tool("brdexport.py", d); self.assertEqual(rc, 0, out)
        docx = os.path.join(d, "client-pack", "brd-confirmation-v0.1.docx"); self.assertTrue(os.path.exists(docx))
        xml = zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8")
        for text in ("Your response", "Part E. Sign-off", "Not evidenced", "Signature"): self.assertIn(text, xml)
        write(os.path.join(d, "brd.yaml"), open(os.path.join(d, "brd.yaml"), encoding="utf-8").read() + "\nopen_items: [{question: 'Secret password: \"hunter2hunter2\"', status: Open}]\n")
        rc, out = tool("brdexport.py", d); self.assertEqual(rc, 1); self.assertIn("Secret-like", out)
    def test_unconfirmed_authorisation_is_a_gap(self):
        d = make_project(self.tmp, auth="not_confirmed"); rc, out = tool("brd.py", "check", os.path.join(d, "brd.yaml")); self.assertEqual(rc, 1); self.assertIn("not_confirmed", out)
    def test_questions_only_report_current_gaps_and_deduplicate(self):
        d = os.path.join(self.tmp, "projects", "Acme", "demo")
        os.makedirs(d)
        brd = os.path.join(d, "brd.yaml")
        write(brd, """
meta: {client: Acme, application: Demo}
purpose: ""
scope_in: [Demo]
transactions:
  - {id: T1, name: Browse, traffic_share: "", measure_start_end: ""}
workload: {peak_window: "", think_time: "", basis: ""}
requirements: [{id: PR-01, metric: response time, target: "", percentile: "", load_condition: ""}]
test_types: []
abort_conditions: []
environment: {target: "", owner: "", test_data: "", personal_data_confirmation: "", monitoring_access: "", test_windows: ""}
open_items: []
""")
        write(os.path.join(d, "environments.yaml"), """
active: local
environments:
  local: {description: test, type: local, base_url: "http://127.0.0.1:1", owner: me, authorisation: not_confirmed, max_vus: 5, max_run_minutes: 5,
          test_windows: "", test_data: "", monitoring: {source: none}, verified: {date: "", by: "", note: ""}}
""")
        rc, out = tool("brd.py", "questions", brd)
        self.assertEqual(rc, 0, out)
        self.assertIn("field=purpose", out); self.assertIn("Example:", out)
        for technical in ("traffic_share", "think_time", "abort_conditions", "requirements"): self.assertNotIn(technical, out)
        self.assertNotIn("scope_in", out)
        rc, out = tool("brd.py", "advise", brd)
        for key in ("traffic_share", "think_time", "requirement", "abort", "test_windows"): self.assertIn(key, out)
        rc, out = tool("brd.py", "advise", brd, "--apply", "--skip=think_time"); self.assertEqual(rc, 0, out)
        rc, out = tool("brd.py", "check", brd)
        self.assertIn("think time", out.lower()); self.assertIn("Purpose", out)
        for gone in ("Traffic share", "Abort", "Test types", "test windows", "Requirement PR-01"): self.assertNotIn(gone, out)
        d2 = yaml.safe_load(open(brd)); self.assertEqual(d2["transactions"][0]["traffic_share"], "100%")
        self.assertTrue(any(r.get("type") == "Assumption" and "Advised" in r.get("description", "") for r in d2["risks"]))
    def test_environment_rules(self):
        import envconf
        ok = {"type": "local", "base_url": "http://h:1", "owner": "me", "authorisation": "not_required", "max_vus": 5, "max_run_minutes": 5, "monitoring": {"source": "none"}}
        good = {"active": "a", "environments": {"a": ok}}; self.assertEqual(envconf.problems(good)[0], [])
        bad = {"active": "a", "environments": {"a": {**ok, "type": "public"}}}; self.assertTrue(any("not_required" in p for p in envconf.problems(bad)[0]))
        bad = {"active": "a", "environments": {"a": {**ok, "base_url": "http://user:pw@h"}}}; self.assertTrue(envconf.problems(bad)[0])
        bad = {"active": "a", "environments": {"a": {**ok, "monitoring": {"source": "docker_stats"}}}}; self.assertTrue(any("containers" in p for p in envconf.problems(bad)[0]))
        bad = {"active": "a", "environments": {"a": {**ok, "credentials_env_vars": ["hunter2pass"]}}}; self.assertTrue(envconf.problems(bad)[0])
        bad = {"active": "a", "environments": {"a": {**ok, "authorisation": "accepted_by_test_lead"}}}; self.assertTrue(any("authorisation_note" in p for p in envconf.problems(bad)[0]))
    def test_run_plan_rules(self):
        import envconf
        ok = {"type": "local", "base_url": "http://h:1", "owner": "me", "authorisation": "not_required", "max_vus": 5, "max_run_minutes": 5, "monitoring": {"source": "none"}}
        plan = {"approved_note": "QA lead in chat 2026-11-23", "load_steps": [2, 4], "ramp_up": "30s", "steady": "3m", "ramp_down": "30s"}
        self.assertEqual(envconf.problems({"active": "a", "environments": {"a": {**ok, "run_plan": plan}}})[0], [])
        for bad in ({"load_steps": [6]}, {"load_steps": [2, 5]}, {"steady": "10m"}):
            self.assertTrue(envconf.problems({"active": "a", "environments": {"a": {**ok, "run_plan": {**plan, **bad}}}})[0], bad)
        self.assertIsNone(envconf.plan({**ok, "run_plan": {**plan, "approved_note": ""}}))


class TestCatalogueImports(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp); self.cat = os.path.join(self.tmp, "api-catalogue.yaml")
    def test_openapi_and_dedupe(self):
        spec = os.path.join(self.tmp, "s.json")
        json.dump({"openapi": "3.0.0", "servers": [{"url": "https://api.example.com"}], "paths": {"/items": {"get": {"summary": "List", "responses": {"200": {"content": {"application/json": {"schema": {"properties": {"data": {}}}}}}}}},
            "/orders": {"post": {"summary": "Order", "requestBody": {"content": {"application/json": {"schema": {"properties": {"password": {}}}}}}, "responses": {"201": {}}}}}}, open(spec, "w"))
        tool("catalogue.py", "import-openapi", self.cat, spec); tool("catalogue.py", "import-openapi", self.cat, spec)
        d = yaml.safe_load(open(self.cat)); self.assertEqual(len(d["apis"]), 2); self.assertEqual({a["method"] for a in d["apis"]}, {"GET", "POST"})
        self.assertEqual([a["safe_to_load"] for a in d["apis"] if a["method"] == "POST"], ["unknown"])
    def test_postman_redacts_secrets(self):
        col = os.path.join(self.tmp, "c.json")
        json.dump({"item": [{"name": "Login", "request": {"method": "POST", "url": "https://api.example.com/login", "header": [{"key": "Authorization", "value": "Bearer eyJabcdefghijklmnop.qrstuvwxyz1234567890"}],
            "body": {"mode": "raw", "raw": json.dumps({"email": "a@b.c", "password": "hunter2hunter2"})}}}]}, open(col, "w"))
        tool("catalogue.py", "import-postman", self.cat, col); t = open(self.cat).read()
        self.assertNotIn("hunter2", t); self.assertNotIn("eyJabc", t)
    def test_postman_reads_test_scripts_and_environment(self):
        def req(name, method, url, script, hdr=()):
            return {"name": name, "request": {"method": method, "url": url, "header": [{"key": "Authorization", "value": "Bearer {{token}}"}] if hdr else []},
                    "event": [{"listen": "test", "script": {"exec": script}}]}
        login = ["pm.response.to.have.status(200);", "const d = pm.response.json();", "pm.expect(d).to.have.property('accessToken');", "pm.environment.set('token', d.accessToken);"]
        col = os.path.join(self.tmp, "c.json"); env = os.path.join(self.tmp, "e.json")
        json.dump({"item": [
            req("Bad login", "POST", "{{base_url}}/login", ["pm.expect(pm.response.code).to.be.oneOf([400, 401]);"]),
            req("Login", "POST", "{{base_url}}/login", login),
            req("List", "GET", "{{base_url}}/items", ["pm.expect(pm.response.code).to.be.oneOf([200, 201]);", "pm.expect(pm.response.responseTime).to.be.below(1500);"], hdr=True),
            req("Other", "GET", "{{base_url}}/other", [], hdr=True)]}, open(col, "w"))
        json.dump({"values": [{"key": "base_url", "value": "https://api.example.com", "enabled": True}, {"key": "token", "value": "supersecretvalue1", "enabled": True}]}, open(env, "w"))
        tool("catalogue.py", "import-postman", self.cat, col, env); d = yaml.safe_load(open(self.cat)); by = {a["name"]: a for a in d["apis"]}
        self.assertEqual(d["meta"]["base_url"], "https://api.example.com"); self.assertNotIn("supersecret", open(self.cat).read())
        self.assertEqual(sorted(by), ["List", "Login", "Other"])
        self.assertEqual(by["Login"]["response"]["status"], 200); self.assertEqual(by["Login"]["response"]["fields"], ["accessToken"])
        self.assertEqual(by["List"]["response"]["expected_statuses"], [200, 201]); self.assertIn("1500", by["List"]["response"]["notes"])
        self.assertEqual(by["List"]["dynamic_values"][0]["from_api"], by["Login"]["id"]); self.assertEqual(by["List"]["depends_on"], [by["Login"]["id"]])
        self.assertEqual(by["Other"]["response"], {}); self.assertTrue(any("Bad login" in n for n in d["notes"]))
    def test_har_excludes_third_party_and_redacts(self):
        har = os.path.join(self.tmp, "c.har")
        json.dump({"log": {"entries": [
            {"time": 10, "_resourceType": "xhr", "request": {"method": "GET", "url": "https://api.example.com/brands", "headers": [{"name": "Authorization", "value": "Bearer abcdefghijklmnopqrstuvwxyz"}]}, "response": {"status": 200, "content": {"mimeType": "application/json", "text": "[{\"id\":1}]"}}},
            {"time": 5, "_resourceType": "xhr", "request": {"method": "POST", "url": "https://www.google-analytics.com/collect", "headers": []}, "response": {"status": 200, "content": {"mimeType": "application/json", "text": "{}"}}}]}}, open(har, "w"))
        tool("catalogue.py", "import-har", self.cat, har, "https://api.example.com"); d = yaml.safe_load(open(self.cat))
        self.assertEqual(len(d["apis"]), 1); self.assertIn("www.google-analytics.com", d["meta"]["excluded_hosts"]); self.assertNotIn("abcdefghijklmnop", open(self.cat).read())
    def test_check_flags_unmapped_transaction(self):
        d = make_project(self.tmp + "/p" if False else tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, os.path.dirname(os.path.dirname(os.path.dirname(d))))
        cat = yaml.safe_load(open(os.path.join(d, "api-catalogue.yaml"))); cat["apis"] = [a for a in cat["apis"] if a["transaction"] != "T3"]; yaml.safe_dump(cat, open(os.path.join(d, "api-catalogue.yaml"), "w"))
        rc, out = tool("catalogue.py", "check", os.path.join(d, "api-catalogue.yaml")); self.assertEqual(rc, 1); self.assertIn("T3", out)


class TestK6Check(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp); self.d = make_project(self.tmp)
    def test_good_script_passes(self): rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 0, out)
    def test_conditional_api_is_not_required_in_script(self):
        cat = yaml.safe_load(open(os.path.join(self.d, "api-catalogue.yaml")))
        cat["apis"].append({"id": "API-999", "transaction": "T1", "safe_to_load": "conditional", "method": "POST", "path": "/conditional"})
        yaml.safe_dump(cat, open(os.path.join(self.d, "api-catalogue.yaml"), "w"))
        rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 0, out)
    def test_wrong_threshold_fails(self):
        p = os.path.join(self.d, "k6", "script.js"); t = open(p).read().replace("p(99)<4000", "p(99)<9000"); open(p, "w").write(t)
        rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 1); self.assertIn("PR-02", out)
    def test_literal_url_and_missing_api_fail(self):
        p = os.path.join(self.d, "k6", "script.js"); t = open(p).read().replace("'API-006'", "'API-099'") + "\nconst X = 'https://evil.example.com';\n"; open(p, "w").write(t)
        rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 1); self.assertIn("API-006", out); self.assertIn("literal URL", out)


class TestReportAndPack(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp)
    def test_browser_runs_report_browser_request_failures(self):
        import report
        n, rate, failed, label = report.req_stats({"browser_http_req_failed": {"passes": 4, "fails": 26, "value": 0.1333}})
        self.assertEqual((n, rate, failed, label), (30, None, 0.1333, "browser requests"))
        self.assertEqual(report.req_stats({"http_reqs": {"count": 2, "rate": 1.0}, "http_req_failed": {"value": 0.5}})[:3], (2, 1.0, 0.5))
    def test_below_peak_is_not_judged(self):
        import report; d = make_project(self.tmp, runs=[("r-load-5", "load", 5, "passed", 80)]); page, f = report.build(d, "r-load-5")
        st = {x["r"]["id"]: x["status"] for x in f["res"]}
        self.assertEqual(st["PR-01"], "Not measured at peak load"); self.assertEqual(st["PR-04"], "Deferred"); self.assertIn("deferred", f["vsub"]); self.assertEqual(f["vcls"], "warn")
    def test_report_lists_each_api_when_k6_exported_them(self):
        import report; d = make_project(self.tmp, runs=[("r-api", "load", 10, "passed", 80)]); sp = os.path.join(d, "runs", "r-api", "summary.json")
        s = json.load(open(sp)); s["metrics"]["http_req_duration{api:API-001}"] = metric(120); s["metrics"]["http_req_duration{api:API-004}"] = metric(300); s["metrics"]["http_reqs{api:API-004}"] = {"count": 42, "rate": 1}
        json.dump(s, open(sp, "w")); page, _ = report.build(d, "r-api")
        self.assertIn("Response times per API", page); self.assertIn("API-001", page); self.assertIn("GET /x1", page); self.assertIn("API-004", page); self.assertNotIn("API-002<", page)
        json.dump({**s, "metrics": {k: v for k, v in s["metrics"].items() if "api:" not in k}}, open(sp, "w")); self.assertIn("not exported", report.build(d, "r-api")[0])
    def test_at_peak_is_met_or_not_met(self):
        import report; d = make_project(self.tmp, runs=[("r-ok", "load", 10, "passed", 80), ("r-slow", "load", 10, "passed", 2500)])
        a = {x["r"]["id"]: x["status"] for x in report.build(d, "r-ok")[1]["res"]}; b = {x["r"]["id"]: x["status"] for x in report.build(d, "r-slow")[1]["res"]}
        self.assertEqual((a["PR-01"], a["PR-03"]), ("Met", "Met")); self.assertEqual(b["PR-01"], "Not met")
    def test_failed_run_banner_names_the_error(self):
        import report; d = make_project(self.tmp, runs=[("r-err", "load", 10, "error", 80)]); open(os.path.join(d, "runs", "r-err", "k6-output.txt"), "w").write('time="x" level=error msg="Error: setup failed: no ids found" hint="script exception"\n')
        f = report.build(d, "r-err")[1]; self.assertIn("failed before", f["vtxt"]); self.assertIn("setup failed", f["vsub"])
    def test_clientpack_builds_and_stops_on_secret(self):
        d = make_project(self.tmp, runs=[("r1", "smoke", 1, "passed", 50), ("r2", "load", 10, "passed", 80)])
        rc, out = tool("clientpack.py", d); self.assertEqual(rc, 0, out); pack = os.path.join(d, "client-pack"); names = os.listdir(pack)
        folder = [n for n in names if not n.endswith(".zip")][0]; self.assertTrue(any(n.endswith(".zip") for n in names))
        for f in ("index.html", "brd.html", "manifest.json"): self.assertTrue(os.path.exists(os.path.join(pack, folder, f)), f)
        self.assertIn("r2", folder)
        open(os.path.join(d, "runs", "r2", "k6-output.txt"), "a").write("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij\n")
        rc, out = tool("clientpack.py", d); self.assertNotEqual(rc, 0); self.assertIn("Secret-like", out)
    def test_status_walks_the_stages(self):
        d = make_project(self.tmp, runs=[]); rc, out = tool("status.py", d, "--json"); j = json.loads(out)
        if shutil.which("pandoc"):
            self.assertFalse(j["stages"][0]["done"]); self.assertIn("brdexport.py", j["next"]["next"])
            rc, out = tool("brdexport.py", d); self.assertEqual(rc, 0, out); rc, out = tool("status.py", d, "--json"); j = json.loads(out)
            os.utime(os.path.join(d, "brd.yaml")); rc, out = tool("status.py", d, "--json"); self.assertFalse(json.loads(out)["stages"][0]["done"])
        self.assertEqual([s["done"] for s in j["stages"]][:3], [True, True, True]); self.assertEqual(j["next"]["n"], 4)
        e = os.path.join(self.tmp, "projects", "New", "app"); os.makedirs(e); rc, out = tool("status.py", e, "--json"); self.assertEqual(json.loads(out)["next"]["n"], 1)
    def test_run_plan_lets_a_completed_run_with_missed_targets_finish_the_flow(self):
        d = make_project(self.tmp, runs=[("20260101T000000Z-local-smoke-1vu", "smoke", 1, "passed", 50), ("r-miss", "load", 10, "thresholds_failed", 2500)])
        rc, out = tool("status.py", d, "--json"); self.assertFalse(json.loads(out)["stages"][6]["done"])
        rc, out = tool("clientpack.py", d); self.assertNotEqual(rc, 0)
        envp = os.path.join(d, "environments.yaml"); cfg = yaml.safe_load(open(envp))
        cfg["environments"]["local"]["run_plan"] = {"approved_note": "QA lead in chat 2026-11-23", "load_steps": [5, 10], "ramp_up": "30s", "steady": "3m", "ramp_down": "30s", "pack_if_targets_missed": True}
        yaml.safe_dump(cfg, open(envp, "w"))
        rc, out = tool("status.py", d, "--json"); self.assertTrue(json.loads(out)["stages"][6]["done"], out)
        rc, out = tool("clientpack.py", d); self.assertEqual(rc, 0, out); self.assertTrue(any("r-miss" in n for n in os.listdir(os.path.join(d, "client-pack"))))
    def test_status_accepts_explicit_open_items_decision(self):
        d = make_project(self.tmp, runs=[])
        brd = os.path.join(d, "brd.yaml")
        text = open(brd, encoding="utf-8").read()
        text = text.replace('status: Draft, prepared_by: QA', 'status: Draft, open_items_decision: proceed_with_open_items, prepared_by: QA')
        open(brd, "w", encoding="utf-8").write(text)
        rc, out = tool("status.py", d, "--json")
        j = json.loads(out)
        self.assertTrue(j["stages"][0]["done"] or shutil.which("pandoc"))
        if shutil.which("pandoc"):
            tool("brdexport.py", d); rc, out = tool("status.py", d, "--json"); self.assertTrue(json.loads(out)["stages"][0]["done"])


class TestMonitor(unittest.TestCase):
    def test_parse_and_summarise(self):
        import monitor
        self.assertEqual(monitor.parse_line("api|12.5%|45.2MiB / 7.6GiB|0.6%")["mem_mib"], 45.2); self.assertIsNone(monitor.parse_line("garbage"))
        s = [{"t_s": t, "series": "a", "cpu_pct": c, "mem_mib": 10} for t, c in [(0, 90), (10, 20), (20, 30), (30, 40), (40, 5)]]
        r = monitor.summarise(s, [10, 30])["a"]; self.assertEqual(r["cpu_avg"], 30.0); self.assertEqual(r["cpu_max_run"], 90.0)


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, o, c=200): b = json.dumps(o).encode(); self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/login" and body == {"username": "u1", "password": "pw1"}: return self._s({"accessToken": "tok123"})
        self._s({"e": 1}, 401)
    def do_GET(self):
        if self.path == "/secure": return self._s({"id": 1}) if self.headers.get("Authorization") == "Bearer tok123" else self._s({"e": 1}, 401)
        if self.path == "/items/a": return self._s({"id": "a"})
        if self.path == "/brands": return self._s([{"id": 1}])
        self._s({"e": 1}, 404)
    def do_QUERY(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n); self._s({"data": [{"id": "a"}]}) if self.path == "/items" else self._s({"e": 1}, 404)

class TestTargetCheck(unittest.TestCase):
    def test_ok_differs_and_skipped(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _H); threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown)
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp); d = os.path.join(tmp, "p"); os.makedirs(d)
        write(os.path.join(d, "environments.yaml"), f"active: l\nenvironments:\n  l:\n    description: t\n    type: local\n    base_url: \"http://127.0.0.1:{srv.server_address[1]}\"\n    owner: me\n    authorisation: not_required\n    max_vus: 5\n    max_run_minutes: 5\n    monitoring: {{source: none, detail: \"\"}}\n    verified: {{date: \"\", by: \"\", note: \"\"}}\n")
        write(os.path.join(d, "api-catalogue.yaml"), """
apis:
  - {id: API-001, method: GET, path: /brands, transaction: T1, auth: none, safe_to_load: "yes", response: {status: 200, fields: [id]}}
  - {id: API-002, method: QUERY, path: /items, transaction: T1, auth: none, safe_to_load: "yes", request_body: {example: {page: "1"}}, response: {status: 200, fields: [data]}}
  - {id: API-003, method: GET, path: "/items/{id}", transaction: T2, auth: none, safe_to_load: "yes", depends_on: [API-002], dynamic_values: [{name: id, from_api: API-002, json_path: "data[].id"}], response: {status: 200, fields: [id]}}
  - {id: API-004, method: GET, path: /missing, transaction: T2, auth: none, safe_to_load: "yes", response: {status: 200}}
  - {id: API-005, method: POST, path: /orders, transaction: T2, auth: none, safe_to_load: "no", response: {status: 201}}
  - {id: API-006, method: GET, path: /brands, transaction: T2, auth: none, safe_to_load: "yes", response: {status: 200, fields: [no_such_field]}}
""")
        rc, out = tool("targetcheck.py", d); self.assertEqual(rc, 1, out)
        self.assertEqual(out.count(" OK"), 3); self.assertIn("status 404", out); self.assertIn("no_such_field", out); self.assertIn("write call, not sent", out)
        self.assertIn("tools/targetcheck.py", open(os.path.join(d, "environments.yaml")).read())
        self.assertEqual(json.load(open(os.path.join(d, "target-check.json")))["calls_ok"], 3)
    def test_login_with_credentials_from_env_vars(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _H); threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown)
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp); d = os.path.join(tmp, "p"); os.makedirs(d)
        write(os.path.join(d, "environments.yaml"), f"active: l\nenvironments:\n  l:\n    description: t\n    type: local\n    base_url: \"http://127.0.0.1:{srv.server_address[1]}\"\n    owner: me\n    authorisation: not_required\n    max_vus: 5\n    max_run_minutes: 5\n    credentials_env_vars: [APP_USER, APP_PASSWORD]\n    monitoring: {{source: none, detail: \"\"}}\n    verified: {{date: \"\", by: \"\", note: \"\"}}\n")
        write(os.path.join(d, "api-catalogue.yaml"), """
apis:
  - {id: API-001, method: POST, path: /login, transaction: T1, auth: none, safe_to_load: conditional, request_body: {example: {username: x, password: <redacted>}}, response: {status: 200, fields: [accessToken]}}
  - {id: API-002, method: GET, path: /secure, transaction: T1, auth: bearer, safe_to_load: "yes", depends_on: [API-001], dynamic_values: [{name: token, from_api: API-001, json_path: "$.accessToken"}], response: {status: 200, fields: [id]}}
  - {id: API-003, method: DELETE, path: /secure, transaction: T1, auth: bearer, safe_to_load: conditional, response: {status: 200}}
""")
        rc, out = tool("targetcheck.py", d); self.assertEqual(rc, 1); self.assertEqual(json.load(open(os.path.join(d, "target-check.json")))["calls_ok"], 0)
        self.assertIn("credentials_env_vars", out)
        rc, out = tool("targetcheck.py", d, env={"APP_USER": "u1", "APP_PASSWORD": "pw1"}); self.assertEqual(rc, 0, out); tc = open(os.path.join(d, "target-check.json")).read()
        self.assertEqual(json.loads(tc)["calls_ok"], 1); self.assertIn("write call, not sent", out)
        for secret in ("pw1", "tok123"): self.assertNotIn(secret, out + tc)
        rc, out = tool("targetcheck.py", d, env={"APP_USER": "u1", "APP_PASSWORD": "wrong"}); self.assertEqual(rc, 1); self.assertIn("login answered 401", out)
    def test_refuses_when_not_confirmed(self):
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp); d = make_project(tmp, auth="not_confirmed"); rc, out = tool("targetcheck.py", d); self.assertNotEqual(rc, 0); self.assertIn("not_confirmed", out)
    def test_verified_note_replaces_a_block_style_value(self):
        import targetcheck
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp); p = os.path.join(tmp, "environments.yaml")
        yaml.safe_dump({"active": "t", "environments": {"t": {"base_url": "http://x", "verified": {"date": "", "by": "", "note": ""}, "max_vus": 5}}}, open(p, "w"), sort_keys=False)
        self.assertTrue(targetcheck.set_verified(p, "t", "2026-01-01", "me", "ok"))
        e = yaml.safe_load(open(p))["environments"]["t"]; self.assertEqual(e["verified"]["note"], "ok"); self.assertEqual(e["max_vus"], 5)


@unittest.skipUnless(K6, "k6 is not installed")
class TestRunGuards(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp); self.env = {"K6_BIN": K6}
    def test_load_needs_a_passed_smoke_run(self):
        d = make_project(self.tmp); rc, out = tool("runk6.py", d, "--profile", "load", "--vus", "5", env=self.env); self.assertNotEqual(rc, 0); self.assertIn("smoke", out)
    def test_unconfirmed_environment_is_refused(self):
        d = make_project(self.tmp, auth="not_confirmed"); rc, out = tool("runk6.py", d, "--profile", "smoke", env=self.env); self.assertNotEqual(rc, 0); self.assertIn("not_confirmed", out)
    def test_step_up_limits(self):
        d = make_project(self.tmp, runs=[("20260101T000000Z-local-smoke-1vu", "smoke", 1, "passed", 50)])
        rc, out = tool("runk6.py", d, "--profile", "load", "--vus", "10", env=self.env); self.assertNotEqual(rc, 0); self.assertIn("too big a step", out)
        rc, out = tool("runk6.py", d, "--profile", "load", "--vus", "50", env=self.env); self.assertNotEqual(rc, 0)


if __name__ == "__main__": unittest.main()
