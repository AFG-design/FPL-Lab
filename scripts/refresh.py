"""Build, validate and publish refresh data in a disposable Actions checkout."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as scripts/refresh.py from the repo root
from scripts.push_data import push_head  # noqa: E402  the one push step every data workflow uses (FL-117)

DATA = ("crowd", "understat", "odds", "history", "site/badges")


def git(*args, **kwargs):
    return subprocess.run(["git", *args], check=True, **kwargs)


def revision(ref):
    return git("rev-parse", ref, capture_output=True, text=True).stdout.strip()


def build(odds_key):
    team = os.environ.get("FPL_TEAM_ID", "8122679")
    # awards.py settles mini-league weekly honours once a gameweek is final; it reads crowd.py's league sample
    for script, args in [("crowd.py", [team]), ("awards.py", [team]), ("understat.py", []),
                         ("odds.py", []), ("odds_players.py", [])]:
        # These sources are optional. The build can use the last committed sample.
        # odds.py (upcoming fixture odds, FL-092) and odds_players.py share the free Odds API key and its credits
        env = dict(os.environ, ODDS_API_KEY=odds_key) if script in ("odds.py", "odds_players.py") else None
        if subprocess.call([sys.executable, script, *args], env=env):
            print(f"::warning::{script} failed during refresh", flush=True)
    subprocess.run([sys.executable, "build.py", team, "site/data.json"], check=True)
    subprocess.run([sys.executable, "validate.py", "site/data.json"], check=True)


def changed(base, tip, *filters):
    names = git("diff", "--no-renames", "--name-only", "-z", *filters, base, tip,
                "--", *DATA, capture_output=True).stdout
    return {os.fsdecode(name) for name in names.split(b"\0") if name}


def refresh(build_data):
    git("fetch", "origin", "main")
    git("reset", "--hard", "FETCH_HEAD")
    pending_merge = False
    for attempt in range(1, 4):
        base = revision("HEAD")
        print(f"Refresh attempt {attempt}/3 on {base}", flush=True)
        build_data()
        git("add", "--", *DATA)
        if pending_merge or changed_index():
            git("commit", "-m", "Data update")
        # Push even an unchanged tree: a build from an outdated base must retry too.
        # push_head is True when main holds this commit, including a push whose reply was lost.
        if push_head():
            return
        # The job may fail on a later retry. Keep each rejected sample for the
        # recovery artifact even if the next build stops before making a commit.
        if "RUNNER_TEMP" in os.environ:
            archive = Path(os.environ["RUNNER_TEMP"]) / f"refresh-attempt-{attempt}.tar.gz"
            git("archive", "--format=tar.gz", "-o", str(archive), "HEAD", *DATA)
        latest, candidate = revision("FETCH_HEAD"), revision("HEAD")   # push_head fetched main
        if latest == base or attempt == 3:
            raise RuntimeError(f"Could not publish refresh attempt {attempt} ({candidate})")
        # Replay whole sampled files only where main has not changed that path.
        # If both writers touched a file, use main as the input to the fresh build.
        # Keep the rejected commit as a parent, so even an overlapping, time-specific
        # sample can be recovered exactly without splicing incompatible JSON arrays.
        carry = changed(base, candidate, "--diff-filter=AM") - changed(base, latest)
        git("reset", "--hard", latest)
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", candidate, latest])
        if ancestor.returncode not in (0, 1):
            ancestor.check_returncode()
        pending_merge = candidate != base and ancestor.returncode == 1
        if pending_merge:
            git("merge", "--no-commit", "--no-ff", "-s", "ours", candidate)
            if carry:
                git("restore", "--source", candidate, "--worktree", "--", *sorted(carry))
        # Generated site payloads are ignored by Git. A fresh build must recreate them.
        for filename in ("data.json", "data-extra.json", "shots.json"):
            Path("site", filename).unlink(missing_ok=True)


def changed_index():
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 1


if __name__ == "__main__":
    try:
        odds_key = os.environ.pop("ODDS_API_KEY", "")
        refresh(lambda: build(odds_key))
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        title = "Refresh failed"
        try:
            deadline = json.loads(Path("site/data.json").read_text())["meta"]["deadline"]
            delta = dt.datetime.fromisoformat(deadline.replace("Z", "+00:00")) - dt.datetime.now(dt.timezone.utc)
            if abs(delta) <= dt.timedelta(hours=2):
                title += " within two hours of the deadline"
        except (OSError, KeyError, ValueError, AttributeError):
            title += " (deadline unavailable)"
        sys.exit(f"::error title={title}::{exc}")
