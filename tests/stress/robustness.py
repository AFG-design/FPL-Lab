#!/usr/bin/env python3
"""Robustness drive for build.py: one baseline run, then missing / corrupt / wrong-shape inputs.

Everything runs inside the scratch copy /tmp/claude-0/robust (never the live repo).
FPL API responses are cached outside the repo so every scenario sees identical network input.
Only write into the live repo: tests/stress/out/robustness.json.

Usage: python3 tests/stress/robustness.py
"""
import hashlib, io, json, os, runpy, shutil, subprocess, sys, time

ORIG = "/home/claude/fpl-lab"
COPY = "/tmp/claude-0/robust"
SNAP = "/tmp/claude-0/robust-snapshot"
APICACHE = "/tmp/claude-0/robust-apicache"
RESULT = os.path.join(ORIG, "tests", "stress", "out", "robustness.json")
API = "https://fantasy.premierleague.com/api"
TEAM = "8122679"
INPUTS = ["odds/odds.json", "odds/players.json", "priors.json", "europe.json",
          "understat/fpl_players.json", "understat/shots.json", "crowd/latest.json", "history/status.json"]
CORRUPT = '{"broken": '
SHAPES = [("odds/odds.json", "{}"), ("odds/odds.json", '{"matches": []}'),
          ("crowd/latest.json", "{}"), ("crowd/latest.json", '{"near": {}}')]
STRIP_KEYS = {"built", "build_secs", "updated"}  # timestamps that always differ between runs


def worker(copy, out):
    """Run build.py in the copy, with API responses served from the on-disk cache when present."""
    import urllib.request
    real = urllib.request.urlopen
    os.makedirs(APICACHE, exist_ok=True)

    def cached(req, *a, **k):
        url = str(getattr(req, "full_url", req))
        if not url.startswith(API):
            return real(req, *a, **k)
        p = os.path.join(APICACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
        if not os.path.exists(p):
            with real(req, *a, **k) as r:
                body = r.read()
            with open(p + ".tmp", "wb") as f:
                f.write(body)
            os.replace(p + ".tmp", p)
        return io.BytesIO(open(p, "rb").read())

    urllib.request.urlopen = cached
    sys.path[0] = copy  # import build's modules from the copy, not from tests/stress
    os.chdir(copy)
    sys.argv = ["build.py", TEAM, out]
    runpy.run_path(os.path.join(copy, "build.py"), run_name="__main__")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def snapshot():
    """Pristine inputs taken from the copy before any build has touched it, plus history/."""
    if os.path.isdir(SNAP):
        shutil.rmtree(SNAP)
    os.makedirs(os.path.join(SNAP, "history"))
    for rel in INPUTS:
        os.makedirs(os.path.dirname(os.path.join(SNAP, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(COPY, rel), os.path.join(SNAP, rel))
    for f in os.listdir(os.path.join(COPY, "history")):
        shutil.copyfile(os.path.join(COPY, "history", f), os.path.join(SNAP, "history", f))
    return {rel: ("same" if sha(os.path.join(ORIG, rel)) == sha(os.path.join(COPY, rel)) else "differs")
            for rel in INPUTS}


def restore():
    for rel in INPUTS:
        os.makedirs(os.path.dirname(os.path.join(COPY, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(SNAP, rel), os.path.join(COPY, rel))
    for f in os.listdir(os.path.join(SNAP, "history")):
        shutil.copyfile(os.path.join(SNAP, "history", f), os.path.join(COPY, "history", f))


def apply(mode, rel, content):
    p = os.path.join(COPY, rel)
    if mode == "missing":
        os.remove(p)
    else:
        open(p, "w").write(CORRUPT if mode == "corrupt" else content)


def strip(v):
    if isinstance(v, dict):
        return {k: strip(x) for k, x in v.items() if k not in STRIP_KEYS}
    if isinstance(v, list):
        return [strip(x) for x in v]
    return v


def is_empty(v):
    return v is None or (hasattr(v, "__len__") and len(v) == 0)


def run(name):
    rundir = os.path.join(COPY, "runs", name)
    shutil.rmtree(rundir, ignore_errors=True)
    os.makedirs(rundir)
    shutil.copytree(os.path.join(COPY, "site", "badges"), os.path.join(rundir, "badges"))
    out = os.path.join(rundir, "data.json")
    t = time.time()
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", COPY, out],
                       cwd=COPY, capture_output=True, text=True, timeout=900)
    return p, round(time.time() - t, 1), out


def summarise(rec, data, base, top5):
    bp = {p["id"]: p for p in base["players"]}
    cp = {p["id"]: p for p in data["players"]}
    rec["n_players"] = len(cp)
    rec["plan_keys"] = sorted(data.get("plans") or {})
    rec["meta_odds"] = data["meta"].get("odds")
    rec["crowd_is_null"] = data.get("crowd") is None
    rec["gw9_xp_top5"] = {bp[i]["name"]: (cp[i]["xp"].get("9") if i in cp else "absent") for i in top5}
    rec["players_xp_changed"] = sum(1 for i in bp if i in cp and cp[i]["xp"] != bp[i]["xp"])
    rec["players_dropped"] = sum(1 for i in bp if i not in cp)
    rec["players_added"] = sum(1 for i in cp if i not in bp)
    rec["top_keys_nulled_or_empty"] = [k for k in base if k != "players" and not is_empty(base[k]) and is_empty(data.get(k))]
    rec["top_keys_changed"] = sorted(k for k in set(base) | set(data)
                                     if k != "players" and strip(base.get(k)) != strip(data.get(k)))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
        return
    if not os.path.isdir(COPY) or os.path.exists(os.path.join(COPY, ".git")):
        sys.exit("copy missing or still has .git: " + COPY)
    snap_check = snapshot()
    scen = [("baseline", None, None, None)]
    for rel in INPUTS:
        scen.append((f"missing__{rel}", "missing", rel, None))
        scen.append((f"corrupt__{rel}", "corrupt", rel, None))
    for rel, content in SHAPES:
        scen.append((f"shape__{rel}__{content}", "shape", rel, content))

    results, base, top5, base_summary = [], None, None, None
    for name, mode, rel, content in scen:
        restore()
        if mode:
            apply(mode, rel, content)
        p, wall, out = run(name.replace("/", "_").replace(" ", ""))
        rec = {"scenario": name, "mode": mode, "input": rel, "content": content,
               "exit_code": p.returncode, "crashed": p.returncode != 0, "wall_secs": wall}
        rec["stdout_notes"] = [l for l in p.stdout.splitlines() if l.strip() and not l.startswith("wrote ")]
        if p.returncode != 0:
            err = [l for l in p.stderr.strip().splitlines() if l.strip()]
            rec["last_error"] = err[-1] if err else ""
            rec["traceback_tail"] = err[-6:]
        else:
            data = json.load(open(out))
            rec["build_secs"] = data["meta"].get("build_secs")
            if base is None:
                base = data
                top5 = [p_["id"] for p_ in data["players"][:5]]
                base_summary = {"n_players": len(data["players"]), "plan_keys": sorted(data["plans"]),
                                "meta_odds": data["meta"].get("odds"), "crowd_is_null": data.get("crowd") is None,
                                "next_gw": data["meta"].get("next_gw"),
                                "gw9_xp_top5": {p_["name"]: p_["xp"].get("9") for p_ in data["players"][:5]}}
                rec["note"] = "baseline"
            else:
                summarise(rec, data, base, top5)
        print(f"{name:55s} exit={p.returncode} wall={wall}s", file=sys.stderr, flush=True)
        results.append(rec)
    restore()
    if base is None:
        sys.exit("baseline crashed; see results")
    doc = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "copy": COPY, "api_cache": APICACHE,
           "api_note": "FPL API responses cached on first fetch so all runs share one snapshot of the API",
           "snapshot_matches_original": snap_check, "baseline": base_summary, "scenarios": results}
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    json.dump(doc, open(RESULT, "w"), indent=1)
    print("wrote", RESULT, file=sys.stderr)


if __name__ == "__main__":
    main()
