---
mode: agent
description: Start a new client performance project and run it end to end through the client pack
---
Start a new performance testing project and continue end to end through the client pack.

1. Ask me in one message for: client name, application name, environment URL and owner, whether I authorise testing it, and the source documents to place in `sources/`.
2. Create `projects/<client>/<app>/` with a `sources/` folder, copy `templates/brd.template.yaml` to `brd.yaml` and `templates/environments.template.yaml` to `environments.yaml`, and create `STATE.md` with stage "1. Collect requirements".
3. When the sources are ready, read them (`requirements-intake`). Then send me ONE message with:
   - only the business facts still missing (`python tools/brd.py questions`), each with its copy-paste example;
   - the advised technical values (`python tools/brd.py advise`) as a table to accept or change;
   - the run plan to approve (load steps, durations, discovery write actions, build the pack if targets are missed), with a ready-to-accept example.
4. Apply my answers, then follow `.github/skills/end-to-end/SKILL.md`: loop on `python tools/status.py projects/<client>/<app>` and do every unfinished stage in order without stopping, until `ALL STAGES DONE`.
5. Stop only for the decisions listed in the end-to-end skill (authorisation, a failed smoke run, an aborted or errored run, a write action or load step outside the approved plan, an unexplained target-check difference). Never decide those for me.
6. After the client pack is built, tell me where it is and to read the cover before sharing it.
