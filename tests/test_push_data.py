"""Real Git remote races: neither a refresh nor generated data may be lost."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts.push_data import push_data


class PushDataTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.addCleanup(os.chdir, Path.cwd())
        os.chdir(self.root)
        self.git('init', '--bare', '-b', 'main', 'origin')
        self.git('clone', 'origin', 'runner')
        os.chdir('runner')
        self.identity()
        Path('data.json').write_text('base')
        self.commit('base')
        self.git('push', 'origin', 'HEAD:main')
        self.git('clone', '../origin', '../rival')
        self.rival = self.root / 'rival'
        self.identity(self.rival)

    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def identity(self, cwd=None):
        self.git('config', 'user.name', 'Test', cwd=cwd)
        self.git('config', 'user.email', 'test@example.invalid', cwd=cwd)

    def commit(self, message, cwd=None):
        self.git('add', '.', cwd=cwd)
        self.git('commit', '-m', message, cwd=cwd)

    def advance(self, path='history.json', value='concurrent'):
        (self.rival / path).write_text(value)
        self.commit('concurrent', self.rival)
        self.git('push', cwd=self.rival)

    def local_change(self):
        Path('data.json').write_text('generated')
        self.commit('generated')

    def test_publish_without_changes(self):
        push_data()
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('rev-parse', 'origin/main'))

    def test_stale_checkout_preserves_both_writers(self):
        self.local_change()
        self.advance()
        push_data()
        self.assertEqual(self.git('show', 'origin/main:data.json'), 'generated')
        self.assertEqual(self.git('show', 'origin/main:history.json'), 'concurrent')

    def test_overlapping_edits_fail_without_losing_local_commit(self):
        self.local_change()
        tip = self.git('rev-parse', 'HEAD')
        self.advance('data.json')
        with self.assertRaisesRegex(RuntimeError, 'Could not rebase'):
            push_data()
        self.assertEqual(self.git('rev-parse', 'HEAD'), tip)
        self.assertEqual(self.git('show', 'origin/main:data.json'), 'concurrent')
        self.assertEqual(Path('data.json').read_text(), 'generated')

    def test_push_race_retries(self):
        self.local_change()
        run = subprocess.run
        pushes = []
        def race(args, **kwargs):
            if args == ['git', 'push', 'origin', 'HEAD:refs/heads/main']:
                pushes.append(1)
                if len(pushes) == 1:
                    self.advance()
            return run(args, **kwargs)
        with patch('scripts.push_data.subprocess.run', side_effect=race):
            push_data()
        self.assertEqual(len(pushes), 2)
        self.assertEqual(self.git('show', 'origin/main:data.json'), 'generated')
        self.assertEqual(self.git('show', 'origin/main:history.json'), 'concurrent')

    def test_repeated_races_stop_after_three_attempts(self):
        self.local_change()
        run = subprocess.run
        pushes = []
        def race(args, **kwargs):
            if args == ['git', 'push', 'origin', 'HEAD:refs/heads/main']:
                pushes.append(1)
                self.advance(value=str(len(pushes)))
            return run(args, **kwargs)
        with patch('scripts.push_data.subprocess.run', side_effect=race):
            with self.assertRaisesRegex(RuntimeError, 'attempt 3'):
                push_data()
        self.assertEqual(len(pushes), 3)
        self.assertEqual(Path('data.json').read_text(), 'generated')

    def test_remote_rejection_without_new_commits_fails(self):
        self.local_change()
        run = subprocess.run
        def reject(args, **kwargs):
            if args == ['git', 'push', 'origin', 'HEAD:refs/heads/main']:
                return subprocess.CompletedProcess(args, 1)
            return run(args, **kwargs)
        with patch('scripts.push_data.subprocess.run', side_effect=reject):
            with self.assertRaisesRegex(RuntimeError, 'attempt 1'):
                push_data()
        self.assertEqual(self.git('show', 'origin/main:data.json'), 'base')

    def test_lost_success_response_is_not_replayed(self):
        self.local_change()
        run = subprocess.run
        pushes = []
        def lost_reply(args, **kwargs):
            result = run(args, **kwargs)
            if args == ['git', 'push', 'origin', 'HEAD:refs/heads/main']:
                pushes.append(1)
                return subprocess.CompletedProcess(args, 1)
            return result
        with patch('scripts.push_data.subprocess.run', side_effect=lost_reply):
            push_data()
        self.assertEqual(len(pushes), 1)
        self.assertEqual(self.git('show', 'origin/main:data.json'), 'generated')
