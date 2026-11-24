---
mode: agent
description: Check that the target answers the catalogue's read calls (stage 4)
---
Do stage 4 only for the project I name (ask me which one if unclear), then stop.

1. Run `python tools/next.py <project folder>`. If the next stage is not stage 4, tell me where the project stands and stop.
2. If the environment's `authorisation` is `not_confirmed`, stop and tell me; never change it.
3. If the catalogue has calls that need a login, tell me to export the variables named in `credentials_env_vars` and run the command myself in my own terminal (it sends one login POST). Show me the exact command and a copy-paste example reply such as `Exported; I will run the check myself`. Never ask me for the values.
4. Otherwise run `python tools/targetcheck.py <project folder>` (read calls only, one request per API) and tell me the result and any difference between the catalogue and the target.
