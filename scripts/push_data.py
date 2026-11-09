"""Publish a generated-data commit without overwriting a concurrent main update.

Only for disposable Actions checkouts. Overlapping edits fail visibly: retain the
local commit and never force-push or choose one writer's data silently.
"""
import subprocess
import sys


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()


def push_data():
    for attempt in range(1, 4):
        git('fetch', 'origin', 'main')
        base = git('rev-parse', 'FETCH_HEAD')
        try:
            git('rebase', 'FETCH_HEAD')
        except subprocess.CalledProcessError as exc:
            subprocess.run(['git', 'rebase', '--abort'], capture_output=True)
            raise RuntimeError('Could not rebase generated data; local commit retained. ' + exc.stderr) from exc
        tip = git('rev-parse', 'HEAD')
        pushed = subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/main'])
        if pushed.returncode == 0:
            return
        git('fetch', 'origin', 'main')
        # A lost response can report failure after the remote accepted the commit.
        if git('rev-parse', 'FETCH_HEAD') == tip:
            return
        if git('rev-parse', 'FETCH_HEAD') == base or attempt == 3:
            raise RuntimeError(f'Data push failed after attempt {attempt}; local commit retained.')


if __name__ == '__main__':
    try:
        push_data()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'::error::Could not publish generated data: {exc}', file=sys.stderr)
        sys.exit(1)
