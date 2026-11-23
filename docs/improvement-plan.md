# Improvement plan

Status: Phase 1, environment-readiness, API-catalogue, and target-validation improvements are implemented on branch `improve/performance-harness`; work remains uncommitted. The HAR importer redacts every query value and records static assets separately. Target checks encode required query values, match dynamic path placeholders by name, and compare exact statuses. Session/CSRF metadata remains evidence-driven and is not executable by k6 yet.
Purpose: a self-contained brief so any new chat can continue the work without the old conversation. Read it fully, then follow "How to resume" at the end.

Note on repo rule 17 ("no extra documents"): this file exists because the user explicitly asked for it. When the plan is finished, delete it or fold the useful parts into `docs/overview.md`.
This plan and `docs/screenshots/` are local working material; do not commit them unless the user changes that instruction.

## 1. Context

- The harness takes a QA lead from client requirements to a client pack (BRD → environment → API catalogue → target check → k6 script → smoke → load → monitoring → report → client pack). All stages work for the local Docker case. See `README.md`, `docs/overview.md` and `.github/copilot-instructions.md` (rules 1-17 are binding).
- `tools/status.py` is the source of truth for stage state. `tools/lint.py` and `python -m unittest discover -s tests` must pass after any change to `tools/`, `.github/` or `templates/` (rule 16). Never weaken a check to make it pass.
- Python setup: PyYAML is pinned in `requirements.txt`; on this Mac use the repo `.venv` (`.venv/bin/python -m unittest discover -s tests`). The unit test that invokes `tools/lint.py` passed, and running it with `-v` reported `LINT: OK`, but a plain `.venv/bin/python tools/lint.py` invocation intermittently failed to import `yaml`; investigate before closing task 0.6.
- Example project: `projects/ToolShop/practicesoftwaretesting/` (local Docker demo, 7 read APIs, load runs up to 50 users, client pack built). The HRM project is independent of this improvement work. Its uncommitted deletions are intentionally left alone; do not inspect, restore, stage, or commit them as part of this plan.

## 2. Decisions already made by the user

1. The screenshots in `docs/screenshots/` are SAMPLES from a proposal for a different client ("Yara"). They are not requirements for this repo. Never hard-code a client name or its commitments.
2. This is a reusable harness. Whenever a new project arrives, requirements come from the client through the BRD. Anything a profile or report needs must be captured in the BRD, or asked as a gap question. It must not be guessed or fixed in code.
3. Which load profiles are in scope is decided per project in the BRD (`test_types`), asked of the client if blank. The harness must support every profile and enforce nothing the BRD did not ask for.
4. RAG thresholds: the assistant recommends. Use the recommendation in section 4; do not implement it until the user confirms the model.
5. Real-client monitoring (APM) is built when a project needs it. Until then keep the collector interface generic.
6. This plan and the screenshot samples stay local and must not be committed.

## 3. Findings from the repo review

### Correctness and safety bugs (fix first)

| # | Priority | Where | Problem |
|---|---|---|---|
| B1 | P1 | `tools/catalogue.py` `import_har`, `query_params` | Resolved: HAR query values are always redacted, including values under nonsensitive parameter names; tests cover API and static-asset URLs. |
| B2 | P1 | `tools/clientpack.py` `choose()` | `--run <id>` returns the run without checking it is a passed load run, so a pack can be built for a failed, aborted or smoke run. Default selection already requires passed load. |
| B3 | P2 | `tools/status.py` stage 4 | Target check is "current" if the environment name matches and the catalogue is older. It ignores a changed `base_url`. Compare the stored `base_url` with the environment's. |
| B4 | P2 | `tools/targetcheck.py` `call()` | `urlopen` follows redirects, so a request can leave the configured host. Refuse redirects to another host (or do not follow). |
| B5 | P3 | `docs/overview.md` | Says monitoring, report and pack are "not built yet"; the README says they are. The ToolShop section is also stale (says load has not been run). |
| B6 | P3 | repo | No CI, no pinned `requirements.txt`. |

### Capability gaps (the real work)

- k6 skeleton `.github/skills/k6-script-builder/reference-skeleton.js` has only two scenarios: `smoke` and a single ramp-hold-ramp-down `load`.
- `templates/brd.template.yaml` lists `test_types` (Baseline, Load, Stress, Spike, Endurance, Scalability) and has an empty `exit_criteria: []`, but no tool reads either. There are no per-profile parameters.
- `tools/runk6.py` only knows `--profile smoke|load` and the "first load max 5, then 2x" step rule. That rule suits a ramp. It does not fit baseline, spike, stress or endurance.
- No baseline-consistency check (repeat runs and variance), no saturation-point detection, no RAG, no run-over-run comparison, no structured findings section.
- Monitoring: only `docker_stats` is built (`tools/monitor.py`). Azure, Dynatrace and client APM are not.
- The catalogue has a separate `web_tier.requests` inventory for session, CSRF, and static-asset observations. It is not part of API transaction flows or k6 execution yet.
- Coverage (profile × flow) is not tracked anywhere.

## 4. RAG recommendation (proposed; confirm before implementation)

Recommendation: **do not use amber to soften a failed measurable requirement.** It creates a second, informal threshold and can make a failed SLO look like a pass. Compare each metric strictly with the target the client agreed in the BRD; show the measured value alongside the target. No default tolerance percentages or multipliers.

Use the following report semantics:

- **Per requirement: Green / Met** only when measured at the agreed peak load and the exact BRD threshold is met.
- **Per requirement: Red / Not met** when measured at the agreed peak load and the threshold is missed, or a run abort threshold fires.
- **Per requirement: Grey / Not assessed** when it was not measured at peak, is deferred, or the run failed before usable results. Never colour below-peak results green.
- **Overall Green** when every Must requirement is measured at peak and met, and no agreed operational warning is active.
- **Overall Red** when any Must requirement is measured and missed, or an abort threshold fires.
- **Overall Grey** when a Must requirement has no valid peak-load evidence and none of the measured Must requirements has failed. State which evidence is missing.
- **Overall Amber** only when all Must requirements are met, but a non-Must requirement is not met or an explicitly agreed warning condition is present. The warning condition must be named in the BRD; the harness must not invent one. Amber is a caution, never a partial pass.

When multiple overall conditions apply, use precedence **Red → Grey → Amber → Green** so a missing critical measurement cannot be hidden by a green result. Keep the existing textual outcomes (Met / Not met / Not assessed) as the authoritative requirement result; RAG is a visual summary, not a substitute for the measured value.

This model avoids asking clients to agree arbitrary "near miss" tolerances. It needs no new numeric RAG threshold. If the client wants a warning band or other amber trigger, capture its exact condition, owner and evidence source in the BRD and ask about it as a gap when unclear. Until the user confirms this recommendation, retain current Met / Not met reporting and do not implement new RAG logic.

## 5. Target design

### 5.1 BRD additions (template `templates/brd.template.yaml`, checked by `tools/brd.py`)

Keep the existing structure. Add only what a profile or the report cannot work without. Every new field is blank by default, appears in `brd.py check` only when its profile is marked `needed: yes`, and is asked as a gap question.

- `test_types[]` gains structured parameters. Per profile, only when `needed: yes`:
  - Baseline: `users` (default meaning 1 user, stated), `repeat_runs`, `max_variance_pct`.
  - Load / stepped ramp: `steps` (user counts), `step_hold`, `peak_hold`.
  - Stress: `start_users`, `step_size`, `step_hold`, `stop_rule` (links to abort conditions), `recovery_observation`.
  - Spike: `base_users`, `spike_users`, `spike_duration`, `recovery_window`, `autoscaling_config` (known or unknown).
  - Endurance: BRD holds `users` and `duration`; the active environment's `environments.yaml` holds the reserved `endurance.test_window` and available `endurance.data_volume`.
  - Scalability: out of scope for the first release; stays a yes/no with notes.
- `abort_conditions[]` and stakeholders: add `rollback_procedure` and `on_call_contact` (required for stress and spike).
- Environment: include endurance-specific `test_window` and `data_volume` under each environment. When Endurance is needed, BRD checks require these from the active environment. Baseline entry requires a successful visible-monitoring preflight.
- `exit_criteria[]`: make it structured, `{profile, start_when, finish_when}`. The sample table shows the idea. The harness checks only the criteria it can verify from files (for example baseline variance). Others stay human confirmations.
- `rag_rules` and `reporting` as in section 4.
- `flows`/coverage: reuse the catalogue `flows` and BRD `transactions`. Coverage is computed, not typed in.

### 5.2 Profiles in k6

- Extend the script builder skill and skeleton with one scenario builder per profile, selected by `PROFILE` (`smoke | baseline | load | stress | spike | endurance`). Parameters arrive from `runk6.py` as `-e` values. The script never contains a URL and always has the VU cap and abort thresholds (rule 9; `k6check.py` must keep enforcing these).
- `k6check.py` additionally checks that each BRD profile marked needed has a scenario, and that abort thresholds exist for stress and spike.

### 5.3 Run guards (`tools/runk6.py`)

- `--profile` accepts the new profiles. Per-profile guards, all read from the BRD and `environments.yaml`, never typed:
  - baseline needs a passed smoke; load/ramp needs a baseline signed off (see 5.4) when the BRD marks baseline as needed.
  - stress and spike refuse to run unless the BRD has `rollback_procedure`, `on_call_contact` and the abort conditions, AND the environment authorisation allows it. Stress and spike must never exceed `max_vus`.
  - endurance refuses unless the active environment provides its reserved test window and available data volume, and `max_run_minutes` allows the duration. The cap is changed only by the user in the environment config.
  - The 2x step rule stays for ramp/stress steps. `--force-step` still needs the user's explicit approval.
- `run.json` records profile parameters, so reports and comparisons are reproducible.

### 5.4 Baseline consistency (new tool or `status.py` extension)

- Compute variance of the key metrics across N consecutive passed baseline runs. Record the result in a small file inside the project (not by hand). Candidate name: `baseline-check.json`, written by a new `tools/baseline.py`. A baseline counts as "consistent" only when the BRD's `repeat_runs` and `max_variance_pct` are satisfied. Never mark it done by hand (rule 15).

### 5.5 Report and analysis (`tools/report.py`)

- Standard metric set in every report: p50/p90/p95/p99, throughput, error rate, CPU, memory (DB only when a source provides it; say "not collected" otherwise, rule 13).
- RAG per requirement and overall, from `rag_rules` (section 4).
- Saturation point detector: for stepped ramp and stress, flag the first step where latency rises while throughput is flat and errors rise. Report it as an observation with the numbers, never as a root cause (rule 12).
- Run-over-run comparison table (same metrics, same percentiles) for runs of the same profile.
- Findings block with fixed headings Observe → Isolate layer → Hypothesis → Evidence → Finding. The tool fills "Observe" and "Evidence" from data. "Hypothesis" and "Finding" stay empty, to be filled only by a human, and the report says so.
- Coverage matrix (profile × flow) computed from `runs/` and shown in the report and the client pack.

### 5.6 Monitoring collectors

- Keep `tools/monitor.py` as the single entry. Define a small collector interface (`check`, `start`, `stop`, output format identical to `monitoring.json`). Add Azure Monitor / Dynatrace collectors only when a real project names its APM and gives access. Until then the report must keep saying plainly that the source is not built (rule 13).

### 5.7 Out of scope for now

- Executable E2E web-tier and browser tests (inventory metadata is now supported; execution remains a separate stream).
- Scalability tests.
- CI/CD integration beyond the repo's own lint/tests CI.

## 6. Phases

Each phase ends with lint and tests green (rule 16), tests added for every new behaviour, and README/overview updated. One phase per chat or PR, in this order.

### Phase 0: fixes and hygiene (small, do first)

- 0.1 B1: redact all HAR query-string values; add tests for sensitive and ordinary parameter names and static-asset URLs. Complete.
- 0.2 B2: `clientpack --run` must require a passed load run; add a test.
- 0.3 B3: store and compare `base_url` in target-check; add a test.
- 0.4 B4: block cross-host redirects in `targetcheck.py`; add a test (local server that redirects).
- 0.5 B5: rewrite `docs/overview.md` to match the README; remove stale ToolShop claims.
- 0.6 B6: add `requirements.txt` (PyYAML) and a GitHub Actions workflow running lint and tests. Investigate why `.venv/bin/python tools/lint.py` could not import `yaml` while an in-process call worked (likely `sys.path`/shebang/environment); fix at the cause.
- Acceptance: all tests pass, lint OK, CI green.

### Phase 1: BRD profile model and gap questions

- Update the template and `tools/brd.py` (`check`, `render`) with the section 5.1 fields; missing items appear only for profiles marked needed.
- Update the `requirements-intake` and `brd-builder` skills so Copilot asks the new gap questions in groups of at most 5 and records answers with `evidence`.
- Add `rag_rules` and structured `exit_criteria`.
- Acceptance: a BRD with Spike needed and no spike parameters lists them as missing; a BRD without spike never asks about it. `templates/` stays untouched per project.

### Phase 2: profiles in the script and run guards

- Skeleton and `k6-script-builder` skill: profile scenarios. `k6check.py`: profile checks.
- `runk6.py`: new profiles and per-profile guards (5.3). `status.py`: stage 6/7 understand profiles and show per-profile progress.
- Acceptance: each profile has a generated script that passes `k6check.py`; guards refuse correctly (tests that need k6 are skipped when k6 is missing).

### Phase 3: baseline consistency and coverage

- `tools/baseline.py` (5.4); coverage computation shared by `status.py`, `report.py`, `clientpack.py`.
- Acceptance: three runs within the variance pass; one outlier fails; status shows the result.

### Phase 4: report upgrades

- Standard metrics, RAG, saturation observation, run-over-run comparison, findings block, coverage matrix (5.5). Client pack includes them.
- Acceptance: golden-file style tests on synthetic runs; no sentence in a report claims a cause; below-peak runs are never green.

### Phase 5: monitoring collectors (only when a project needs them)

- Collector interface refactor, then the chosen APM collector. Needs a real environment and access; do not start without the user's go-ahead and the client's APM details.

### Phase 6 (later): E2E web-tier execution

- The catalogue now stores separate session, CSRF and static-asset observations. Plan HAR-based protocol scripts with correlation and optional browser checks for critical journeys later.

## 7. Open questions for the user

1. Confirm or adjust the RAG model in section 4 before Phase 4 is implemented.
2. Is the first real engagement already known? If yes, which APM does it use (decides Phase 5)?

## 8. How to resume in a new chat

1. Read this file, `.github/copilot-instructions.md`, and `README.md`.
2. Run `git status` and `git log --oneline -10` to see what is already done; tick off finished tasks below.
3. Ask the user which phase to start (default: Phase 0). Do not implement beyond the chosen phase.
4. For each change: make it, add tests, run `.venv/bin/python -m unittest discover -s tests` and lint, and show the user the result.
5. Never invent client values, never change `authorisation`, never run load without the user's chosen users, and keep reports free of hand-written conclusions.

### Progress tracker (update as work is done)

- [ ] Phase 0 fixes (0.1-0.6); 0.1-0.5 are implemented, 0.6 is implemented except for resolving the intermittent local lint invocation. Target checking also has focused coverage for encoding, placeholder matching, and exact statuses.
- [x] Phase 1 BRD profile model; profile scope, conditional fields, evidence, criteria, operational safety fields, fixed RAG policy, environment-owned endurance readiness, and monitoring visibility preflight implemented and tested.
- [ ] Phase 2 profiles and run guards
- [ ] Phase 3 baseline and coverage
- [ ] Phase 4 report upgrades
- [ ] Phase 5 monitoring collectors
- [ ] Phase 6 E2E stream
