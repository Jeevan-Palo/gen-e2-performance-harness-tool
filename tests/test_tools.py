"""Tests for the harness tools. Run from the repo root:  python -m unittest discover -s tests -v
Uses only the standard library and PyYAML. Tests that need k6 are skipped when k6 is not installed (set K6_BIN or put k6 on PATH)."""
import os, sys, json, shutil, subprocess, tempfile, threading, unittest, yaml, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

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
test_types:
  - type: "Baseline (single user)"
    needed: no
    notes: ""
  - type: "Load (stepped ramp)"
    needed: yes
    notes: ""
    parameters: {{steps: [5, 10], step_hold: "1m", peak_hold: "3m", ramp_down: "30s", flows: [T1, T2, T3]}}
  - type: Stress
    needed: no
    notes: ""
  - type: Spike
    needed: no
    notes: ""
  - type: "Endurance (soak)"
    needed: no
    notes: ""
  - type: Scalability
    needed: no
    notes: ""
abort_conditions: [{{condition: Error rate, threshold: "> 2%", action: stop}}]
exit_criteria:
  - {{profile: "Load (stepped ramp)", start_when: "Smoke passed", finish_when: "Peak step completed or abort condition fired"}}
evidence:
  - {{field: "test_types[0].needed", source: "test fixture"}}
  - {{field: "test_types[1].needed", source: "test fixture"}}
  - {{field: "test_types[1].parameters.steps", source: "test fixture"}}
  - {{field: "test_types[1].parameters.step_hold", source: "test fixture"}}
  - {{field: "test_types[1].parameters.peak_hold", source: "test fixture"}}
  - {{field: "test_types[1].parameters.ramp_down", source: "test fixture"}}
  - {{field: "test_types[1].parameters.flows", source: "test fixture"}}
  - {{field: "test_types[2].needed", source: "test fixture"}}
  - {{field: "test_types[3].needed", source: "test fixture"}}
  - {{field: "test_types[4].needed", source: "test fixture"}}
  - {{field: "test_types[5].needed", source: "test fixture"}}
  - {{field: "exit_criteria[0].start_when", source: "test fixture"}}
  - {{field: "exit_criteria[0].finish_when", source: "test fixture"}}
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
            "outcome": outcome, "command": "k6 run", "flows": ["T1", "T2", "T3"],
            "monitoring": {"source": "none", "status": "none", "samples": 0, "note": ""}}))
        write(os.path.join(rd, "summary.json"), json.dumps({"metrics": {f"transaction_duration{{transaction:T{i}}}": metric(p95) for i in (1, 2, 3)} | {"http_req_failed": {"value": 0.0, "passes": 0, "fails": 100},
            "http_reqs": {"count": 100, "rate": 5.0}, "iterations": {"count": 40}, "vus_max": {"value": vus}, "blocked_responses": {"count": 0}, "checks": {"value": 1.0}}}))
        write(os.path.join(rd, "k6-output.txt"), "k6 output\n")
    return d


class TestLint(unittest.TestCase):
    def test_repo_is_clean(self):
        rc, out = tool("lint.py"); self.assertEqual(rc, 0, out)

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
        self.assertIn("Baseline (single user)", out)
    def test_complete_project_passes_and_renders(self):
        d = make_project(self.tmp); rc, out = tool("brd.py", "check", os.path.join(d, "brd.yaml")); self.assertEqual(rc, 0, out)
        rc, out = tool("brd.py", "render", os.path.join(d, "brd.yaml")); md = open(os.path.join(d, "brd.md"), encoding="utf-8").read()
        self.assertIn("## 6. Performance requirements", md); self.assertIn("Authorisation to test", md)
        self.assertIn("RAG rules", md); self.assertIn("Green", md); self.assertIn("Entry criteria", md)
        self.assertIn("user counts for each load step", md)
    def test_profile_parameters_are_required_only_when_profile_is_needed(self):
        d = make_project(self.tmp); path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(path, encoding="utf-8"))
        brd["test_types"][3]["needed"] = True
        brd["test_types"][3]["parameters"] = {}
        write(path, yaml.safe_dump(brd, sort_keys=False))
        rc, out = tool("brd.py", "check", path)
        self.assertEqual(rc, 1)
        self.assertIn("Spike profile: spike user count", out)
        self.assertIn("Spike profile: abort decision owner", out)
        self.assertIn("Spike profile: entry and exit criteria", out)

        brd["test_types"][3]["needed"] = False
        write(path, yaml.safe_dump(brd, sort_keys=False))
        rc, out = tool("brd.py", "check", path)
        self.assertEqual(rc, 0, out)
    def test_profile_parameter_requires_traceable_evidence(self):
        d = make_project(self.tmp); path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(path, encoding="utf-8"))
        brd["evidence"] = [item for item in brd["evidence"] if item["field"] != "test_types[1].parameters.steps"]
        write(path, yaml.safe_dump(brd, sort_keys=False))
        rc, out = tool("brd.py", "check", path)
        self.assertEqual(rc, 1)
        self.assertIn("Evidence for test_types[1].parameters.steps", out)
    def test_omitted_profile_is_reported_as_a_scope_gap(self):
        d = make_project(self.tmp); path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(path, encoding="utf-8"))
        brd["test_types"] = [item for item in brd["test_types"] if item["type"] != "Scalability"]
        brd["evidence"] = [item for item in brd["evidence"] if item["field"] != "test_types[5].needed"]
        write(path, yaml.safe_dump(brd, sort_keys=False))
        rc, out = tool("brd.py", "check", path)
        self.assertEqual(rc, 1)
        self.assertIn("Test type 'Scalability': confirm whether it is needed (yes/no)", out)
    def test_endurance_window_and_data_volume_come_from_active_environment(self):
        d = make_project(self.tmp); brd_path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(brd_path, encoding="utf-8"))
        brd["test_types"][4]["needed"] = True
        brd["test_types"][4]["parameters"] = {"users": 10, "duration": "10m", "ramp_down": "30s", "flows": ["T1", "T2", "T3"]}
        brd["exit_criteria"].append({
            "profile": "Endurance (soak)",
            "start_when": "Environment is ready",
            "finish_when": "Agreed duration completes",
        })
        brd["evidence"].extend([
            {"field": "test_types[4].parameters.users", "source": "test fixture"},
            {"field": "test_types[4].parameters.duration", "source": "test fixture"},
            {"field": "test_types[4].parameters.ramp_down", "source": "test fixture"},
            {"field": "test_types[4].parameters.flows", "source": "test fixture"},
            {"field": "exit_criteria[1].start_when", "source": "test fixture"},
            {"field": "exit_criteria[1].finish_when", "source": "test fixture"},
        ])
        write(brd_path, yaml.safe_dump(brd, sort_keys=False))
        rc, out = tool("brd.py", "check", brd_path)
        self.assertEqual(rc, 1)
        self.assertIn("Endurance test window in environments.yaml", out)
        self.assertIn("Endurance data volume in environments.yaml", out)

        env_path = os.path.join(d, "environments.yaml")
        envs = yaml.safe_load(open(env_path, encoding="utf-8"))
        envs["environments"]["local"]["endurance"] = {
            "test_window": "Reserved evening window",
            "data_volume": "Seeded synthetic dataset",
        }
        write(env_path, yaml.safe_dump(envs, sort_keys=False))
        rc, out = tool("brd.py", "check", brd_path)
        self.assertEqual(rc, 0, out)
        rc, out = tool("brd.py", "render", brd_path)
        self.assertEqual(rc, 0, out)
        rendered = open(os.path.join(d, "brd.md"), encoding="utf-8").read()
        self.assertIn("Reserved evening window", rendered)
        self.assertIn("Seeded synthetic dataset", rendered)
    def test_unconfirmed_authorisation_is_a_gap(self):
        d = make_project(self.tmp, auth="not_confirmed"); rc, out = tool("brd.py", "check", os.path.join(d, "brd.yaml")); self.assertEqual(rc, 1); self.assertIn("not_confirmed", out)
    def test_environment_rules(self):
        import envconf
        ok = {"type": "local", "base_url": "http://h:1", "owner": "me", "authorisation": "not_required", "max_vus": 5, "max_run_minutes": 5, "monitoring": {"source": "none"}}
        good = {"active": "a", "environments": {"a": ok}}; self.assertEqual(envconf.problems(good)[0], [])
        bad = {"active": "a", "environments": {"a": {**ok, "type": "public"}}}; self.assertTrue(any("not_required" in p for p in envconf.problems(bad)[0]))
        bad = {"active": "a", "environments": {"a": {**ok, "base_url": "http://user:pw@h"}}}; self.assertTrue(envconf.problems(bad)[0])
        bad = {"active": "a", "environments": {"a": {**ok, "monitoring": {"source": "docker_stats"}}}}; self.assertTrue(any("containers" in p for p in envconf.problems(bad)[0]))
        bad = {"active": "a", "environments": {"a": {**ok, "credentials_env_vars": ["hunter2pass"]}}}; self.assertTrue(envconf.problems(bad)[0])
        bad = {"active": "a", "environments": {"a": {**ok, "authorisation": "accepted_by_test_lead"}}}; self.assertTrue(any("authorisation_note" in p for p in envconf.problems(bad)[0]))
        bad = {"active": "a", "environments": {"a": {**ok, "endurance": "not a mapping"}}}; self.assertTrue(any("endurance must be a mapping" in p for p in envconf.problems(bad)[0]))


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
    def test_har_excludes_third_party_and_redacts(self):
        har = os.path.join(self.tmp, "c.har")
        json.dump({"log": {"entries": [
            {"time": 10, "_resourceType": "xhr", "request": {"method": "GET", "url": "https://api.example.com/brands?access_token=unique-query-secret-1234&state=state-query-secret-5678", "headers": [{"name": "Authorization", "value": "Bearer abcdefghijklmnopqrstuvwxyz"}]}, "response": {"status": 200, "content": {"mimeType": "application/json", "text": "[{\"id\":1}]"}}},
            {"time": 3, "_resourceType": "script", "request": {"method": "GET", "url": "https://api.example.com/assets/app.js?signature=static-query-secret-1234", "headers": []}, "response": {"status": 200, "headers": [{"name": "Cache-Control", "value": "public, max-age=3600"}], "content": {"mimeType": "application/javascript", "text": "/* app */"}}},
            {"time": 5, "_resourceType": "xhr", "request": {"method": "POST", "url": "https://www.google-analytics.com/collect", "headers": []}, "response": {"status": 200, "content": {"mimeType": "application/json", "text": "{}"}}}]}}, open(har, "w"))
        tool("catalogue.py", "import-har", self.cat, har, "https://api.example.com"); d = yaml.safe_load(open(self.cat))
        self.assertEqual(len(d["apis"]), 1); self.assertIn("www.google-analytics.com", d["meta"]["excluded_hosts"]); self.assertNotIn("abcdefghijklmnop", open(self.cat).read())
        text = open(self.cat).read()
        self.assertNotIn("unique-query-secret-1234", text)
        self.assertNotIn("state-query-secret-5678", text)
        self.assertNotIn("static-query-secret-1234", text)
        self.assertEqual([q["example"] for q in d["apis"][0]["query_params"]], ["<redacted>", "<redacted>"])
        self.assertEqual(d["web_tier"]["requests"][0]["kind"], "static_asset")
        self.assertEqual(d["web_tier"]["requests"][0]["path"], "/assets/app.js")
        self.assertEqual(d["web_tier"]["requests"][0]["response"]["cache_control"], "public, max-age=3600")
    def test_web_tier_inventory_is_checked_separately_from_api_flows(self):
        d = make_project(os.path.join(self.tmp, "project"))
        cat_path = os.path.join(d, "api-catalogue.yaml")
        cat = yaml.safe_load(open(cat_path))
        cat["web_tier"] = {"requests": [
            {"id": "WEB-001", "kind": "session", "method": "GET", "path": "/login", "details": {"cookie_names": ["session_id"]}, "response": {"status": 200}, "safe_to_load": "unknown", "evidence": {"source_type": "browser", "source": "login page"}},
            {"id": "WEB-002", "kind": "csrf", "method": "GET", "path": "/csrf", "details": {"token_name": "X-CSRF-Token"}, "response": {"status": 200}, "safe_to_load": "unknown", "evidence": {"source_type": "har", "source": "capture.har"}},
            {"id": "WEB-003", "kind": "static_asset", "method": "GET", "path": "/app.js", "details": {}, "response": {"status": 200, "content_type": "application/javascript"}, "safe_to_load": "unknown", "evidence": {"source_type": "har", "source": "capture.har"}},
        ]}
        yaml.safe_dump(cat, open(cat_path, "w"), sort_keys=False)
        rc, out = tool("catalogue.py", "check", cat_path, os.path.join(d, "brd.yaml"))
        self.assertEqual(rc, 0, out)
        cat["web_tier"]["requests"][1]["kind"] = "page"
        yaml.safe_dump(cat, open(cat_path, "w"), sort_keys=False)
        rc, out = tool("catalogue.py", "check", cat_path, os.path.join(d, "brd.yaml"))
        self.assertEqual(rc, 1)
        self.assertIn("web-tier kind", out)
        cat["web_tier"]["requests"][1]["kind"] = "csrf"
        cat["web_tier"]["requests"][1]["details"] = {"csrf_token": "leaked-token-value-123"}
        yaml.safe_dump(cat, open(cat_path, "w"), sort_keys=False)
        rc, out = tool("catalogue.py", "check", cat_path, os.path.join(d, "brd.yaml"))
        self.assertEqual(rc, 1)
        self.assertIn("Possible secret", out)
    def test_check_flags_unmapped_transaction(self):
        d = make_project(self.tmp + "/p" if False else tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, os.path.dirname(os.path.dirname(os.path.dirname(d))))
        cat = yaml.safe_load(open(os.path.join(d, "api-catalogue.yaml"))); cat["apis"] = [a for a in cat["apis"] if a["transaction"] != "T3"]; yaml.safe_dump(cat, open(os.path.join(d, "api-catalogue.yaml"), "w"))
        rc, out = tool("catalogue.py", "check", os.path.join(d, "api-catalogue.yaml")); self.assertEqual(rc, 1); self.assertIn("T3", out)


class TestK6Check(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp); self.d = make_project(self.tmp)
    def test_good_script_passes(self): rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 0, out)
    def test_wrong_threshold_fails(self):
        p = os.path.join(self.d, "k6", "script.js"); t = open(p).read().replace("p(99)<4000", "p(99)<9000"); open(p, "w").write(t)
        rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 1); self.assertIn("PR-02", out)
    def test_literal_url_and_missing_api_fail(self):
        p = os.path.join(self.d, "k6", "script.js"); t = open(p).read().replace("'API-006'", "'API-099'") + "\nconst X = 'https://evil.example.com';\n"; open(p, "w").write(t)
        rc, out = tool("k6check.py", self.d); self.assertEqual(rc, 1); self.assertIn("API-006", out); self.assertIn("literal URL", out)
    def test_needed_profile_must_have_a_scenario(self):
        brd_path = os.path.join(self.d, "brd.yaml")
        brd = yaml.safe_load(open(brd_path, encoding="utf-8"))
        brd["test_types"][2]["needed"] = "yes"
        brd["test_types"][2]["parameters"] = {"start_users": 1, "step_size": 1, "step_hold": "1m",
                                               "stop_rule": "abort conditions", "recovery_observation": "1m", "flows": ["T1"]}
        write(brd_path, yaml.safe_dump(brd, sort_keys=False))
        script = os.path.join(self.d, "k6", "script.js")
        text = open(script, encoding="utf-8").read().replace("} else if (PROFILE === 'stress') {", "} else if (PROFILE === 'stress-missing') {")
        write(script, text)
        rc, out = tool("k6check.py", self.d)
        self.assertEqual(rc, 1)
        self.assertIn("Stress is needed but has no scenario", out)

class TestProfilesBaselineAndCoverage(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp)

    def _baseline_config(self, d):
        path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(path, encoding="utf-8"))
        brd["test_types"][0]["needed"] = "yes"
        brd["test_types"][0]["parameters"] = {
            "users": 1, "repeat_runs": 3, "max_variance_pct": 10, "flows": ["T1", "T2", "T3"],
        }
        write(path, yaml.safe_dump(brd, sort_keys=False))
        return brd

    def test_baseline_requires_three_consistent_runs_and_records_signoff(self):
        import baseline, runk6
        d = make_project(self.tmp, runs=[
            ("b1", "baseline", 1, "passed", 100),
            ("b2", "baseline", 1, "passed", 100),
            ("b3", "baseline", 1, "passed", 100),
        ])
        brd = self._baseline_config(d)
        result = baseline.check(d)
        self.assertTrue(result["consistent"], result)
        baseline.save(d, result)
        rc, out = tool("baseline.py", "sign-off", d, "--by", "QA lead", "--date", "2026-11-21")
        self.assertEqual(rc, 0, out)
        self.assertTrue(runk6.baseline_is_signed_off(d, "local", brd))

    def test_baseline_outlier_fails_variance_limit(self):
        import baseline
        d = make_project(self.tmp, runs=[
            ("b1", "baseline", 1, "passed", 100),
            ("b2", "baseline", 1, "passed", 100),
            ("b3", "baseline", 1, "passed", 300),
        ])
        self._baseline_config(d)
        result = baseline.check(d)
        self.assertFalse(result["consistent"])
        self.assertIn("variance limit", result["reason"])

    def test_load_guard_uses_brd_steps_and_smoke_prerequisite(self):
        import runk6
        d = make_project(self.tmp)
        brd = yaml.safe_load(open(os.path.join(d, "brd.yaml"), encoding="utf-8"))
        _, env = __import__("envconf").get_env(d)
        cfg = runk6.profile_config(d, brd, "load", env, 10)
        self.assertEqual(cfg["flows"], ["T1", "T2", "T3"])
        self.assertEqual([x[0] for x in cfg["stages"]], [5, 10, 10, 0])
        with self.assertRaisesRegex(ValueError, "passed smoke"):
            runk6.check_run_guards(d, "load", cfg, brd, "local", [])

    def test_coverage_matrix_reflects_selected_and_passed_flows(self):
        import coverage as coverage_tool
        d = make_project(self.tmp, runs=[("r-load", "load", 5, "passed", 80)])
        path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(path, encoding="utf-8"))
        brd["test_types"][1]["parameters"]["flows"] = ["T1"]
        write(path, yaml.safe_dump(brd, sort_keys=False))
        matrix = coverage_tool.compute(d, "local")["matrix"][0]["cells"]
        self.assertEqual({x["flow"]: x["status"] for x in matrix},
                         {"T1": "covered", "T2": "not_selected", "T3": "not_selected"})
    def test_spike_uses_brd_peak_without_the_ramp_step_guard(self):
        import runk6
        d = make_project(self.tmp)
        path = os.path.join(d, "brd.yaml")
        brd = yaml.safe_load(open(path, encoding="utf-8"))
        brd["test_types"][3].update({
            "needed": "yes",
            "parameters": {
                "base_users": 2, "spike_users": 15, "spike_duration": "30s",
                "recovery_window": "1m", "autoscaling_config": "unknown", "ramp_down": "30s", "flows": ["T2"],
            },
        })
        brd["operational_safety"] = {
            "abort_owner": "Operations", "rollback_owner": "Operations",
            "rollback_procedure": "Documented", "on_call_contact": "On call",
        }
        write(path, yaml.safe_dump(brd, sort_keys=False))
        _, env = __import__("envconf").get_env(d)
        cfg = runk6.profile_config(d, brd, "spike", env, None)
        self.assertEqual(cfg["vus"], 15)
        self.assertEqual(cfg["flows"], ["T2"])
        self.assertEqual(cfg["stages"][:2], [(15, 30), (2, 60)])
        self.assertTrue(runk6.check_run_guards(d, "spike", cfg, brd, "local",
                                               [{"profile": "smoke", "outcome": "passed"}]))
        brd["operational_safety"]["on_call_contact"] = ""
        with self.assertRaisesRegex(ValueError, "on_call_contact"):
            runk6.profile_config(d, brd, "spike", env, None)


class TestReportAndPack(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp)
    def test_below_peak_is_not_judged(self):
        import report; d = make_project(self.tmp, runs=[("r-load-5", "load", 5, "passed", 80)]); page, f = report.build(d, "r-load-5")
        st = {x["r"]["id"]: x["status"] for x in f["res"]}
        self.assertEqual(st["PR-01"], "Not measured at peak load"); self.assertEqual(st["PR-04"], "Deferred"); self.assertIn("deferred", f["vsub"]); self.assertEqual(f["vcls"], "warn")
    def test_at_peak_is_met_or_not_met(self):
        import report; d = make_project(self.tmp, runs=[("r-ok", "load", 10, "passed", 80), ("r-slow", "load", 10, "passed", 2500)])
        a = {x["r"]["id"]: x["status"] for x in report.build(d, "r-ok")[1]["res"]}; b = {x["r"]["id"]: x["status"] for x in report.build(d, "r-slow")[1]["res"]}
        self.assertEqual((a["PR-01"], a["PR-03"]), ("Met", "Met")); self.assertEqual(b["PR-01"], "Not met")
    def test_report_contains_metric_set_rag_coverage_and_analysis_framework(self):
        import report
        d = make_project(self.tmp, runs=[("r1", "load", 10, "passed", 80)])
        page, facts = report.build(d, "r1")
        self.assertIn("p50", page)
        self.assertIn("throughput (TPS)", page)
        self.assertIn("Database metrics", page)
        self.assertIn("Not collected", page)
        self.assertIn("Overall RAG: Grey", page)
        self.assertIn("Profile-by-flow coverage", page)
        self.assertIn("Observation", page)
        self.assertIn("Hypothesis", page)
        self.assertEqual(facts["rag"], "Grey")
    def test_saturation_detector_requires_latency_and_error_increase_with_flat_tps(self):
        import report
        def metrics(p95, tps, errors):
            return {
                "transaction_duration{transaction:T1}": {"p(95)": p95},
                "http_reqs": {"rate": tps},
                "http_req_failed": {"value": errors},
            }
        history = [
            ("r1", {"vus": 5}, metrics(100, 10, 0.01)),
            ("r2", {"vus": 10}, metrics(150, 10, 0.02)),
        ]
        self.assertEqual(report.saturation_observation(history)["run_id"], "r2")
        history[1][2]["http_req_failed"]["value"] = 0.01
        self.assertIsNone(report.saturation_observation(history))
    def test_failed_run_banner_names_the_error(self):
        import report; d = make_project(self.tmp, runs=[("r-err", "load", 10, "error", 80)]); open(os.path.join(d, "runs", "r-err", "k6-output.txt"), "w").write('time="x" level=error msg="Error: setup failed: no ids found" hint="script exception"\n')
        f = report.build(d, "r-err")[1]; self.assertIn("failed before", f["vtxt"]); self.assertIn("setup failed", f["vsub"])
    def test_clientpack_builds_and_stops_on_secret(self):
        d = make_project(self.tmp, runs=[("r1", "smoke", 1, "passed", 50), ("r2", "load", 10, "passed", 80)])
        rc, out = tool("clientpack.py", d); self.assertEqual(rc, 0, out); pack = os.path.join(d, "client-pack"); names = os.listdir(pack)
        folder = [n for n in names if not n.endswith(".zip")][0]; self.assertTrue(any(n.endswith(".zip") for n in names))
        for f in ("index.html", "brd.html", "manifest.json"): self.assertTrue(os.path.exists(os.path.join(pack, folder, f)), f)
        self.assertIn("r2", folder)
        cover = open(os.path.join(pack, folder, "index.html"), encoding="utf-8").read()
        self.assertIn("Coverage matrix", cover)
        self.assertIn("Exit-criteria status", cover)
        open(os.path.join(d, "runs", "r2", "k6-output.txt"), "a").write("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij\n")
        rc, out = tool("clientpack.py", d); self.assertNotEqual(rc, 0); self.assertIn("Secret-like", out)
    def test_clientpack_rejects_explicit_non_load_or_failed_run(self):
        d = make_project(self.tmp, runs=[
            ("r-smoke", "smoke", 1, "passed", 50),
            ("r-failed", "load", 10, "thresholds_failed", 80),
        ])
        for rid in ("r-smoke", "r-failed"):
            rc, out = tool("clientpack.py", d, "--run", rid)
            self.assertNotEqual(rc, 0)
            self.assertIn("not a passed load run", out)
    def test_status_walks_the_stages(self):
        d = make_project(self.tmp, runs=[]); rc, out = tool("status.py", d, "--json"); j = json.loads(out)
        self.assertEqual([s["done"] for s in j["stages"]][:3], [True, True, True]); self.assertEqual(j["next"]["n"], 4)
        e = os.path.join(self.tmp, "projects", "New", "app"); os.makedirs(e); rc, out = tool("status.py", e, "--json"); self.assertEqual(json.loads(out)["next"]["n"], 1)
    def test_status_invalidates_target_check_after_environment_url_change(self):
        d = make_project(self.tmp)
        write(os.path.join(d, "target-check.json"), json.dumps({
            "environment": "local", "base_url": "http://different.example",
            "calls_ok": 7, "calls_differ": 0, "calls_skipped": 0,
        }))
        rc, out = tool("status.py", d, "--json")
        status = json.loads(out)
        target_stage = next(s for s in status["stages"] if s["n"] == 4)
        self.assertFalse(target_stage["done"])
        self.assertIn("environment URL changed", target_stage["detail"])


class TestMonitor(unittest.TestCase):
    def test_parse_and_summarise(self):
        import monitor
        self.assertEqual(monitor.parse_line("api|12.5%|45.2MiB / 7.6GiB|0.6%")["mem_mib"], 45.2); self.assertIsNone(monitor.parse_line("garbage"))
        s = [{"t_s": t, "series": "a", "cpu_pct": c, "mem_mib": 10} for t, c in [(0, 90), (10, 20), (20, 30), (30, 40), (40, 5)]]
        r = monitor.summarise(s, [10, 30])["a"]; self.assertEqual(r["cpu_avg"], 30.0); self.assertEqual(r["cpu_max_run"], 90.0)
    def test_visibility_requires_a_configured_live_source(self):
        import monitor
        self.assertIn("No monitoring source", monitor.check_visibility("none", ["app"])[1])
        self.assertIn("not built", monitor.check_visibility("azure", ["app"])[1])
        with patch.object(monitor, "docker_sample", return_value=([{"series": "app"}], None)):
            rows, err = monitor.check_visibility("docker_stats", ["app"])
            self.assertEqual(len(rows), 1); self.assertIsNone(err)
        with patch.object(monitor, "docker_sample", return_value=([], "docker is unavailable")):
            rows, err = monitor.check_visibility("docker_stats", ["app"])
            self.assertEqual(rows, []); self.assertEqual(err, "docker is unavailable")


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, o, c=200): b = json.dumps(o).encode(); self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/items/a": return self._s({"id": "a"})
        if self.path == "/brands": return self._s([{"id": 1}])
        self._s({"e": 1}, 404)
    def do_QUERY(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n); self._s({"data": [{"id": "a"}]}) if self.path == "/items" else self._s({"e": 1}, 404)

class TestTargetCheck(unittest.TestCase):
    def test_check_one_encodes_query_and_matches_each_dynamic_path_value(self):
        import targetcheck
        api = {
            "id": "API-003", "method": "GET", "path": "/items/{id}/locales/{locale}",
            "safe_to_load": "yes", "auth": "none",
            "dynamic_values": [
                {"name": "id", "from_api": "API-001", "json_path": "id"},
                {"name": "locale", "from_api": "API-001", "json_path": "locale"},
            ],
            "query_params": [{"name": "filter", "example": "a&b c", "required": True}],
            "response": {"status": 200},
        }
        with patch.object(targetcheck, "call", return_value=(200, {}, 5, None)) as request:
            result = targetcheck.check_one(api, "http://example.test", {"API-001": {"id": "p/1", "locale": "en US"}})
        self.assertEqual(result["result"], "ok")
        request.assert_called_once_with("http://example.test", "GET", "/items/p%2F1/locales/en%20US?filter=a%26b+c", None)

    def test_check_one_requires_example_for_required_query(self):
        import targetcheck
        api = {"id": "API-001", "method": "GET", "path": "/items", "safe_to_load": "yes", "auth": "none",
               "query_params": [{"name": "page", "example": "", "required": True}], "response": {"status": 200}}
        with patch.object(targetcheck, "call") as request:
            result = targetcheck.check_one(api, "http://example.test", {})
        self.assertEqual(result["result"], "skipped")
        self.assertIn("page", result["detail"])
        request.assert_not_called()

    def test_check_one_requires_exact_catalogue_status(self):
        import targetcheck
        api = {"id": "API-001", "method": "GET", "path": "/items", "safe_to_load": "yes", "auth": "none", "response": {"status": 200}}
        with patch.object(targetcheck, "call", return_value=(201, {}, 5, None)):
            result = targetcheck.check_one(api, "http://example.test", {})
        self.assertEqual(result["result"], "differs")
        self.assertIn("catalogue says 200", result["detail"])

    def test_refuses_cross_origin_redirect(self):
        hits = []
        class DestinationHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200); self.end_headers()
            def log_message(self, *a): pass
        destination = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)
        threading.Thread(target=destination.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (destination.shutdown(), destination.server_close()))

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", target)
                self.end_headers()
            def log_message(self, *a): pass
        target = f"http://127.0.0.1:{destination.server_address[1]}/redirected"
        source = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        threading.Thread(target=source.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (source.shutdown(), source.server_close()))

        import targetcheck
        status, _, _, _ = targetcheck.call(f"http://127.0.0.1:{source.server_address[1]}", "GET", "/start", None)
        self.assertEqual(status, 302)
        self.assertEqual(hits, [])

    def test_redirect_must_stay_on_exact_configured_origin(self):
        import targetcheck
        handler = targetcheck.SameOriginRedirectHandler("https://app.example.test")
        request = targetcheck.urllib.request.Request("https://app.example.test/start")
        self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, "https://app.example.test.attacker.test/next"))
        self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, "https://user@app.example.test/next"))
        off_target = targetcheck.urllib.request.Request("https://other.example.test/start")
        self.assertIsNone(handler.redirect_request(off_target, None, 302, "Found", {}, "https://other.example.test/next"))

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
        target_result = json.load(open(os.path.join(d, "target-check.json")))
        self.assertEqual(target_result["calls_ok"], 3)
        self.assertEqual(target_result["base_url"], f"http://127.0.0.1:{srv.server_address[1]}")
    def test_refuses_when_not_confirmed(self):
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp); d = make_project(tmp, auth="not_confirmed"); rc, out = tool("targetcheck.py", d); self.assertNotEqual(rc, 0); self.assertIn("not_confirmed", out)


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
