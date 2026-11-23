# Business Requirements Document: Performance Testing

| Field | Value |
|---|---|
| Client / business unit | SwagLabs |
| Application / system | SauceDemo |
| Document version | 0.1 |
| Date | [NOT PROVIDED] |
| Client BRD owner | [NOT PROVIDED] |
| Prepared by | [NOT PROVIDED] |
| Status | Draft |

## 1. Purpose and background
Performance testing is needed now to evaluate the application's response time, stability, and reliability under expected user traffic. It helps identify performance bottlenecks, detect potential issues before release, and ensure a smooth user experience.

This BRD states the business transactions in scope and the performance expectations that the test must prove. It does not describe how the test is built.

## 2. Objectives and scope

Objectives
[NOT PROVIDED]

In scope: Browse the SauceDemo application
Out of scope: [NOT PROVIDED]

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
| T1 | Login | Guest/registered test user | High | 25% | From login page request start to inventory page load completion | Sample assumption |
| T2 | Browse products | Registered test user | High | 25% | From inventory request start to product page response completion | Sample assumption |
| T3 | Add to cart | Registered test user | High | 25% | From add-to-cart action start to cart badge update | No load-safe network API observed; sample assumption |
| T4 | Checkout | Registered test user | High | 25% | From checkout action start to completion page render | No load-safe network API observed; sample assumption |

## 5. Workload model

| Item | Value |
|---|---|
| Peak concurrent users | 5 concurrent users across the whole site |
| Peak requests or transactions per second | [NOT PROVIDED] |
| Peak window and duration | Sample assumption: 30-minute test within an agreed window |
| Average daily volume | [NOT PROVIDED] |
| Expected growth over 12 months | [NOT PROVIDED] |
| User think time and pacing | 3 seconds between user actions |
| Geographic distribution of users | [NOT PROVIDED] |
| Data volumes in the system | [NOT PROVIDED] |
| Basis of figures (measured / forecast / assumed) | assumed |

## 6. Performance requirements

| ID | Transaction | Metric | Target | Percentile | Load condition | Priority | Notes |
|---|---|---|---|---|---|---|---|
| PR-01 | T1 | Response time | <= 2 s | p95 | 100 concurrent users | Must |  |
| PR-02 | T2 | Response time | <= 2 s | p95 | 100 concurrent users | Must |  |
| PR-03 | T3 | Response time | <= 2 s | p95 | 100 concurrent users | Must |  |
| PR-04 | T4 | Response time | <= 3 s | p95 | 100 concurrent users | Must |  |
| PR-05 | All | Error rate | <= 1% | n/a | peak load | Must |  |
| PR-06 | System | Stability | maintain target load for 30 minutes without major degradation | n/a | target load | Should | Deferred: sample run duration is not a stability proof |

## 7. Test types required

| Test type | Needed? | Notes |
|---|---|---|
| Baseline (single user) | yes | [NOT PROVIDED] |
| Load | [NOT PROVIDED] | [NOT PROVIDED] |
| Stress | [NOT PROVIDED] | [NOT PROVIDED] |
| Spike | [NOT PROVIDED] | [NOT PROVIDED] |
| Endurance (soak) | [NOT PROVIDED] | [NOT PROVIDED] |
| Scalability | [NOT PROVIDED] | [NOT PROVIDED] |

## 8. Test environment and data

| Item | Detail |
|---|---|
| Authorisation to test | accepted_by_test_lead - Accepted by test lead in chat on 2026-11-23 |
| Target environment | test: SauceDemo test environment - https://www.saucedemo.com/ |
| Environment owner | Test lead |
| Comparison with production | [NOT PROVIDED] |
| Third-party services | [NOT PROVIDED] |
| Test data needs | Predefined SauceDemo test accounts; standard products in the public catalog; reset application state and shopping carts between runs |
| No real personal or payment data (confirmation) | Synthetic or masked data only |
| Monitoring access | none |
| Allowed test windows | Sample assumption: off-peak 30-minute window |

## 9. Test stop (abort) conditions

Agree these with the operations team before the test is approved.

| Condition | Threshold | Action |
|---|---|---|
| Error rate | > 5% for 2 consecutive minutes | Stop and notify operations |
| Response time | p95 > 10 s for 2 consecutive minutes | Stop |
| Server health | Not available for public environment | Stop if health source reports severe degradation |
| Impact on other systems or users | Sample assumption: any confirmed impact | Stop immediately |
| Request from operations or environment owner | Any stop request | Stop immediately |

## 10. Monitoring and reporting
Metrics collected: [NOT PROVIDED]
Tools: [NOT PROVIDED]
Interim updates: [NOT PROVIDED]
Final report: [NOT PROVIDED]

The report states each requirement ID as met, not met or not measured, with evidence.

## 11. Assumptions, constraints, dependencies and risks

| Type | Description | Owner | Impact if wrong |
|---|---|---|---|
| Assumption | 25% sample traffic share assigned to each transaction because client shares were unavailable. | Test lead | Traffic mix may not represent production |
| Assumption | Peak window and abort conditions use sample values and require client/operations approval. | Test lead | Results must not be claimed as approved requirements |
| Constraint | Environment hard limit is 5 VUs; stated 100-VU targets cannot be executed under this setup. | Test lead | 100-VU requirements remain untested |

## 12. Acceptance and exit criteria

The test is accepted when:
[NOT PROVIDED]

## 13. Open items

| # | Question | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Confirm TPS if required in addition to 5 whole-site concurrent users. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 2 | Confirm the peak window and duration; 'Proposed' is not a specific date/time or duration. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 3 | Confirm allowed test windows, dates, times and any blackout periods. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 4 | Confirm T1 traffic share. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 5 | Confirm T1 response-time measurement start and end point. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 6 | Confirm T2 traffic share. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 7 | Confirm T2 response-time measurement start and end point. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 8 | Confirm T3 traffic share. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 9 | Confirm T3 response-time measurement start and end point. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 10 | Confirm T4 traffic share. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 11 | Confirm T4 response-time measurement start and end point. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 12 | Resolve workload conflict: 5 whole-site concurrent users was stated while T1-T4 requirements apply at 100 concurrent users. | [NOT PROVIDED] | [NOT PROVIDED] | Open |
| 13 | Confirm abort thresholds and actions with operations; proposed values are not yet agreed. | [NOT PROVIDED] | [NOT PROVIDED] | Open |

## 14. Approval

| Name | Role | Decision | Date |
|---|---|---|---|
| [NOT PROVIDED] | Business owner | [NOT PROVIDED] | [NOT PROVIDED] |
| [NOT PROVIDED] | Environment owner | [NOT PROVIDED] | [NOT PROVIDED] |
| [NOT PROVIDED] | Operations contact | [NOT PROVIDED] | [NOT PROVIDED] |
