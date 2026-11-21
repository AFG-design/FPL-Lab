"""Run the real build.py and validate.py offline, in a temporary copy of the repo (shared by the build-level tests).

The FPL API is served from recorded responses (tests/fixtures/season_end_api.json.gz: bootstrap, fixtures, live and
one entry, no rival or league data; the manager's name is replaced). Any other fetch (rivals, the overall leader, the
deployed site) fails, as a flaky network would, and the build must carry on without it. Built from the FL-060 test.
"""
import gzip
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
import tempfile
from unittest import mock
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "season_end_api.json.gz"
CROWD_FIXTURE = ROOT / "tests" / "fixtures" / "season_end_crowd.json.gz"
API = "https://fantasy.premierleague.com/api"
TEAM_ID = "8122679"
_GW_FILE_RE = re.compile(r"_gw(\d+)\.json$")


def _trim_gws_dict(gws, cur):
    """Keep only integer-keyed gameweek entries <= cur."""
    if not isinstance(gws, dict):
        return gws
    return {k: v for k, v in gws.items() if not (k.isdigit() and int(k) > cur)}


def _align_repo_to_gw(repo, cur):
    """Make the temporary repo copy match the recorded API fixture's gameweek (cur).

    main's live crowd/latest.json, crowd/history.json and history/ files advance on every gameweek
    rollover, while season_end_api.json.gz is frozen at cur (GW10) with events truncated to <= cur.
    Without aligning the copy to cur, build.py crashes at crowd['gw'] > cur (StopIteration) and
    validate.py fails on settled awards past cur_gw. Runs before prepare(repo) so tests can still
    override or corrupt any file in the copy.
    """
    crowd_dir = repo / "crowd"
    crowd_dir.mkdir(exist_ok=True)
    with gzip.open(CROWD_FIXTURE, "rt") as f:
        (crowd_dir / "latest.json").write_text(f.read())

    hist_dir = repo / "history"
    if hist_dir.is_dir():
        for p in list(hist_dir.iterdir()):
            m = _GW_FILE_RE.search(p.name)
            if m and int(m.group(1)) > cur:
                p.unlink()

    for rel in (Path("crowd") / "history.json", Path("history") / "status.json"):
        p = repo / rel
        if p.exists():
            data = json.loads(p.read_text())
            if isinstance(data, dict) and isinstance(data.get("gws"), dict):
                data["gws"] = _trim_gws_dict(data["gws"], cur)
                p.write_text(json.dumps(data))

    awards_p = hist_dir / "awards.json"
    if awards_p.exists():
        data = json.loads(awards_p.read_text())
        if isinstance(data, dict) and isinstance(data.get("leagues"), dict):
            for lg in data["leagues"].values():
                if isinstance(lg, dict) and isinstance(lg.get("gws"), dict):
                    lg["gws"] = _trim_gws_dict(lg["gws"], cur)
            awards_p.write_text(json.dumps(data))


def season_end(api):
    """The recorded mid-season responses as FPL serves them just after the last deadline. Also the fast way to run a
    whole build (no forecasts or plans to solve): about 2 s instead of a minute."""
    boot = api["/bootstrap-static/"]
    cur = next(e["id"] for e in boot["events"] if e["is_current"])
    boot["events"] = [e for e in boot["events"] if e["id"] <= cur]
    for e in boot["events"]:
        e["is_next"] = False
        if e["id"] == cur:
            e["finished"] = e["data_checked"] = False   # live: the last gameweek is still being played
    api["/fixtures/"] = [f for f in api["/fixtures/"] if f["event"] and f["event"] <= cur]
    return api, cur


def offline_build(test_case, prepare=None, api_change=None):
    """Build and validate on the season-end replay. prepare(repo) may change the repo copy first, and api_change(api)
    the recorded responses (delete a path to make that request fail). Returns
    (repo, data.json as a dict, validate's exit code, current gameweek). The copy is removed at class cleanup."""
    tmp = tempfile.TemporaryDirectory()
    test_case.addClassCleanup(tmp.cleanup)
    repo = Path(tmp.name) / "repo"
    # build.py reads and writes history/, odds/ and friends next to itself: work on a copy, never the real repo
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "node_modules", "site", "tests"))
    (repo / "site").mkdir()
    with gzip.open(FIXTURE, "rt") as f:
        api, cur = season_end(json.load(f))
    _align_repo_to_gw(repo, cur)
    if prepare:
        prepare(repo)
    if api_change:
        api_change(api)

    def urlopen(req, *a, **k):
        url = req.full_url if hasattr(req, "full_url") else req
        path = url[len(API):] if url.startswith(API) else None
        if path not in api:
            raise OSError(f"offline in test: {url}")
        return io.BytesIO(json.dumps(api[path]).encode())

    out = repo / "site" / "data.json"
    cwd, argv, path = os.getcwd(), sys.argv, list(sys.path)
    try:
        os.chdir(repo)
        sys.argv = ["build.py", TEAM_ID, str(out)]
        sys.path.insert(0, str(repo))
        for name in [m for m in sys.modules if (repo / f"{m}.py").exists()]:
            del sys.modules[name]   # import the copy's modules, not ones another test loaded from the repo
        with mock.patch.object(urllib.request, "urlopen", urlopen), mock.patch("time.sleep"):
            runpy.run_path(str(repo / "build.py"), run_name="__main__")
        rc = runpy.run_path(str(repo / "validate.py"))["main"](str(out))
    finally:
        os.chdir(cwd)
        sys.argv, sys.path[:] = argv, path
        for name in [m for m in sys.modules if (repo / f"{m}.py").exists()]:
            del sys.modules[name]   # later tests import the real repo's modules again
    return repo, json.loads(out.read_text()), rc, cur
