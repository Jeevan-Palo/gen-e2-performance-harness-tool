---
name: api-discovery-browser
description: Discover APIs by using the application in a browser when no API documentation exists or it is incomplete, and record pages, requests, responses and business flow into api-catalogue.yaml. Use for Step 5 of the performance flow.
---

# API discovery in the browser (Step 5)

Use only on an environment the user has confirmed we may use. Check `environments.yaml` first: browse only the active environment, and only if its `authorisation` is not `not_confirmed`. Never change that value yourself.

## Safety rules (always)
1. Read-only by default: browse, search, open pages and product views. Do NOT submit forms that create or change data (register, add to cart, checkout, post, delete) unless the user explicitly approves that exact action in this chat.
2. Never use real credentials or real personal data. Use only test accounts the user gives you, and never write them into any file.
3. If the active environment's authorisation is `not_confirmed`, do not browse it at all; tell the user. Otherwise keep discovery to the pages needed, with no scripted or repeated requests and no load of any kind.
4. Stop and tell the user if you see rate limiting, a block page, a CAPTCHA, or any 429/503.
5. Write calls you did not execute (e.g. checkout) are NOT discovered. Add them from documentation if available, or record them as an open item. Do not invent them.

## Procedure
1. Pick the BRD transactions to discover (T1, T2, ...) and the start URL from the user.
2. Preferred method, if a browser tool is available (for example Playwright MCP): open each page of the flow, watch network requests of type XHR/fetch, and note per request: method, URL, request body, response status, response fields, page, and what the user was doing.
3. Fallback, always works: ask the user to record a HAR file (Chrome: open DevTools > Network, tick "Preserve log", perform the flow, then "Save all as HAR with content") and put it in `sources/`. Then import it:
   `python tools/catalogue.py import-har <catalogue> <file.har> <base_url>`
   The script imports same-host API calls and first-party static assets separately, lists observed third-party API/static hosts under `meta.excluded_hosts`, and removes auth headers, cookies and query-string values.
4. For every discovered API fill `transaction`, `step_order`, `page`, `business_flow`, `dynamic_values`, `depends_on`, `safe_to_load` and `side_effects`, only from what you observed. Set `evidence.source_type` to `browser` or `har`.
5. Record session and CSRF behavior in the separate `web_tier.requests` inventory only when observed. Store cookie/header names and token locations, never cookie or token values. HAR import does not infer these categories.
6. Run `python tools/catalogue.py check <catalogue> <brd.yaml>` and fix or ask, as in the `api-catalogue-from-sources` skill.
7. Update `STATE.md` and give the user a short summary: pages visited, APIs and web-tier resources found, transactions still without APIs, write calls not discovered.

## Do not
- Do not generate a performance script. The catalogue is the input for the next step.
- Do not keep screenshots, HAR files or notes containing credentials or personal data.
