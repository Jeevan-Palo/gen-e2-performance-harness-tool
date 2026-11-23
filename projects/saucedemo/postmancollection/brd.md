# Business Requirements Document: Performance Testing

| Field | Value |
|---|---|
| Client / business unit | saucedemo |
| Application / system | postmancollection |
| Document version | 0.1 |
| Date | [NOT PROVIDED] |
| Client BRD owner | [NOT PROVIDED] |
| Prepared by | [NOT PROVIDED] |
| Status | Draft |

## 1. Purpose and background
To test this tool

This BRD states the business transactions in scope and the performance expectations that the test must prove. It does not describe how the test is built.

## 2. Objectives and scope

Objectives
[NOT PROVIDED]

In scope: Authentication (T1), Inventory (T2) and Cart (T3) APIs of the Postman collection on dummyjson.com
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
| T1 | Authentication | [NOT PROVIDED] | [NOT PROVIDED] | 34% | From the user action (click or page request) until the next page is fully loaded | [NOT PROVIDED] |
| T2 | Inventory | [NOT PROVIDED] | [NOT PROVIDED] | 33% | From the user action (click or page request) until the next page is fully loaded | [NOT PROVIDED] |
| T3 | Cart | [NOT PROVIDED] | [NOT PROVIDED] | 33% | From the user action (click or page request) until the next page is fully loaded | [NOT PROVIDED] |

## 5. Workload model

| Item | Value |
|---|---|
| Peak concurrent users | Up to the environment limit (5 concurrent users), stepped; real peak to be confirmed from analytics |
| Peak requests or transactions per second | [NOT PROVIDED] |
| Peak window and duration | Busiest business hour; tested as 5 min ramp-up, 20 min steady load, 5 min ramp-down |
| Average daily volume | [NOT PROVIDED] |
| Expected growth over 12 months | [NOT PROVIDED] |
| User think time and pacing | 5 seconds between user actions |
| Geographic distribution of users | [NOT PROVIDED] |
| Data volumes in the system | [NOT PROVIDED] |
| Basis of figures (measured / forecast / assumed) | assumed |

## 6. Performance requirements

| ID | Transaction | Metric | Target | Percentile | Load condition | Priority | Notes |
|---|---|---|---|---|---|---|---|
| PR-01 | All | Error rate | <= 1% | n/a | peak load | Must |  |

## 7. Test types required

| Test type | Needed? | Notes |
|---|---|---|
| Baseline (single user) | yes | [NOT PROVIDED] |
| Load | yes | [NOT PROVIDED] |
| Stress | no | [NOT PROVIDED] |
| Spike | no | [NOT PROVIDED] |
| Endurance (soak) | no | [NOT PROVIDED] |
| Scalability | no | [NOT PROVIDED] |

## 8. Test environment and data

| Item | Detail |
|---|---|
| Authorisation to test | accepted_by_test_lead - User stated authorisation=accepted_by_test_lead, 2026-11-23. |
| Target environment | saucedemo-environment: SauceDemo Environment - https://dummyjson.com |
| Environment owner | Test Lead |
| Comparison with production | [NOT PROVIDED] |
| Third-party services | [NOT PROVIDED] |
| Test data needs | Synthetic test accounts and standard catalogue products; data reset between runs |
| No real personal or payment data (confirmation) | Yes: only synthetic test data is used; no real personal or payment data |
| Monitoring access | none: client-side k6 metrics only; server CPU and memory added when APM access is granted |
| Allowed test windows | Weekdays 10:00-16:00 client local time, outside releases and batch jobs |

## 9. Test stop (abort) conditions

Agree these with the operations team before the test is approved.

| Condition | Threshold | Action |
|---|---|---|
| Error rate | > 5% for 2 consecutive minutes | Stop the test and notify the environment owner |
| Response time | p95 > 10 s for 2 consecutive minutes | Stop the test |
| Throttling or blocking | Any 429, 503 or WAF/CDN block response | Stop immediately |
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
| Assumption | Advised values accepted by the user in place of client figures: workload.peak_window, workload.think_time, workload.basis, requirements, test_types, abort_conditions, environment.personal_data_confirmation, environments.yaml test_data, environments.yaml test_windows, environments.yaml monitoring. | Test lead | Results show behaviour under advised settings; confirm with the client before sign-off |
| Assumption | Advised values accepted by the user in place of client figures: workload.peak_concurrent_users. | Test lead | Results show behaviour under advised settings; confirm with the client before sign-off |
| Assumption | Advised values accepted by the user in place of client figures: transactions[].traffic_share, transactions[].measure_start_end. | Test lead | Results show behaviour under advised settings; confirm with the client before sign-off |

## 12. Acceptance and exit criteria

The test is accepted when:
[NOT PROVIDED]

## 13. Open items

| # | Question | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Peak load: What is the peak concurrent user or TPS load, and is it sitewide or per transaction? | [NOT PROVIDED] | [NOT PROVIDED] | Open |

## 14. Approval

| Name | Role | Decision | Date |
|---|---|---|---|
| [NOT PROVIDED] | Business owner | [NOT PROVIDED] | [NOT PROVIDED] |
| [NOT PROVIDED] | Environment owner | [NOT PROVIDED] | [NOT PROVIDED] |
| [NOT PROVIDED] | Operations contact | [NOT PROVIDED] | [NOT PROVIDED] |
