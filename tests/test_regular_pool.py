"""FL-163: eligibility is known before the deadline, including non-appearances."""
import copy
import unittest
from backtest import in_regular_pool, regular_rows
import bench


def context():
    return {
        'elements': {p: {'element_type': 3} for p in range(1, 6)},
        'fixtures': [{'kickoff_time': '2026-08-15T12:00:00Z'}],
        'pstats': {
            1: {9: {'minutes': 20}},  # existing pool
            2: {g: {'minutes': 90, 'starts': 1} for g in range(1, 6)},  # returner at GW10
            3: {9: {'minutes': 0, 'starts': 0}},  # registered arrival with prior
            4: {10: {'minutes': 90, 'starts': 1}},  # future appearance cannot admit him
            5: {9: {'minutes': 0, 'starts': 0}},
        },
        'priors': {'3': {'season': '2025/26', 'last_mins': 1500},
                   '4': {'season': '2025-26', 'last_mins': 2000},
                   '5': {'season': '2024/25', 'last_mins': 3000}},
        'pts_gw': {p: {10: 0, 11: 2} for p in range(1, 6)},
    }


class RegularPool(unittest.TestCase):
    def test_recent_returner_and_registered_arrival_even_when_they_dont_play(self):
        c = context()
        self.assertEqual([p for p in c['elements'] if in_regular_pool(c, p, 10)], [1, 2, 3])
        rows = regular_rows(c, 10, {1: 2., 2: 3., 3: 4.})
        self.assertEqual([r[3] for r in rows], [0, 0, 0])
        self.assertEqual([r[0] for r in bench.pool_rows(c, 10, {1: 2., 2: 3., 3: 4.})], [1])

    def test_future_results_and_starts_cannot_change_membership(self):
        c = context(); before = [in_regular_pool(c, p, 10) for p in c['elements']]
        for p in c['elements']:
            c['pstats'][p][10] = {'minutes': 180, 'starts': 2}
            c['pstats'][p][11] = {'minutes': 90, 'starts': 1}
            c['pts_gw'][p][10] = 20
        self.assertEqual(before, [in_regular_pool(c, p, 10) for p in c['elements']])

    def test_ten_gw_boundary_and_prior_threshold(self):
        c = context()
        self.assertTrue(in_regular_pool(c, 2, 11))
        self.assertFalse(in_regular_pool(c, 2, 12))
        c['priors']['3']['last_mins'] = 1499
        self.assertFalse(in_regular_pool(c, 3, 10))
        c['priors']['3']['mins'] = 4000  # weighted prior is not last-season minutes
        self.assertFalse(in_regular_pool(c, 3, 10))

    def test_deadline_registration_not_first_future_row(self):
        c = context()
        self.assertFalse(in_regular_pool(c, 4, 10))
        c['status_rows'] = {10: {4: ('a', 100)}}
        self.assertTrue(in_regular_pool(c, 4, 10))

    def test_missing_inputs_are_not_invented(self):
        c = context(); c.pop('priors')
        self.assertFalse(in_regular_pool(c, 3, 10))
        c = context(); c['fixtures'] = []
        self.assertFalse(in_regular_pool(c, 3, 10))
        with self.assertRaisesRegex(ValueError, 'missing projection'):
            regular_rows(context(), 10, {1: 2.})
        c = context(); del c['pts_gw'][3][10]
        self.assertEqual(len(regular_rows(c, 10, {1: 2., 2: 3.})), 2)

    def test_horizon_freezes_membership_at_origin_and_handles_blanks(self):
        c = context(); original = copy.deepcopy(c)
        rows = regular_rows(c, 10, {1: 2., 2: 3., 3: 4.}, horizon=5)
        self.assertEqual([r[0] for r in rows], [1, 2, 3])
        self.assertEqual([r[3] for r in rows], [2, 2, 2])
        self.assertEqual(c, original)


if __name__ == '__main__':
    unittest.main()
