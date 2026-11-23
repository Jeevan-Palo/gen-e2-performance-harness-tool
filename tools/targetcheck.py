#!/usr/bin/env python3
"""Check that the active environment answers the API catalogue's READ calls the same way (status and field names).
Usage: python tools/targetcheck.py <project_dir> [--env NAME]
Sends at most one request per catalogue API, only GET, HEAD or QUERY calls marked safe_to_load=yes that need no login.
Writes <project_dir>/target-check.json and updates `verified` of the environment in environments.yaml. Stops at the first 429 or 503.
"""
import sys, os, re, json, time, datetime, argparse, urllib.request, urllib.error, yaml
from urllib.parse import urlsplit, quote, urlencode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf

READ = {"GET", "HEAD", "QUERY"}
blank = lambda v: v is None or v == "" or v == [] or v == {}

class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, base_url):
        super().__init__()
        self.expected_origin = self.origin(base_url)

    @staticmethod
    def origin(url):
        parsed = urlsplit(url)
        if parsed.username is not None or parsed.password is not None: return None
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme.lower() == "https" else 80)
        return parsed.scheme.lower(), (parsed.hostname or "").lower(), port

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self.origin(req.full_url) != self.expected_origin or self.origin(newurl) != self.expected_origin:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def jp(obj, path):
    for part in path.split("."):
        if part.endswith("[]"):
            obj = obj[part[:-2]][0] if part[:-2] else obj[0]
        else:
            obj = obj[part]
    return obj

def keys_of(body):
    ks = set()
    if isinstance(body, dict):
        ks |= set(body)
        for v in body.values():
            if isinstance(v, list) and v and isinstance(v[0], dict): ks |= set(v[0])
    elif isinstance(body, list) and body and isinstance(body[0], dict): ks |= set(body[0])
    return ks

def call(base, method, path, body, timeout=20):
    data = json.dumps(body).encode() if body not in (None, {}, "") else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json", "Accept": "application/json"})
    t = time.time()
    try:
        opener = urllib.request.build_opener(SameOriginRedirectHandler(base))
        with opener.open(req, timeout=timeout) as r: status, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: status, text = e.code, e.read().decode("utf-8", "replace")
    except Exception as e: return None, None, round((time.time() - t) * 1000), str(e)[:120]
    try: parsed = json.loads(text)
    except Exception: parsed = None
    return status, parsed, round((time.time() - t) * 1000), None

def set_verified(envfile, name, date, by, note):
    lines = open(envfile, encoding="utf-8").read().split("\n"); i = 0
    while i < len(lines) and not re.fullmatch(rf"  {re.escape(name)}:\s*", lines[i]): i += 1
    j = i + 1
    while j < len(lines) and (lines[j].startswith("    ") or not lines[j].strip()):
        if lines[j].startswith("    verified:"):
            lines[j] = "    verified: {date: \"%s\", by: \"%s\", note: \"%s\"}" % (date, by, note.replace('"', "'")); open(envfile, "w", encoding="utf-8").write("\n".join(lines)); return True
        j += 1
    return False

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--env"); a = ap.parse_args(); d = a.project.rstrip("/")
    name, env = envconf.get_env(d, a.env)
    if env is None: sys.exit("No environments.yaml or unknown environment.")
    if env.get("authorisation") in (None, "", "not_confirmed"): sys.exit(f"Environment '{name}': authorisation is not_confirmed, so no request is sent.")
    base = str(env["base_url"]).rstrip("/")
    cat = yaml.safe_load(open(os.path.join(d, "api-catalogue.yaml"), encoding="utf-8")) or {}
    bp = os.path.join(d, "brd.yaml"); active = None
    if os.path.exists(bp): active = {t.get("id") for t in (yaml.safe_load(open(bp, encoding="utf-8")) or {}).get("transactions", []) if t.get("id")}
    apis = [x for x in cat.get("apis", []) if not active or x.get("transaction") in active]
    done, store, results, order = set(), {}, [], list(apis)
    while order:
        prog = False
        for x in list(order):
            if all(dep in done or dep not in {y["id"] for y in apis} for dep in x.get("depends_on") or []):
                order.remove(x); prog = True; done.add(x["id"]); results.append(check_one(x, base, store))
                if results[-1].get("status") in (429, 503): print("Stopped: the target answered 429 or 503."); order = []; break
                time.sleep(0.2)
        if not prog:
            for x in order: results.append({"id": x["id"], "call": f"{x.get('method')} {x.get('path')}", "result": "skipped", "detail": "dependency cycle"})
            break
    ok = [r for r in results if r["result"] == "ok"]; bad = [r for r in results if r["result"] == "differs"]; skip = [r for r in results if r["result"] == "skipped"]
    for r in results: print(f"  {r['id']:<8} {r['call']:<40} {str(r.get('status') or '-'):>4} {str(r.get('ms') or '-'):>6} ms  {r['result'].upper()}  {r.get('detail', '')}")
    now = datetime.datetime.now(datetime.timezone.utc)
    summary = {"environment": name, "base_url": base, "checked_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "calls_ok": len(ok), "calls_differ": len(bad), "calls_skipped": len(skip), "results": results}
    json.dump(summary, open(os.path.join(d, "target-check.json"), "w"), indent=1)
    note = f"{len(ok)} of {len(ok)+len(bad)} read calls matched the catalogue (status and field names); {len(skip)} skipped (writes, logins or no value)"
    if bad: note = f"{len(bad)} read call(s) differ from the catalogue; " + note
    set_verified(envconf.path(d), name, now.strftime("%Y-%m-%d"), "tools/targetcheck.py", note)
    print(f"\n{'MATCH' if ok and not bad else 'DIFFERENCES' if bad else 'NOTHING CHECKED'}: {note}. Saved target-check.json and updated the environment's verified note.")
    sys.exit(0 if ok and not bad else 1)

def check_one(x, base, store):
    r = {"id": x["id"], "call": f"{x.get('method')} {x.get('path')}"}
    m = str(x.get("method", "")).upper()
    if m not in READ: return {**r, "result": "skipped", "detail": "write call, not sent"}
    if x.get("safe_to_load") != "yes": return {**r, "result": "skipped", "detail": f"safe_to_load={x.get('safe_to_load')}"}
    if x.get("auth") not in (None, "", "none"): return {**r, "result": "skipped", "detail": "needs login, credentials are not stored"}
    path = x.get("path", "")
    for ph in re.findall(r"\{(\w+)\}", path):
        val = None
        for dv in x.get("dynamic_values") or []:
            if dv.get("name") != ph: continue
            src = store.get(dv.get("from_api"))
            if src is not None and dv.get("json_path"):
                try: val = jp(src, dv["json_path"]); break
                except (KeyError, IndexError, TypeError, AttributeError): pass
        if val is None: return {**r, "result": "skipped", "detail": f"no value for {{{ph}}}"}
        path = path.replace("{" + ph + "}", quote(str(val), safe=""))
    query = []
    for q in x.get("query_params") or []:
        if q.get("required") is not True: continue
        name, value = q.get("name"), q.get("example")
        if not isinstance(name, str) or not name or not isinstance(value, (str, int, float, bool)) or value == "":
            return {**r, "result": "skipped", "detail": f"no usable example for required query parameter {name or '<unnamed>'}"}
        query.append((name, value))
    qp = urlencode(query)
    body = (x.get("request_body") or {}).get("example")
    status, parsed, ms, err = call(base, m, path + ("?" + qp if qp else ""), body)
    if status is None: return {**r, "result": "differs", "ms": ms, "detail": f"no answer: {err}"}
    store[x["id"]] = parsed
    exp = (x.get("response") or {}).get("status")
    r.update(status=status, ms=ms)
    if isinstance(exp, int) and not isinstance(exp, bool):
        if status != exp: return {**r, "result": "differs", "detail": f"status {status}, catalogue says {exp}"}
    elif isinstance(exp, str) and exp.isdigit():
        if status != int(exp): return {**r, "result": "differs", "detail": f"status {status}, catalogue says {exp}"}
    elif not 200 <= status < 300:
        return {**r, "result": "differs", "detail": f"status {status}, catalogue says {exp}"}
    want = set((x.get("response") or {}).get("fields") or []); have = keys_of(parsed)
    miss = sorted(want - have) if want else []
    return {**r, "result": "differs", "detail": "missing fields: " + ", ".join(miss)} if miss else {**r, "result": "ok"}

if __name__ == "__main__": main()
