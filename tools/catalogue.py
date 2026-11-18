#!/usr/bin/env python3
"""API catalogue helper. Usage:
  python tools/catalogue.py check          <api-catalogue.yaml> [brd.yaml]
  python tools/catalogue.py import-openapi <api-catalogue.yaml> <spec.json|yaml> [base_url]
  python tools/catalogue.py import-postman <api-catalogue.yaml> <collection.json>
  python tools/catalogue.py import-har     <api-catalogue.yaml> <capture.har> <base_url>
Imports MERGE into the catalogue (skip duplicates by method+path) and never keep secrets. Requires PyYAML.
"""
import sys, os, re, json, datetime, yaml
from urllib.parse import urlparse, parse_qsl

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "QUERY"}
AUTH = {"none", "bearer", "cookie", "basic", "other"}
SAFE = {"yes", "no", "conditional", "unknown"}
SRC = {"postman", "openapi", "document", "browser", "har"}
CONF = {"high", "medium", "low"}
SENSITIVE_KEYS = re.compile(r"pass(word)?|pwd|token|secret|card|cvv|cvc|iban|ssn|api[_-]?key|authorization|cookie", re.I)
SECRET_PATTERNS = [(re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]{20,}"), "bearer token"),
                   (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "JWT"),
                   (re.compile(r"(?i)(password|passwd|secret|api[_-]?key)\"?\s*[:=]\s*\"?(?!<redacted>|\$\{|\{\{|<)[^\s\",}]{4,}"), "password/secret/key value")]

def blank(v): return v is None or v == "" or v == [] or v == {}

def load(path):
    if not os.path.exists(path): return {"meta": {}, "apis": [], "flows": [], "notes": []}
    return yaml.safe_load(open(path, encoding="utf-8")) or {}

def save(path, d):
    yaml.safe_dump(d, open(path, "w", encoding="utf-8"), sort_keys=False, allow_unicode=True, width=200)

def norm_path(p):
    segs = []
    for s in p.split("/"):
        if re.fullmatch(r"\d+", s) or re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", s) or re.fullmatch(r"[0-9A-Z]{26}", s):
            segs.append("{id}")
        else: segs.append(s)
    return "/".join(segs) or "/"

def redact(o):
    if isinstance(o, dict): return {k: ("<redacted>" if SENSITIVE_KEYS.search(k) else redact(v)) for k, v in o.items()}
    if isinstance(o, list): return [redact(x) for x in o[:3]]
    return o

def merge(path, new, source_type, base_url=None, excluded=None):
    d = load(path)
    d.setdefault("meta", {}); d.setdefault("apis", []); d.setdefault("flows", []); d.setdefault("notes", [])
    if base_url and blank(d["meta"].get("base_url")): d["meta"]["base_url"] = base_url
    d["meta"].setdefault("excluded_hosts", [])
    for h in excluded or []:
        if h not in d["meta"]["excluded_hosts"]: d["meta"]["excluded_hosts"].append(h)
    have = {(a.get("method"), a.get("path")) for a in d["apis"]}
    n = len(d["apis"]); added = 0
    for a in new:
        if (a["method"], a["path"]) in have: continue
        n += 1; added += 1; have.add((a["method"], a["path"]))
        a = {"id": f"API-{n:03d}", **a}
        a.setdefault("transaction", ""); a.setdefault("safe_to_load", "yes" if a["method"] in ("GET", "HEAD", "QUERY") else "unknown")
        a.setdefault("evidence", {})["source_type"] = source_type
        a["evidence"].setdefault("confidence", "medium")
        a["evidence"].setdefault("observed_at", datetime.date.today().isoformat())
        d["apis"].append(a)
    d["meta"].setdefault("created", datetime.date.today().isoformat())
    save(path, d)
    print(f"Added {added} API(s), skipped {len(new)-added} duplicate(s). Total {len(d['apis'])}. Wrote {path}")

def resolve(spec, node, depth=0):
    if isinstance(node, dict) and "$ref" in node and depth < 4:
        cur = spec
        for p in node["$ref"].lstrip("#/").split("/"): cur = cur.get(p, {}) if isinstance(cur, dict) else {}
        return resolve(spec, cur, depth + 1)
    return node or {}

def fields_of(spec, schema):
    s = resolve(spec, schema)
    if s.get("type") == "array": s = resolve(spec, s.get("items"))
    return sorted((s.get("properties") or {}).keys())

def import_openapi(cat, specfile, base=None):
    raw = open(specfile, encoding="utf-8").read()
    spec = json.loads(raw) if raw.lstrip().startswith("{") else yaml.safe_load(raw)
    base = base or (spec.get("servers") or [{}])[0].get("url", "")
    out = []
    for path, item in (spec.get("paths") or {}).items():
        for m, op in item.items():
            if m.upper() not in METHODS or not isinstance(op, dict): continue
            params = [resolve(spec, p) for p in (item.get("parameters") or []) + (op.get("parameters") or [])]
            q = [{"name": p["name"], "example": p.get("example", ""), "required": bool(p.get("required"))} for p in params if p.get("in") == "query"]
            sec = op.get("security", spec.get("security"))
            auth = "bearer" if sec else "none"
            rb = resolve(spec, op.get("requestBody"))
            body = {}
            for ct, c in (rb.get("content") or {}).items():
                body = {"content_type": ct, "notes": "fields: " + ", ".join(fields_of(spec, c.get("schema"))) if fields_of(spec, c.get("schema")) else ""}
                if "example" in c: body["example"] = redact(c["example"])
                break
            resp = {}
            for code, r in (op.get("responses") or {}).items():
                if str(code).startswith("2"):
                    r = resolve(spec, r); cts = r.get("content") or {}; ct = next(iter(cts), "")
                    resp = {"status": int(code) if str(code).isdigit() else code, "content_type": ct,
                            "fields": fields_of(spec, (cts.get(ct) or {}).get("schema")) if ct else []}
                    break
            out.append({"name": op.get("summary") or op.get("operationId") or f"{m.upper()} {path}", "method": m.upper(), "path": path,
                        "auth": auth, "headers": {}, "query_params": q, "request_body": body, "response": resp,
                        "dynamic_values": [], "depends_on": [], "page": "", "business_flow": "", "side_effects": "", "test_data": "",
                        "observed_latency_ms": None, "evidence": {"source": os.path.basename(specfile), "confidence": "high"}})
    merge(cat, out, "openapi", base)

def import_postman(cat, colfile):
    col = json.load(open(colfile, encoding="utf-8"))
    out, hosts = [], set()
    def walk(items, folder=""):
        for it in items:
            if "item" in it: walk(it["item"], (folder + "/" if folder else "") + it.get("name", ""))
            elif "request" in it:
                r = it["request"]; u = r.get("url", {})
                raw = u if isinstance(u, str) else u.get("raw", "")
                parts = urlparse(raw.split("?")[0])
                path = parts.path if parts.scheme else "/" + "/".join(u.get("path", [])) if isinstance(u, dict) else raw
                if parts.scheme: hosts.add(f"{parts.scheme}://{parts.netloc}")
                elif raw.startswith("{{"): hosts.add(raw.split("}}")[0] + "}}")
                if not str(path).startswith("/"): path = "/" + str(path).split("}}", 1)[-1].lstrip("/")
                hdrs = {h["key"]: h.get("value", "") for h in r.get("header", []) if not h.get("disabled")}
                auth = "bearer" if ("auth" in r or any(k.lower() == "authorization" for k in hdrs)) else "none"
                hdrs = {k: v for k, v in hdrs.items() if not SENSITIVE_KEYS.search(k)}
                q = [{"name": x["key"], "example": x.get("value", ""), "required": not x.get("disabled", False)} for x in (u.get("query", []) if isinstance(u, dict) else [])]
                body = {}
                b = r.get("body") or {}
                if b.get("mode") == "raw" and b.get("raw"):
                    try: body = {"content_type": "application/json", "example": redact(json.loads(b["raw"]))}
                    except Exception: body = {"content_type": "text", "notes": "raw body, not JSON"}
                resp = {}
                if it.get("response"): rr = it["response"][0]; resp = {"status": rr.get("code"), "notes": rr.get("name", "")}
                out.append({"name": it.get("name", ""), "method": (r.get("method") or "GET").upper(), "path": norm_path(path), "auth": auth,
                            "headers": hdrs, "query_params": q, "request_body": body, "response": resp, "dynamic_values": [], "depends_on": [],
                            "page": "", "business_flow": folder, "side_effects": "", "test_data": "", "observed_latency_ms": None,
                            "evidence": {"source": f"{os.path.basename(colfile)} > {folder}/{it.get('name','')}", "confidence": "medium"}})
    walk(col.get("item", []))
    merge(cat, out, "postman", sorted(hosts)[0] if hosts else None)

def import_har(cat, harfile, base):
    har = json.load(open(harfile, encoding="utf-8"))["log"]
    bh = urlparse(base).netloc
    pages = {p["id"]: p.get("title", "") for p in har.get("pages", [])}
    out, excl = [], set()
    for e in har.get("entries", []):
        rq, rs = e["request"], e["response"]
        u = urlparse(rq["url"])
        mime = (rs.get("content") or {}).get("mimeType", "")
        if u.netloc != bh:
            if "json" in mime or e.get("_resourceType") in ("xhr", "fetch"): excl.add(u.netloc)
            continue
        if not ("json" in mime or e.get("_resourceType") in ("xhr", "fetch")): continue
        hd = {h["name"].lower(): h["value"] for h in rq.get("headers", [])}
        auth = "bearer" if hd.get("authorization", "").lower().startswith("bearer") else "cookie" if "cookie" in hd else "none"
        keep = {k: v for k, v in hd.items() if k in ("content-type", "accept")}
        body = {}
        pd = rq.get("postData")
        if pd and pd.get("text"):
            try: body = {"content_type": pd.get("mimeType", ""), "example": redact(json.loads(pd["text"]))}
            except Exception: body = {"content_type": pd.get("mimeType", ""), "notes": "non-JSON body"}
        flds = []
        try:
            j = json.loads((rs.get("content") or {}).get("text", "") or "null")
            j = j[0] if isinstance(j, list) and j else j
            flds = sorted(j.keys()) if isinstance(j, dict) else []
        except Exception: pass
        out.append({"name": f"{rq['method']} {norm_path(u.path)}", "method": rq["method"], "path": norm_path(u.path), "auth": auth, "headers": keep,
                    "query_params": [{"name": k, "example": v, "required": False} for k, v in parse_qsl(u.query)][:10], "request_body": body,
                    "response": {"status": rs["status"], "content_type": mime, "fields": flds}, "dynamic_values": [], "depends_on": [],
                    "page": pages.get(e.get("pageref"), ""), "business_flow": "", "side_effects": "", "test_data": "",
                    "observed_latency_ms": round(e.get("time", 0)), "evidence": {"source": os.path.basename(harfile), "confidence": "medium"}})
    merge(cat, out, "har", f"{urlparse(base).scheme}://{bh}", excl)

def check(cat, brdfile):
    if not os.path.exists(cat):
        print(f"ISSUES: catalogue file not found: {cat}"); sys.exit(1)
    d = load(cat); P = []; W = []
    m = d.get("meta") or {}
    has_env = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(cat)), "environments.yaml"))
    for k in ("application", "base_url"):
        if blank(m.get(k)) and not (k == "base_url" and has_env): P.append(f"meta.{k} is empty")
    apis = d.get("apis") or []
    if not apis: P.append("No APIs in the catalogue")
    ids = [a.get("id") for a in apis]
    for i in {x for x in ids if ids.count(x) > 1}: P.append(f"Duplicate id {i}")
    for a in apis:
        i = a.get("id", "?")
        if (a.get("method") or "").upper() not in METHODS: P.append(f"{i}: invalid method")
        if not str(a.get("path", "")).startswith("/"): P.append(f"{i}: path must start with /")
        if (a.get("auth") or "") not in AUTH: P.append(f"{i}: auth must be one of {sorted(AUTH)}")
        if (a.get("safe_to_load") or "") not in SAFE: P.append(f"{i}: safe_to_load must be one of {sorted(SAFE)}")
        ev = a.get("evidence") or {}
        if ev.get("source_type") not in SRC: P.append(f"{i}: evidence.source_type must be one of {sorted(SRC)}")
        if blank(ev.get("source")): P.append(f"{i}: evidence.source is empty")
        if blank((a.get("response") or {}).get("status")): P.append(f"{i}: response.status missing")
        if blank(a.get("transaction")): P.append(f"{i}: not mapped to a BRD transaction")
        for dep in a.get("depends_on") or []:
            if dep not in ids: P.append(f"{i}: depends_on {dep} does not exist")
        for dv in a.get("dynamic_values") or []:
            if dv.get("from_api") not in ids: P.append(f"{i}: dynamic value '{dv.get('name')}' from_api {dv.get('from_api')} does not exist")
        if a.get("safe_to_load") == "unknown": W.append(f"{i}: safe_to_load still unknown")
        if ev.get("confidence") == "low": W.append(f"{i}: low confidence")
        if a.get("method") in ("POST", "PUT", "PATCH", "DELETE") and blank(a.get("side_effects")): W.append(f"{i}: write call without side_effects described")
    text = open(cat, encoding="utf-8").read()
    for rx, label in SECRET_PATTERNS:
        if rx.search(text): P.append(f"Possible secret in file ({label}). Remove it.")
    if brdfile and os.path.exists(brdfile):
        brd = yaml.safe_load(open(brdfile, encoding="utf-8")) or {}
        bt = {t.get("id") for t in (brd.get("transactions") or []) if t.get("id")}
        mapped = {a.get("transaction") for a in apis if a.get("transaction")}
        for t in sorted(bt - mapped): P.append(f"BRD transaction {t} has no API mapped")
        for t in sorted(mapped - bt): P.append(f"API mapped to {t}, which is not in brd.yaml")
        flows = {f.get("transaction") for f in (d.get("flows") or []) if f.get("steps")}
        for t in sorted(bt - flows): W.append(f"No ordered flow defined for {t}")
    else: W.append("brd.yaml not found, BRD mapping not checked")
    if P:
        print(f"ISSUES to fix ({len(P)}):"); [print(f"  {n}. {x}") for n, x in enumerate(P, 1)]
    if W:
        print(f"Warnings ({len(W)}):"); [print(f"  - {x}") for x in W]
    if not P: print("OK: catalogue passes all required checks.")
    sys.exit(1 if P else 0)

def main():
    a = sys.argv[1:]
    try:
        if a[0] == "check" and len(a) in (2, 3): check(a[1], a[2] if len(a) == 3 else os.path.join(os.path.dirname(os.path.abspath(a[1])), "brd.yaml"))
        elif a[0] == "import-openapi" and len(a) in (3, 4): import_openapi(a[1], a[2], a[3] if len(a) == 4 else None)
        elif a[0] == "import-postman" and len(a) == 3: import_postman(a[1], a[2])
        elif a[0] == "import-har" and len(a) == 4: import_har(a[1], a[2], a[3])
        else: sys.exit(__doc__)
    except IndexError: sys.exit(__doc__)

if __name__ == "__main__": main()
