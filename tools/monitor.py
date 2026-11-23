#!/usr/bin/env python3
"""Server-side monitoring during a run.
Sources (set per environment in environments.yaml, monitoring.source):
  docker_stats  built: samples CPU and memory of the listed Docker containers while the run is in progress (and of k6 itself)
  azure | dynatrace | client_apm   not built yet: runk6 says so and collects nothing
Usage: python tools/monitor.py check <project_dir>     one quick sample of the configured containers (preflight)
CPU % follows Docker's convention: 100% = one full core (can exceed 100 on several cores).
"""
import sys, os, re, json, time, subprocess, threading, datetime, statistics

UNITS = {"b": 1, "kb": 1e3, "kib": 1024, "mb": 1e6, "mib": 1024**2, "gb": 1e9, "gib": 1024**3, "tb": 1e12, "tib": 1024**4}
FMT = "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"
iso = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_bytes(s):
    m = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]+)\s*", s or "")
    return float(m.group(1)) * UNITS.get(m.group(2).lower(), 1) if m else None

def parse_line(line):
    """'name|12.34%|45.2MiB / 7.6GiB|0.58%' -> dict, or None"""
    p = line.strip().split("|")
    if len(p) != 4: return None
    try:
        used = parse_bytes(p[2].split("/")[0])
        return {"series": p[0], "cpu_pct": float(p[1].strip().rstrip("%")), "mem_mib": round(used / 1024**2, 2) if used is not None else None,
                "mem_pct": float(p[3].strip().rstrip("%") or 0)}
    except ValueError:
        return None

def docker_sample(containers, timeout=40):
    """One sample of all listed containers. Returns (rows, error_text_or_None)."""
    try:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format", FMT, *containers], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError: return [], "docker command not found"
    except subprocess.TimeoutExpired: return [], "docker stats timed out"
    rows = [x for x in (parse_line(l) for l in r.stdout.splitlines()) if x]
    err = None
    if r.returncode != 0 or len(rows) < len(containers):
        found = {x["series"] for x in rows}
        missing = [c for c in containers if c not in found]
        err = ((r.stderr or "").strip().splitlines() or ["docker stats failed"])[0][:200] if r.returncode != 0 else f"no data for: {', '.join(missing)}"
    return rows, err

def docker_ready(containers):
    rows, err = docker_sample(containers)
    return (len(rows) > 0 and err is None), (err or "")

def check_visibility(source, containers):
    if source == "none": return [], "No monitoring source is configured; monitoring is not visible"
    if source != "docker_stats": return [], f"Monitoring collector '{source}' is not built; visibility cannot be confirmed"
    if not containers: return [], "No monitoring containers are configured"
    rows, err = docker_sample(containers)
    if err or not rows: return rows, err or "no monitoring samples returned"
    return rows, None

def cpu_seconds(pid):
    """Cumulative CPU seconds of a process, or None."""
    try:
        st = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return (int(st[11]) + int(st[12])) / os.sysconf("SC_CLK_TCK")
    except Exception: pass
    try:
        t = subprocess.run(["ps", "-o", "time=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
        parts = [float(x) for x in t.split(":")]
        sec = 0.0
        for x in parts: sec = sec * 60 + x
        return sec
    except Exception: return None

def rss_mib(pid):
    try:
        for l in open(f"/proc/{pid}/status"):
            if l.startswith("VmRSS:"): return round(int(l.split()[1]) / 1024, 2)
    except Exception: pass
    try:
        kb = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
        return round(int(kb) / 1024, 2)
    except Exception: return None

def pct95(v):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))] if v else None

def summarise(samples, window):
    out = {}
    for name in sorted({s["series"] for s in samples}):
        a = [s for s in samples if s["series"] == name]
        st = [s for s in a if window is None or window[0] <= s["t_s"] <= window[1]] or a
        cpu = [s["cpu_pct"] for s in st if s.get("cpu_pct") is not None]; mem = [s["mem_mib"] for s in st if s.get("mem_mib") is not None]
        out[name] = {"samples": len(a), "steady_samples": len(st),
                     "cpu_avg": round(statistics.mean(cpu), 1) if cpu else None, "cpu_p95": round(pct95(cpu), 1) if cpu else None,
                     "cpu_max_run": round(max([s["cpu_pct"] for s in a if s.get("cpu_pct") is not None] or [0]), 1) if a else None,
                     "mem_avg_mib": round(statistics.mean(mem), 1) if mem else None,
                     "mem_max_mib": round(max([s["mem_mib"] for s in a if s.get("mem_mib") is not None] or [0]), 1) if a else None}
    return out

class DockerSampler:
    def __init__(self, containers, interval=5, pid=None):
        self.containers, self.interval, self.pid = list(containers), max(2, int(interval)), pid
        self.samples, self.errors, self.t0 = [], [], None
        self._stop = threading.Event(); self._th = threading.Thread(target=self._loop, daemon=True)
    def start(self): self.t0 = time.time(); self._th.start(); return self
    def _loop(self):
        last_cpu = None
        while not self._stop.is_set():
            began = time.time()
            rows, err = docker_sample(self.containers)
            t = round(time.time() - self.t0, 1)
            for r in rows: self.samples.append({"t_s": t, **r})
            if err and err not in self.errors: self.errors.append(err)
            if self.pid:
                cs, now = cpu_seconds(self.pid), time.time()
                if cs is not None and last_cpu is not None and now > last_cpu[1]:
                    self.samples.append({"t_s": round(now - self.t0, 1), "series": "k6 (load generator)", "cpu_pct": round(max(0.0, (cs - last_cpu[0]) / (now - last_cpu[1]) * 100), 1), "mem_mib": rss_mib(self.pid), "mem_pct": None})
                if cs is not None: last_cpu = (cs, now)
            self._stop.wait(max(0.0, self.interval - (time.time() - began)))
    def stop(self, steady_window=None):
        self._stop.set(); self._th.join(timeout=60); end = time.time()
        return {"source": "docker_stats", "status": "collected" if self.samples else "unavailable", "containers": self.containers, "interval_seconds": self.interval,
                "start_utc": iso(self.t0), "end_utc": iso(end), "duration_s": round(end - self.t0, 1), "steady_window_s": steady_window,
                "cpu_note": "CPU % follows Docker: 100% = one full core", "errors": self.errors,
                "summary": summarise(self.samples, steady_window), "samples": self.samples}

def main():
    if len(sys.argv) != 3 or sys.argv[1] != "check": sys.exit(__doc__)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import envconf
    name, env = envconf.get_env(sys.argv[2])
    if env is None: sys.exit("No environments.yaml or active environment")
    m = env.get("monitoring") or {}
    print(f"Environment '{name}': monitoring source = {m.get('source')}")
    rows, err = check_visibility(m.get("source", "none"), m.get("containers") or [])
    for r in rows: print(f"  {r['series']:<28} CPU {r['cpu_pct']:>6.1f}%   memory {r['mem_mib']:>8.1f} MiB")
    print("OK: monitoring is visible." if not err and rows else f"PROBLEM: {err}")
    sys.exit(0 if (rows and not err) else 1)

if __name__ == "__main__": main()
