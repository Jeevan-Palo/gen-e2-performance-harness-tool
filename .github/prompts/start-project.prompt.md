---
mode: agent
description: Start a new client performance project (Steps 1-3)
---
Start a new performance testing project.

1. Ask me for the client name and application name (one question).
2. Create `projects/<client>/<app>/` with a `sources/` folder, copy `templates/brd.template.yaml` to `brd.yaml` and `templates/environments.template.yaml` to `environments.yaml` (then ask me for each environment I may test, its URL and who owns it), and create `STATE.md` with stage "1. Collect requirements".
3. Tell me to put the client's documents (BRD, emails, notes, Postman collection, etc.) into `sources/`, and wait.
4. When I say the files are there, follow `.github/skills/requirements-intake/SKILL.md`, then `.github/skills/brd-builder/SKILL.md`.
