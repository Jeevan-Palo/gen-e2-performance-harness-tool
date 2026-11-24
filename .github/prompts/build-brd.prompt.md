---
mode: agent
description: Create the project if needed, collect the BRD documents, build the BRD and the client confirmation Word file, then stop (stage 1)
---
Do stage 1 only, then stop. No catalogue, script or runs.

1. Ask me in one message, with copy-paste examples, for the client name and application name (for example `client PST, app Toolshop`) and the environment URL and owner (for example `URL https://staging.example.com, owner Jane Doe (QA lead)`). Skip anything I already gave.
2. If `projects/<client>/<app>/` does not exist, create it with a `sources/` folder, copy `templates/brd.template.yaml` to `brd.yaml` and `templates/environments.template.yaml` to `environments.yaml`, and create `STATE.md` with stage "1. Collect requirements". If it exists, keep everything in it.
3. If `sources/` is empty, tell me the exact folder path and ask: "Have you placed the BRD / requirement documents in sources/?" with the copy-paste example reply `Done, files placed`. Wait for my answer. If I reply yes or done, continue and read them. If I say there are none, continue with the questions only.
4. Run `python tools/next.py <project folder>`. The `sources` gate is cleared by my answer in step 3, so do not stop on it again. If it reports a stage after stage 1, tell me where the project stands and stop.
5. Follow `.github/skills/requirements-intake/SKILL.md`, then `.github/skills/brd-builder/SKILL.md`.
6. Send me ONE message with the missing business facts (`python tools/brd.py questions`, each with its copy-paste example) and the advised values to accept or change (`python tools/brd.py advise`). Apply my answers, run `python tools/brd.py check` and `python tools/brd.py render`.
7. Run `python tools/brdexport.py <project folder>`. Tell me the path of `client-pack/brd-confirmation-v<version>.docx` and the Stated / Advised / Assumed / Not evidenced / Open counts. It is for the client to review and sign; do not send it or fill its sign-off.
