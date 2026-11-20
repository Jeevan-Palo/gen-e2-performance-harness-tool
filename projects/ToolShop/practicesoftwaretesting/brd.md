# Business Requirements Document: Performance Testing

| Field | Value |
|---|---|
| Client / business unit | ToolShop (Practice Software Testing, Testsmith) |
| Application / system | Practice Software Testing - Toolshop v5.0 |
| Document version | 0.1 |
| Date | 2026-11-17 |
| Client BRD owner | [NOT PROVIDED] |
| Prepared by | [NOT PROVIDED] |
| Status | Draft |

## 1. Purpose and background
Practice exercise to validate the performance-testing harness end to end on a demo shop (ToolShop / Practice Software Testing). There is no real business event or production risk driving this test.

This BRD states the business transactions in scope and the performance expectations that the test must prove. It does not describe how the test is built.

## 2. Objectives and scope

Objectives
[NOT PROVIDED]

In scope: Practice Software Testing - Toolshop v5.0 web application (Angular UI) and its REST API (Swagger-documented)
Out of scope: T4 - Add item to cart: not discovered; write actions, deferred to a later phase; T5 - Checkout and place order: not discovered; write actions, deferred to a later phase; Load testing the public site (https://practicesoftwaretesting.com/): out of scope - Testsmith's authorisation was never confirmed; load runs target a local Docker copy owned by the test lead instead

## 3. Stakeholders and approvers

| Role | Name | Responsibility |
|---|---|---|
| Business owner | [NOT PROVIDED] | Owns requirements and accepts results |
| Environment owner | [NOT PROVIDED] | Authorises testing in the target environment |
| Operations / support contact | [NOT PROVIDED] | Agrees stop conditions, informed before and during runs |
| Performance test lead | [NOT PROVIDED] | Plans and runs the test, reports results |
| Development / architecture contact | [NOT PROVIDED] | Supports diagnosis and fixes |

## 4. Business transactions in scope

| ID | Transaction | User type | Criticality | Share of traffic | Response-time start/end | Notes |
|---|---|---|---|---|---|---|
| T1 | Browse product catalogue | Guest | Medium | 44% | Start: listing request sent; End: product list response received | [NOT PROVIDED] |
| T2 | Search products by keyword | Guest | High | 31% | Start: search request sent; End: search results response received | [NOT PROVIDED] |
| T3 | View product details | Guest | Medium | 25% | Start: product request sent; End: product detail response received | [NOT PROVIDED] |

## 5. Workload model

| Item | Value |
|---|---|
| Peak concurrent users | 50 concurrent users, sitewide, split across T1-T3 by traffic share above |
| Peak requests or transactions per second | [NOT PROVIDED] |
| Peak window and duration | Not applicable - single practice run, not a real traffic peak. Planned run: ~15 minutes total (2 min ramp-up, 10 min steady state at 50 users, 3 min ramp-down). Runs target the test lead's own local Docker copy, so no external permission is needed; first execution will still be a smoke run (1 user, 1 iteration) before any load. First load run: 5 users (test lead's choice); further step-ups toward the 50-user peak happen only when the test lead asks. PR-01 to PR-06 are judged only against the 50-user peak load condition stated in each requirement; any run below that level is reported as "not measured at peak load". |
| Average daily volume | [NOT PROVIDED] |
| Expected growth over 12 months | [NOT PROVIDED] |
| User think time and pacing | Random 1-3 seconds between steps within a journey; no additional wait between iterations. |
| Geographic distribution of users | [NOT PROVIDED] |
| Data volumes in the system | [NOT PROVIDED] |
| Basis of figures (measured / forecast / assumed) | assumed |

## 6. Performance requirements

| ID | Transaction | Metric | Target | Percentile | Load condition | Priority | Notes |
|---|---|---|---|---|---|---|---|
| PR-01 | T2 - Search products by keyword | response time | <= 2 s | p95 | Peak load: 50 concurrent users sitewide | Must |  |
| PR-02 | T2 - Search products by keyword | response time | <= 4 s | p99 | Peak load: 50 concurrent users sitewide | Must |  |
| PR-03 | T5 - Checkout and place order | response time | <= 3 s | p95 | Peak load: 50 concurrent users sitewide | Must | T5 deferred to a later phase |
| PR-04 | T5 - Checkout and place order | response time | <= 5 s | p99 | Peak load: 50 concurrent users sitewide | Must | T5 deferred to a later phase |
| PR-05 | All transactions | error rate | < 1% | n/a | Peak load: 50 concurrent users sitewide | Must |  |
| PR-06 | T1, T3 - Browse product catalogue / View product details | response time | <= 2 s | p95 | Peak load: 50 concurrent users sitewide | Should |  |
| PR-07 | T4 - Add item to cart | response time | <= 2 s | p95 | Peak load: 50 concurrent users sitewide | Should | T4 deferred to a later phase |

## 7. Test types required

| Test type | Needed? | Notes |
|---|---|---|
| Baseline (single user) | yes | [NOT PROVIDED] |
| Load | yes | [NOT PROVIDED] |
| Stress | [NOT PROVIDED] | [NOT PROVIDED] |
| Spike | [NOT PROVIDED] | [NOT PROVIDED] |
| Endurance (soak) | [NOT PROVIDED] | [NOT PROVIDED] |
| Scalability | [NOT PROVIDED] | [NOT PROVIDED] |

## 8. Test environment and data

| Item | Detail |
|---|---|
| Authorisation to test | not_required - Own private copy on the test lead's machine; no third party involved |
| Target environment | local: Local Docker copy of Practice Software Testing (Toolshop), run by the test lead - http://localhost:8091 |
| Environment owner | Test lead (runs and owns the local Docker copy) |
| Comparison with production | Not applicable: practice project, no production system |
| Third-party services | None called by the tests |
| Test data needs | Seeded demo data of the local copy; synthetic data only |
| No real personal or payment data (confirmation) | No real personal or payment data will be used; all names, emails, addresses and card details will be made-up test values. Checkout will use only dummy payment details the site allows for practice (not yet verified whether it accepts them). This confirmation is the test lead's own statement and has not been independently checked. |
| Monitoring access | docker_stats: CPU and memory of the ToolShop API, web server and database containers, sampled with docker stats |
| Allowed test windows | Any time, chosen by the test lead |

## 9. Test stop (abort) conditions

Agree these with the operations team before the test is approved.

| Condition | Threshold | Action |
|---|---|---|
| Error rate | Above 2% for 1 minute | Stop the run and review |
| Response time | p95 above 3x the target of the affected transaction for 2 minutes | Stop the run |
| Server health | Any HTTP 429 or 503 response (stopped automatically by the script). CPU and memory are recorded for the report but do not stop the run automatically. | Stop immediately |
| Impact on other systems or users | Any sign: slowdown reports, owner notice, or unusual responses | Stop immediately |
| Request from operations or environment owner | Any time | Stop immediately |

## 10. Monitoring and reporting
Metrics collected: Response time (p95/p99) and error rate, measured client-side via k6 at API/HTTP level (not browser rendering). No server-side CPU/memory available.
Tools: [NOT PROVIDED]
Interim updates: [NOT PROVIDED]
Final report: [NOT PROVIDED]

The report states each requirement ID as met, not met or not measured, with evidence.

## 11. Assumptions, constraints, dependencies and risks

| Type | Description | Owner | Impact if wrong |
|---|---|---|---|
| Assumption | This test has no real business driver; it is a practice/validation exercise for the performance-testing harness on a demo application. | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | Peak load assumed at 50 concurrent users sitewide (not measured or forecast from real traffic); no separate TPS figure given. Split across T1-T3 by the traffic shares recorded in the transactions table (recomputed to 44%/31%/25% after T4 and T5 moved to scope_out, keeping the original 35:25:20 ratio). | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | Performance requirements PR-01 to PR-06 are assumed targets (not derived from a client SLA). | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | Business transaction definitions (T1-T5: names, criticality, traffic share, flow, measurement points) are assumed/stated by the test lead for this practice project, not confirmed by a client business owner. | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | Peak window/run duration assumed as a single ~15 minute practice run (2 min ramp-up, 10 min steady state, 3 min ramp-down); first execution will be a smoke run (1 user, 1 iteration) before any load. | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | Think time assumed at random 1-3 seconds between steps, no extra pacing between iterations. | [NOT PROVIDED] | [NOT PROVIDED] |
| Constraint | Load testing the public site (https://practicesoftwaretesting.com/) remains blocked pending Testsmith's permission and is now out of scope (see scope_out); the active target for load runs is the test lead's own local Docker copy, which needs no such permission. | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | The local Docker copy is assumed to expose the same REST API (same paths, methods including QUERY, response shapes) as api-catalogue.yaml, which was built from discovery against the public site - this has not been separately verified against the local copy. | [NOT PROVIDED] | [NOT PROVIDED] |
| Assumption | All abort conditions in abort_conditions are the test lead's own assumptions, not yet agreed with an environment owner or operations contact. | [NOT PROVIDED] | [NOT PROVIDED] |
| Constraint | Hard limits assumed regardless of other conditions: never more than 50 virtual users, never longer than 20 minutes per run. | [NOT PROVIDED] | [NOT PROVIDED] |

## 12. Acceptance and exit criteria

The test is accepted when:
[NOT PROVIDED]

## 13. Open items

| # | Question | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Resolved for now: load runs target the test lead's own local Docker copy instead of the public site, so Testsmith's authorisation is not needed for this phase. Revisit only if testing against the public site is wanted again. | Test lead | [NOT PROVIDED] | Resolved |
| 2 | Base URL confirmed (http://localhost:8091). Closed: the local Docker copy's REST API was checked against api-catalogue.yaml (built from discovery against the public site, same paths/methods incl. QUERY). Reason: 7 calls returned 200, status codes only; response shapes not compared. | Test lead | [NOT PROVIDED] | Closed |
| 3 | Confirm how many test accounts are available and whether one account can be used by several virtual users at once. | Test lead | [NOT PROVIDED] | Open |
| 4 | Whether the site's checkout accepts dummy/test payment details for practice has not been verified. | Test lead | [NOT PROVIDED] | Open |
| 5 | Which further test types (stress, spike, soak, scalability) are needed in addition to Baseline and Load, which are confirmed as yes? | Test lead | [NOT PROVIDED] | Open |

## 14. Approval

| Name | Role | Decision | Date |
|---|---|---|---|
| [NOT PROVIDED] | Business owner | [NOT PROVIDED] | [NOT PROVIDED] |
| [NOT PROVIDED] | Environment owner | [NOT PROVIDED] | [NOT PROVIDED] |
| [NOT PROVIDED] | Operations contact | [NOT PROVIDED] | [NOT PROVIDED] |
