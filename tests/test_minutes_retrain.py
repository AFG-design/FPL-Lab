"""FL-162: training features and calibration cannot see evaluation outcomes."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import xmins
from tools import retrain_minutes as experiment


class RetrainMinutes(unittest.TestCase):
    def test_folds_and_calibration_are_strictly_earlier(self):
        for test, training in experiment.FOLDS.items():
            if test != 'current':
                self.assertLess(int(training[-1][:4]), int(test[:4]))
            self.assertEqual(training, experiment.SEASONS[:len(training)])
            self.assertLess(int(training[-2][:4]), int(training[-1][:4]))

    def test_calibration_handles_extremes_and_requires_labels(self):
        p = np.linspace(.01, .99, 1000)
        y = (np.arange(1000) % 10 < (p * 10).astype(int)).astype(float)
        a, b = experiment.fit_calibration(p, y)
        self.assertTrue(np.isfinite([a, b]).all())
        self.assertGreater(b, 0)
        class Booster:
            def predict(self, _): return np.array([0., .5, 1.])
        q = experiment.CalibratedStart(Booster(), [a, b]).predict(None)
        self.assertTrue(np.all((q > 0) & (q < 1)))
        self.assertTrue(np.all(np.diff(q) > 0))
        with self.assertRaises(ValueError): experiment.fit_calibration([], [])
        with self.assertRaises(ValueError): experiment.fit_calibration([.5]*4, [1]*4)

    def test_override_restored_on_error(self):
        old = xmins._boosters
        with self.assertRaisesRegex(RuntimeError, 'stop'):
            with experiment.installed(('test', {})):
                self.assertEqual(xmins._boosters, ('test', {}))
                raise RuntimeError('stop')
        self.assertIs(xmins._boosters, old)

    def test_reliability_boundaries_and_empty_bins(self):
        result = experiment.reliability([(0., 0), (.9, 1), (1., 0)])
        self.assertEqual([r['bin'] for r in result], ['0-10%', '90-100%'])
        self.assertEqual(result[-1]['n'], 2)
        self.assertEqual(result[-1]['started'], .5)
        self.assertEqual(experiment.reliability([]), [])

    def test_training_features_ignore_target_and_future_minutes(self):
        names = ['round', 'history_gws', 'last_minutes', 'last_starts', 'minutes_avg_3']
        ctx = {'elements': {1: {'team': 1, 'element_type': 3}},
               'pstats': {1: {1: {'minutes': 90, 'starts': 1}, 2: {'minutes': 60, 'starts': 1},
                              3: {'minutes': 0, 'starts': 0}, 4: {'minutes': 90, 'starts': 1}}},
               'team_fix': {1: [(k, 2, True, {'kickoff_time': f'2024-08-{k:02}T12:00:00Z'}) for k in range(1,5)]}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'raw').mkdir(); (root/'raw/bootstrap.json').write_text('{}')
            folder = root/'archive/2023-24'; folder.mkdir(parents=True)
            source = folder/'merged_gw.csv'
            source.write_text('element,GW,minutes,starts\n1,3,0,0\n')
            with patch.object(experiment, 'ROOT', root), patch.object(experiment.archive, 'load_season',
                    return_value=({}, [], {}, {}, lambda pid, k: 1)), patch.object(experiment, 'prepare', return_value=ctx):
                before = experiment.season_rows('2023-24', names)
                ctx['pstats'][1][3] = {'minutes': 180, 'starts': 2}
                ctx['pstats'][1][4] = {'minutes': 0, 'starts': 0}
                source.write_text('element,GW,minutes,starts\n1,3,90,1\n1,3,90,1\n')
                after = experiment.season_rows('2023-24', names)
            np.testing.assert_equal(before[0][0], after[0][0])
            np.testing.assert_equal(after[0][0], after[0][1])
            self.assertEqual(before[1][0][0], 0)
            self.assertEqual(after[1][0][0], 1)
            self.assertEqual(after[2][0][2], 2)

    def test_cannot_write_inside_repository(self):
        for name in ('xmins', 'xmins_sell', 'history', '.'):
            with patch.object(experiment.sys, 'argv', ['retrain_minutes.py', 'train', '--out', str(experiment.ROOT / name)]):
                with self.assertRaisesRegex(ValueError, 'outside the repository'):
                    experiment.main()

    def test_paired_ci_identity(self):
        rows = {1: [(1, 'MID', 1., 2.), (2, 'MID', 2., 3.)],
                2: [(1, 'MID', 3., 1.), (2, 'MID', 4., 5.)]}
        self.assertEqual(experiment.correlation_ci(rows, copy.deepcopy(rows), n=100), [0., 0., 0.])
        self.assertEqual(experiment.horizon_ci({1: 4., 2: 5.}, {1: 4., 2: 5.}, n=100), [0., 0., 0.])


if __name__ == '__main__': unittest.main()
