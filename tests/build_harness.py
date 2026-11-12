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
import runpy
import shutil
import sys
import tempfile
from unittest import mock
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "season_end_api.json.gz"
API = "https://fantasy.premierleague.com/api"
TEAM_ID = "8122679"


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


def offline_build(test_case, prepare=None):
    """Build and validate on the season-end replay. prepare(repo) may change the repo copy first. Returns
    (repo, data.json as a dict, validate's exit code, current gameweek). The copy is removed at class cleanup."""
    tmp = tempfile.TemporaryDirectory()
    test_case.addClassCleanup(tmp.cleanup)
    repo = Path(tmp.name) / "repo"
    # build.py reads and writes history/, odds/ and friends next to itself: work on a copy, never the real repo
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "node_modules", "site", "tests"))
    (repo / "site").mkdir()
    if prepare:
        prepare(repo)
    with gzip.open(FIXTURE, "rt") as f:
        api, cur = season_end(json.load(f))

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
