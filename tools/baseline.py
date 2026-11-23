#!/usr/bin/env python3
"""Check baseline-run consistency and record explicit human sign-off."""
import argparse
import datetime
import json
import math
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brd as brdtool
import envconf


def _metric_values(run_dir):
    path = os.path.join(run_dir, "summary.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        metrics = (json.load(f) or {}).get("metrics") or {}
    values = {}
    for key, data in metrics.items():
        if not isinstance(data, dict):
            continue
        if key.startswith("transaction_duration{"):
            for percentile in ("p(50)", "p(90)", "p(95)", "p(99)"):
                if data.get(percentile) is not None:
                    values[f"{key}.{percentile}"] = float(data[percentile])
        elif key == "http_reqs" and data.get("rate") is not None:
            values["throughput_tps"] = float(data["rate"])
        elif key == "http_req_failed" and data.get("value") is not None:
            values["error_rate"] = float(data["value"])
    monitor_path = os.path.join(run_dir, "monitoring.json")
    if os.path.isfile(monitor_path):
        with open(monitor_path, encoding="utf-8") as f:
            components = (json.load(f) or {}).get("summary") or {}
        for component, data in components.items():
            if not isinstance(data, dict): continue
            for key in ("cpu_avg", "mem_avg_mib"):
                if data.get(key) is not None:
                    values[f"monitoring.{component}.{key}"] = float(data[key])
    return values


def check(project, env_name=None):
    with open(os.path.join(project, "brd.yaml"), encoding="utf-8") as f:
        brd = yaml.safe_load(f) or {}
    profile = next((p for p in (brd.get("test_types") or [])
                    if isinstance(p, dict) and brdtool.profile_key(p.get("type")) == "baseline"), {})
    params = profile.get("parameters") or {}
    try:
        count = int(params["repeat_runs"])
        limit = float(params["max_variance_pct"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("BRD baseline repeat_runs and max_variance_pct must be completed")
    if count < 2 or not math.isfinite(limit) or limit <= 0:
        raise ValueError("BRD baseline repeat_runs must be at least 2 and max_variance_pct must be positive")
    active, _ = envconf.get_env(project, env_name)
    runs_dir = os.path.join(project, "runs")
    attempts = []
    for name in sorted(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else []:
        path = os.path.join(runs_dir, name, "run.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                run = json.load(f)
            if run.get("env") == active and run.get("profile") == "baseline":
                attempts.append((name, run))
    selected = attempts[-count:]
    result = {
        "checked_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": active,
        "required_runs": count,
        "max_variance_pct": limit,
        "run_ids": [name for name, _ in selected],
        "consistent": False,
        "signed_off": False,
        "metrics": {},
    }
    if len(selected) != count:
        result["reason"] = f"Found {len(selected)} of {count} required baseline runs."
    elif any(run.get("outcome") != "passed" for _, run in selected):
        result["reason"] = "The most recent baseline attempts include a run that did not pass."
    elif len({(tuple(run.get("flows") or []), run.get("vus")) for _, run in selected}) != 1:
        result["reason"] = "Baseline runs used different flow selections or user counts."
    else:
        run_metrics = [_metric_values(os.path.join(runs_dir, name)) for name, _ in selected]
        if any(values is None for values in run_metrics):
            result["reason"] = "A baseline run has no summary.json."
        else:
            common = set.intersection(*(set(values) for values in run_metrics))
            for key in sorted(common):
                samples = [values[key] for values in run_metrics]
                mean = sum(samples) / len(samples)
                cv = 0.0 if mean == 0 and len(set(samples)) == 1 else (
                    math.inf if mean == 0 else math.sqrt(sum((x - mean) ** 2 for x in samples) / len(samples)) / abs(mean) * 100
                )
                result["metrics"][key] = {
                    "values": samples,
                    "mean": mean,
                    "variance_pct": cv if math.isfinite(cv) else None,
                    "within_limit": math.isfinite(cv) and cv < limit,
                }
            result["consistent"] = bool(common) and all(v["within_limit"] for v in result["metrics"].values())
            result["reason"] = "All common metrics are under the variance limit." if result["consistent"] else (
                "One or more common metrics are not under the variance limit." if common else
                "The runs have no common measurable metrics."
            )
    return result


def save(project, result):
    path = os.path.join(project, "baseline-check.json")
    old = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f) or {}
    if (old.get("run_ids") != result.get("run_ids") or old.get("environment") != result.get("environment")
            or old.get("max_variance_pct") != result.get("max_variance_pct") or not result.get("consistent")):
        old.pop("sign_off", None)
    result["sign_off"] = old.get("sign_off")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["check", "sign-off"])
    ap.add_argument("project")
    ap.add_argument("--env")
    ap.add_argument("--by")
    ap.add_argument("--date", help="Sign-off date in YYYY-MM-DD format")
    args = ap.parse_args()
    try:
        result = check(args.project, args.env)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        sys.exit(str(exc))
    path = save(args.project, result)
    if args.command == "sign-off":
        if not result["consistent"]:
            sys.exit("Baseline is not consistent; sign-off is not allowed. Run baseline check and review its metrics.")
        if not args.by or not args.date:
            sys.exit("Baseline sign-off requires --by and --date (YYYY-MM-DD), supplied by the human approver.")
        try:
            signed_date = datetime.date.fromisoformat(args.date)
        except ValueError:
            sys.exit("--date must be a valid YYYY-MM-DD date.")
        result["sign_off"] = {
            "by": args.by, "date": signed_date.isoformat(), "run_ids": result["run_ids"],
            "max_variance_pct": result["max_variance_pct"],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f"Baseline check saved to {path}")
    sys.exit(0 if result["consistent"] else 1)


if __name__ == "__main__":
    main()
