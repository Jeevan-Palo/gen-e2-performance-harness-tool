#!/usr/bin/env python3
"""Check the harness repo itself (not a project). Usage: python tools/lint.py   (from the repo root; exit 1 if anything is wrong)
Checks: skill, prompt and agent frontmatter (handoff targets exist, the runner agent has no edit tool), every next.py gate described in the end-to-end skill, names, references to tools/skills/prompts that do not exist, rule numbering in
copilot-instructions.md, tools compile, templates and project YAML parse, secret-like text. Requires PyYAML.
"""
import sys, os, re, ast, glob, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET = [re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]{20,}"), re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
          re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key)\b['\"]?\s*[:=]\s*['\"][^'\"\s<$\{]{8,}['\"]")]
rel = lambda p: os.path.relpath(p, ROOT)

def frontmatter(path):
    t = open(path, encoding="utf-8").read(); m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    if not m: return None, "no frontmatter block"
    try: return yaml.safe_load(m.group(1)) or {}, None
    except Exception as e: return None, "frontmatter does not parse: " + str(e).splitlines()[0][:100]

def lint():
    P = []
    read = lambda p: open(p, encoding="utf-8", errors="replace").read()
    skills = sorted(glob.glob(os.path.join(ROOT, ".github", "skills", "*", "SKILL.md")))
    prompts = sorted(glob.glob(os.path.join(ROOT, ".github", "prompts", "*.prompt.md")))
    tools = sorted(glob.glob(os.path.join(ROOT, "tools", "*.py")))
    for f in skills:
        fm, err = frontmatter(f)
        if err: P.append(f"{rel(f)}: {err}"); continue
        folder = os.path.basename(os.path.dirname(f))
        if fm.get("name") != folder: P.append(f"{rel(f)}: name '{fm.get('name')}' must equal the folder name '{folder}'")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(fm.get("name", ""))): P.append(f"{rel(f)}: name must be lowercase letters, digits and hyphens")
        d = str(fm.get("description", ""))
        if not d.strip(): P.append(f"{rel(f)}: description is empty")
        if len(d) > 1024: P.append(f"{rel(f)}: description is {len(d)} characters (limit 1024)")
    for f in prompts:
        fm, err = frontmatter(f)
        if err: P.append(f"{rel(f)}: {err}"); continue
        if not str(fm.get("description", "")).strip(): P.append(f"{rel(f)}: description is empty")
    agents = sorted(glob.glob(os.path.join(ROOT, ".github", "agents", "*.agent.md")))
    agent_names = set()
    for f in agents:
        fm, err = frontmatter(f)
        if err: P.append(f"{rel(f)}: {err}"); continue
        stem = os.path.basename(f)[:-len(".agent.md")]; agent_names.add(stem)
        if fm.get("name") != stem: P.append(f"{rel(f)}: name '{fm.get('name')}' must equal the file name '{stem}'")
        if not str(fm.get("description", "")).strip(): P.append(f"{rel(f)}: description is empty")
        if not isinstance(fm.get("tools"), list) or not fm.get("tools"): P.append(f"{rel(f)}: tools must be a non-empty list")
        if stem == "perf-runner" and any(x in ("editFiles", "edit", "create") for x in fm.get("tools") or []):
            P.append(f"{rel(f)}: the runner must not have an edit tool (it must not be able to change run files, reports or the pack)")
    for f in agents:
        fm, err = frontmatter(f)
        for h in (fm or {}).get("handoffs") or []:
            if h.get("agent") not in agent_names: P.append(f"{rel(f)}: handoff to agent '{h.get('agent')}', which does not exist")
    for f in tools:
        try: ast.parse(read(f))
        except SyntaxError as e: P.append(f"{rel(f)}: syntax error line {e.lineno}")
    known_tools = {os.path.basename(t) for t in tools}; known_skills = {os.path.basename(os.path.dirname(s)) for s in skills}
    known_prompts = {os.path.basename(p) for p in prompts}
    docs = [os.path.join(ROOT, ".github", "copilot-instructions.md"), os.path.join(ROOT, "README.md"), os.path.join(ROOT, "docs", "overview.md")] + skills + prompts + agents
    for f in docs:
        if not os.path.exists(f): P.append(f"missing file: {rel(f)}"); continue
        t = read(f)
        if re.search(r"\bSteps? \d", t): P.append(f"{rel(f)}: old step numbering ('Step N'); use the stage numbers 1-9 that tools/status.py prints")
        for m in set(re.findall(r"tools/([A-Za-z0-9_]+\.py)", t)):
            if m not in known_tools: P.append(f"{rel(f)}: refers to tools/{m}, which does not exist")
        for m in set(re.findall(r"\.github/skills/([a-z0-9\-]+)/", t)):
            if m not in known_skills: P.append(f"{rel(f)}: refers to skill '{m}', which does not exist")
        for m in set(re.findall(r"\.github/prompts/([A-Za-z0-9\-]+\.prompt\.md)", t)):
            if m not in known_prompts: P.append(f"{rel(f)}: refers to prompt {m}, which does not exist")
    e2e = os.path.join(ROOT, ".github", "skills", "end-to-end", "SKILL.md")
    nx = os.path.join(ROOT, "tools", "next.py")
    if os.path.exists(e2e) and os.path.exists(nx):
        gates = re.search(r"(?s)GATES = \{(.*?)\n\}", read(nx))
        for g in re.findall(r'(?m)^    "([a-z_]+)":', gates.group(1) if gates else ""):
            if f"`{g}`" not in read(e2e): P.append(f"{rel(e2e)}: gate `{g}` raised by tools/next.py is not described")
    for rf in ("requirements.txt", "setup.sh", "setup.ps1"):
        if not os.path.exists(os.path.join(ROOT, rf)): P.append(f"missing file: {rf} (needed so other people can set up the repo)")
    ci = os.path.join(ROOT, ".github", "copilot-instructions.md")
    if os.path.exists(ci):
        nums = [int(x) for x in re.findall(r"(?m)^(\d+)\. ", read(ci))]
        if nums != list(range(1, len(nums) + 1)): P.append(f"{rel(ci)}: rule numbers are not 1..N in order: {nums}")
    for f in sorted(glob.glob(os.path.join(ROOT, "templates", "*.yaml"))):
        try: yaml.safe_load(read(f))
        except Exception as e: P.append(f"{rel(f)}: YAML does not parse: {str(e).splitlines()[0][:80]}")
    for f in sorted(glob.glob(os.path.join(ROOT, "projects", "*", "*", "*.yaml")) + glob.glob(os.path.join(ROOT, "projects", "*", "*", "k6", "*.yaml"))):
        try: yaml.safe_load(read(f))
        except Exception as e: P.append(f"{rel(f)}: YAML does not parse: {str(e).splitlines()[0][:80]}")
    for f in sorted(glob.glob(os.path.join(ROOT, "**", "*"), recursive=True)):
        if not os.path.isfile(f) or any(x in f for x in ("/.venv/", "/.git/", "/node_modules/", "/__pycache__/", "/runs/", "/client-pack/", "/tests/")): continue
        if f.endswith((".md", ".yaml", ".yml", ".py", ".js", ".json")) and os.path.basename(f) != "lint.py":
            t = read(f)
            for rx in SECRET:
                if rx.search(t): P.append(f"{rel(f)}: contains secret-like text"); break
    return P

def main():
    P = lint()
    if P: print(f"LINT: {len(P)} problem(s)"); [print(f"  {i}. {x}") for i, x in enumerate(P, 1)]
    else: print("LINT: OK")
    sys.exit(1 if P else 0)

if __name__ == "__main__": main()
