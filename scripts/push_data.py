"""Publish a generated-data commit without overwriting a concurrent main update.

The one push routine for every workflow that commits data (FL-117): priors.yml and odds-archive.yml run this file;
refresh.py calls push_head(), the same push step, but rebuilds on main's new tip instead of rebasing (its data.json
depends on everything on main). Only for disposable Actions checkouts. Overlapping edits fail visibly: retain the
local commit and never force-push or choose one writer's data silently.
"""
import subprocess
import sys


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()


def push_head():
    """Push HEAD to main, never forced. True when main now holds this commit: the push went through, or the remote
    accepted it but the reply was lost (main's tip is our commit, so it must not be replayed). False when main has
    moved on without it; FETCH_HEAD is then main's new tip, and the local commit is untouched."""
    tip = git('rev-parse', 'HEAD')
    if subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/main']).returncode == 0:
        return True
    git('fetch', 'origin', 'main')
    return git('rev-parse', 'FETCH_HEAD') == tip


def push_data():
    for attempt in range(1, 4):
        git('fetch', 'origin', 'main')
        base = git('rev-parse', 'FETCH_HEAD')
        try:
            git('rebase', 'FETCH_HEAD')
        except subprocess.CalledProcessError as exc:
            subprocess.run(['git', 'rebase', '--abort'], capture_output=True)
            raise RuntimeError('Could not rebase generated data; local commit retained. ' + exc.stderr) from exc
        if push_head():
            return
        if git('rev-parse', 'FETCH_HEAD') == base or attempt == 3:
            raise RuntimeError(f'Data push failed after attempt {attempt}; local commit retained.')


if __name__ == '__main__':
    try:
        push_data()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'::error::Could not publish generated data: {exc}', file=sys.stderr)
        sys.exit(1)
