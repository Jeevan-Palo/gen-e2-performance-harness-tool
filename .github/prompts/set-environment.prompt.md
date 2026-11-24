---
mode: agent
description: Fill and check environments.yaml for a project (stage 2)
---
Do stage 2 only for the project I name (ask me which one if unclear), then stop.

1. Run `python tools/next.py <project folder>`. If stage 1 is not done, tell me and stop.
2. Ask me in one message, each with a copy-paste example answer (for example `URL https://staging.example.com, owner Jane Doe (QA lead)`), for whatever `environments.yaml` still lacks: URL, owner, limits, monitoring, test windows, test data, credential variable NAMES. Never guess a value and never store credentials.
3. Never set `authorisation` yourself. Only when I state it in this chat, record my statement and the date in `authorisation_note`. Ask me with an example such as `Yes, I confirm testing the <environment name> environment is authorised`.
4. Run `python tools/envconf.py check <project folder>` and show me the result. Switch environments only with `python tools/envconf.py use <project folder> <name>`.
