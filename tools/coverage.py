#!/usr/bin/env python3
"""Compute profile-by-flow coverage from the BRD, catalogue and recorded runs."""
import json
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brd as brdtool


def compute(project, env_name=None):
    with open(os.path.join(project, "brd.yaml"), encoding="utf-8") as f:
        brd = yaml.safe_load(f) or {}
    with open(os.path.join(project, "api-catalogue.yaml"), encoding="utf-8") as f:
        catalogue = yaml.safe_load(f) or {}
    flows = sorted({str(flow.get("transaction")) for flow in catalogue.get("flows", [])
                    if isinstance(flow, dict) and flow.get("transaction")})
    profiles = []
    for item in brd.get("test_types") or []:
        if not isinstance(item, dict) or brdtool.yes_no(item.get("needed")) is not True:
            continue
        key = brdtool.profile_key(item.get("type"))
        if key and key != "scalability":
            params = item.get("parameters") or {}
            profiles.append({
                "key": key,
                "label": item.get("type"),
                "flows": [str(flow) for flow in (params.get("flows") or [])],
            })
    runs = []
    runs_dir = os.path.join(project, "runs")
    for name in sorted(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else []:
        path = os.path.join(runs_dir, name, "run.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                run = json.load(f)
            if env_name is None or run.get("env") == env_name:
                runs.append(run)
    matrix = []
    for profile in profiles:
        cells = []
        for flow in flows:
            if flow not in profile["flows"]:
                status = "not_selected"
            else:
                matching = [run for run in runs if run.get("profile") == profile["key"]
                            and flow in (run.get("flows") or [])]
                if any(run.get("outcome") == "passed" for run in matching):
                    status = "covered"
                elif matching:
                    status = "attempted"
                else:
                    status = "pending"
            cells.append({"flow": flow, "status": status})
        matrix.append({"profile": profile["key"], "label": profile["label"], "cells": cells})
    return {"flows": flows, "profiles": profiles, "matrix": matrix, "runs": runs}


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python tools/coverage.py <project_dir> [environment]")
    print(json.dumps(compute(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None), indent=2))


if __name__ == "__main__":
    main()
