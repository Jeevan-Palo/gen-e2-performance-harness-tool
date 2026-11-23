#!/usr/bin/env python3
"""Check that the active environment answers the API catalogue's READ calls the same way (status and field names).
Usage: python tools/targetcheck.py <project_dir> [--env NAME]
Sends at most one request per catalogue API, only GET, HEAD or QUERY calls marked safe_to_load=yes. Calls that need a login are sent
only when the environment's credentials_env_vars (a user name and a password variable) are set in your shell: the check then sends ONE
login POST (the catalogue API whose response feeds another API's dynamic_values), keeps the token in memory only, and uses it for the
read calls. Credentials and tokens are never printed or written. All other write calls are never sent.
Writes <project_dir>/target-check.json and updates `verified` of the environment in environments.yaml. Stops at the first 429 or 503.
"""
import sys, os, re, json, time, datetime, argparse, urllib.request, urllib.error, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envconf

READ = {"GET", "HEAD", "QUERY"}
blank = lambda v: v is None or v == "" or v == [] or v == {}

def jp(obj, path):
    for part in path.removeprefix("$").lstrip(".").split("."):
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

def call(base, method, path, body, timeout=20, token=None):
    data = json.dumps(body).encode() if body not in (None, {}, "") else None
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "perf-harness-targetcheck/1.0"}  # the default Python-urllib agent is refused by some CDNs (Cloudflare 1010)
    if token: headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: status, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: status, text = e.code, e.read().decode("utf-8", "replace")
    except Exception as e: return None, None, round((time.time() - t) * 1000), str(e)[:120]
    try: parsed = json.loads(text)
    except Exception: parsed = None
    return status, parsed, round((time.time() - t) * 1000), None

SECRET_KEY = re.compile(r"pass(word)?|pwd|secret", re.I)
TOKEN_NAME = re.compile(r"token", re.I)
USER_KEY = re.compile(r"^(user(name)?|email|login)$", re.I)

def credentials(env):
    """(user, password) read from the environment variables named in credentials_env_vars, or None if either is not set."""
    names = env.get("credentials_env_vars") or []
    u = next((os.environ.get(n) for n in names if re.search(r"USER|EMAIL|LOGIN", n) and os.environ.get(n)), None)
    pw = next((os.environ.get(n) for n in names if re.search(r"PASS|SECRET", n) and os.environ.get(n)), None)
    return (u, pw) if u and pw else None

def login_body(example, creds):
    out = {}
    for k, v in (example or {}).items():
        out[k] = creds[1] if SECRET_KEY.search(k) else creds[0] if USER_KEY.match(k) else v
    return out

def server_message(parsed):
    """The server's own error text (never the request), cut short, to tell a bad login from a block."""
    m = parsed.get("message") if isinstance(parsed, dict) else None
    return f": {str(m)[:100]}" if m else ""

def set_verified(envfile, name, date, by, note):
    lines = open(envfile, encoding="utf-8").read().split("\n"); i = 0
    while i < len(lines) and not re.fullmatch(rf"  {re.escape(name)}:\s*", lines[i]): i += 1
    j = i + 1
    while j < len(lines) and (lines[j].startswith("    ") or not lines[j].strip()):
        if lines[j].startswith("    verified:"):
            lines[j] = "    verified: {date: \"%s\", by: \"%s\", note: \"%s\"}" % (date, by, note.replace('"', "'"))
            k = j + 1  # drop the block-style children of the old value (files rewritten by yaml.safe_dump)
            while k < len(lines) and lines[k].startswith("      "): k += 1
            del lines[j + 1:k]
            open(envfile, "w", encoding="utf-8").write("\n".join(lines)); return True
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
    ids = {y["id"] for y in apis}
    login_ids = {dv.get("from_api") for y in apis for dv in y.get("dynamic_values") or [] if dv.get("json_path") and dv.get("from_api") in ids}
    ctx = {"login_ids": login_ids, "creds": credentials(env), "token": {}}
    done, store, results, order = set(), {}, [], list(apis)
    while order:
        prog = False
        for x in list(order):
            if all(dep in done or dep not in {y["id"] for y in apis} for dep in x.get("depends_on") or []):
                order.remove(x); prog = True; done.add(x["id"]); results.append(check_one(x, base, store, ctx))
                if results[-1].get("status") in (429, 503): print("Stopped: the target answered 429 or 503."); order = []; break
                time.sleep(0.2)
        if not prog:
            for x in order: results.append({"id": x["id"], "call": f"{x.get('method')} {x.get('path')}", "result": "skipped", "detail": "dependency cycle"})
            break
    if any(r["result"] == "login" for r in results): print("  (login is not counted as a matched read call)")
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

def check_one(x, base, store, ctx):
    r = {"id": x["id"], "call": f"{x.get('method')} {x.get('path')}"}
    m = str(x.get("method", "")).upper()
    if x["id"] in ctx["login_ids"] and m == "POST" and x.get("auth") in (None, "", "none"):
        if not ctx["creds"]: return {**r, "result": "skipped", "detail": "login: set the variables in credentials_env_vars (user and password) in your shell"}
        status, parsed, ms, err = call(base, m, x.get("path", ""), login_body((x.get("request_body") or {}).get("example"), ctx["creds"]))
        if status is None: return {**r, "result": "differs", "ms": ms, "detail": f"no answer: {err}"}
        r.update(status=status, ms=ms)
        if not 200 <= status < 300: return {**r, "result": "differs", "detail": f"login answered {status}" + server_message(parsed)}
        store[x["id"]] = parsed
        return {**r, "result": "login", "detail": "logged in; token kept in memory only"}
    if m not in READ: return {**r, "result": "skipped", "detail": "write call, not sent"}
    if x.get("safe_to_load") != "yes": return {**r, "result": "skipped", "detail": f"safe_to_load={x.get('safe_to_load')}"}
    dvs = x.get("dynamic_values") or []; token = None
    if x.get("auth") not in (None, "", "none"):
        for dv in dvs:
            if TOKEN_NAME.search(str(dv.get("name"))) and store.get(dv.get("from_api")) is not None and dv.get("json_path"):
                try: token = jp(store[dv["from_api"]], dv["json_path"])
                except Exception: pass
        if not token: return {**r, "result": "skipped", "detail": "needs login: set the credentials_env_vars in your shell and make sure the login succeeds"}
    path = x.get("path", "")
    for ph in re.findall(r"\{(\w+)\}", path):
        val = None
        for dv in [d for d in dvs if not TOKEN_NAME.search(str(d.get("name")))]:
            src = store.get(dv.get("from_api"))
            if src is not None and dv.get("json_path"):
                try: val = jp(src, dv["json_path"]); break
                except Exception: pass
        if val is None: return {**r, "result": "skipped", "detail": f"no value for {{{ph}}}"}
        path = path.replace("{" + ph + "}", str(val))
    qp = "&".join(f"{q['name']}={q.get('example','')}" for q in x.get("query_params") or [] if q.get("required") and q.get("example") != "")
    body = (x.get("request_body") or {}).get("example")
    status, parsed, ms, err = call(base, m, path + ("?" + qp if qp else ""), body, token=token)
    if status is None: return {**r, "result": "differs", "ms": ms, "detail": f"no answer: {err}"}
    store[x["id"]] = parsed
    exp = (x.get("response") or {}).get("status")
    r.update(status=status, ms=ms)
    if not (200 <= status < 300) or (isinstance(exp, int) and 200 <= exp < 300 and not 200 <= status < 300): return {**r, "result": "differs", "detail": f"status {status}, catalogue says {exp}"}
    want = set((x.get("response") or {}).get("fields") or []); have = keys_of(parsed)
    miss = sorted(want - have) if want else []
    return {**r, "result": "differs", "detail": "missing fields: " + ", ".join(miss)} if miss else {**r, "result": "ok"}

if __name__ == "__main__": main()
