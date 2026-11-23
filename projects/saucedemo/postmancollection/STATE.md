# STATE: saucedemo / postmancollection
- Stage: 9 client pack built; ALL STAGES DONE per tools/status.py; 2026-11-23.
- BRD: Draft; purpose and scope answered by the user; real peak remains an advised assumption; 1 open item (peak load).
- Source: Postman collection + environment file; catalogue statuses are expected (from test scripts), not observed.
- Target: https://dummyjson.com; test account via APP_USER and APP_PASSWORD (values never stored).
- Runs (token in memory only; per-transaction and per-API timings exported): smoke 1 VU, load 2, 4, 5 VUs (30s/2m/30s); all passed, 0% errors, no blocks. Earlier runs without per-API data remain in runs/.
- Pack: client-pack/ (zip built, nothing sent). Read the cover before sharing; BRD status is Draft, prepared_by is empty.
- Not covered: server CPU/memory (monitoring none); 30-minute advised profile exceeds the 5-minute cap.
