#!/usr/bin/env python3
"""Build the Word document the client reviews and signs: values with their basis (stated / advised / assumed), open questions with
an answer column, and a blank sign-off table. It is generated from brd.yaml and environments.yaml; never edit values in the .docx,
change the yaml and export again.
Usage: python tools/brdexport.py <project_dir>
Output: <project_dir>/client-pack/brd-confirmation-v<meta.version>.docx (same version = overwritten). Nothing is sent anywhere.
Needs pandoc (brew install pandoc) and PyYAML.
"""
import sys, os, re, shutil, subprocess, tempfile, zipfile, datetime, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf, brd as brdtool, lint

BASIS_TEXT = {
    "Stated": "the client or the sources said it", "Advised": "suggested by the test lead; needs your confirmation",
    "Assumed": "an assumption we made; needs your confirmation", "Not evidenced": "a value is present but no record of where it came from",
    "Open": "no value yet; we need your answer"}

def esc(x):
    return re.sub(r"([\\`*_{}\[\]<>#|$~^])", r"\\\1", re.sub(r"\s*\n\s*", " ", str(x if x is not None else ""))).strip()

def table(headers, widths, data):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("-" * w for w in widths) + "|"]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in data]
    return out + [""]

def question_rows(d, cap):
    rows = [(q["field"], q["question"], q["format"].replace("Example: ", "", 1)) for q in brdtool.questions(d)]
    rows += [(a["field"], "Please confirm or change this suggested value", a["value"]) for a in brdtool.advice(d, cap)]
    rows += [("", f"Please provide: {x}", "") for x in brdtool.check(d) if brdtool.category(x) is None]
    rows += [("open item", r["question"], "") for r in brdtool.rows(d.get("open_items"), ["question"])
             if str(r.get("status", "")).strip().lower() == "open"]
    return rows

def build_markdown(d, cap, today):
    m = d.get("meta") or {}
    pr = brdtool.provenance(d); counts = brdtool.provenance_counts(pr)
    L = ["# Performance Testing: Requirements Confirmation", "",
         *table(["Item", "Detail"], [18, 60], [(k, m.get(f) or "[not provided]") for k, f in [("Client", "client"), ("Application", "application"), ("BRD version", "version"), ("Status", "status"), ("Prepared by", "prepared_by")]] + [("Document date", today)]),
         "## How to use this document", "",
         "1. Check the values in Part C. The **Basis** column says where each value came from.",
         "2. Answer the questions in Part B and, for any value you do not agree with, write the correct value in the **Your response** column.",
         "3. Sign Part E and return the file to the test lead.", "",
         "Nothing is tested until this document has been reviewed and the BRD is approved by the client.", "",
         "## Part A. Summary of the values", ""]
    L += table(["Basis", "Meaning", "Count"], [14, 50, 8], [(b, BASIS_TEXT[b], counts[b]) for b in brdtool.BASES])
    L += ["## Part B. Questions for you", ""]
    q = question_rows(d, cap)
    L += table(["#", "Question", "Suggested answer or example", "Your answer"], [4, 34, 28, 28], [(i, r[1], r[2], "") for i, r in enumerate(q, 1)]) if q else ["No open questions.", ""]
    L += ["## Part C. Values to confirm", ""]
    for sec in dict.fromkeys(r["section"] for r in pr):
        L += [f"### {sec}", ""]
        L += table(["Item", "Value", "Basis", "Source", "Your response"], [18, 28, 10, 20, 24],
                   [(r["item"], r["value"] or "[not provided]", r["basis"], r["source"], "") for r in pr if r["section"] == sec])
    risks = brdtool.rows(d.get("risks"), ["description"])
    L += ["## Part D. Assumptions, constraints, dependencies and risks", ""]
    L += table(["Type", "Description", "Owner", "Impact if wrong", "Your response"], [12, 34, 12, 22, 20],
               [(r.get("type"), r.get("description"), r.get("owner"), r.get("impact"), "") for r in risks]) if risks else ["None recorded.", ""]
    L += ["## Part E. Sign-off", "", "Decision: Approved / Approved with changes / Not approved (delete the options that do not apply).", ""]
    appr = [a for a in (d.get("approvals") or []) if isinstance(a, dict)] or [{"role": "Business owner"}]
    L += table(["Name", "Role", "Decision", "Signature", "Date"], [20, 20, 20, 20, 12], [(a.get("name"), a.get("role"), "", "", "") for a in appr])
    L += [f"Generated from brd.yaml version {m.get('version') or '?'} on {today}. If a value is wrong, tell the test lead; do not rely on edits to the tables above.", ""]
    return "\n".join(L)

def styled_reference(tmp):
    ref = os.path.join(tmp, "reference.docx")
    with open(ref, "wb") as f: f.write(subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"], check=True, capture_output=True).stdout)
    out = os.path.join(tmp, "styled.docx")
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="808080"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    with zipfile.ZipFile(ref) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "word/styles.xml":
                s = data.decode("utf-8")
                s = re.sub(r'(w:styleId="Table".*?<w:tblInd[^>]*/>)', lambda mm: mm.group(1) + f"<w:tblBorders>{border}</w:tblBorders>", s, count=1, flags=re.S)
                s = re.sub(r'(w:styleId="Table".*?<w:top w:w=")0(".*?<w:bottom w:w=")0(")', r"\g<1>40\g<2>40\g<3>", s, count=1, flags=re.S)
                s = re.sub(r'(<w:tblStylePr w:type="firstRow">)(\s*<w:tcPr>\s*<w:tcBorders>.*?</w:tcBorders>)',
                           r'\1<w:rPr><w:b/></w:rPr>\2<w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/>', s, count=1, flags=re.S)
                s = re.sub(r'(w:styleId="Compact".*?)(</w:style>)', r'\1<w:rPr><w:sz w:val="18"/></w:rPr>\2', s, count=1, flags=re.S)
                data = s.encode("utf-8")
            zo.writestr(item, data)
    return out

def docx_path(folder, brd):
    version = re.sub(r"[^\w.\-]", "_", str((brd.get("meta") or {}).get("version") or "0"))
    return os.path.join(folder, "client-pack", f"brd-confirmation-v{version}.docx")

def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    d = sys.argv[1].rstrip("/"); path = os.path.join(d, "brd.yaml")
    if not os.path.exists(path): sys.exit(f"{path} does not exist")
    if not shutil.which("pandoc"): sys.exit("pandoc is not installed (brew install pandoc), so no Word file was built.")
    raw = yaml.safe_load(open(path, encoding="utf-8")) or {}
    brd = brdtool.apply_env(raw, d)
    _, env = envconf.get_env(d)
    md = build_markdown(brd, (env or {}).get("max_vus"), datetime.date.today().isoformat())
    hits = [p.pattern[:30] for p in lint.SECRET if p.search(md)]
    if hits: sys.exit("Secret-like text found in the BRD, so no document was built. Remove it from brd.yaml / environments.yaml and try again.")
    out = docx_path(d, brd); os.makedirs(os.path.dirname(out), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "brd-confirmation.md"); open(src, "w", encoding="utf-8").write(md)
        r = subprocess.run(["pandoc", src, "-f", "markdown-smart-raw_html-tex_math_dollars-yaml_metadata_block", "-o", out, "--reference-doc", styled_reference(tmp)], capture_output=True, text=True)
    if r.returncode: sys.exit("pandoc failed: " + r.stderr.strip())
    pr = brdtool.provenance(brd); c = brdtool.provenance_counts(pr)
    print("Wrote", out); print(" | ".join(f"{b} {c[b]}" for b in brdtool.BASES))

if __name__ == "__main__":
    main()
