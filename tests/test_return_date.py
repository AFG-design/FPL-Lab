import datetime as dt
import unittest
from fplmodel import return_date, availability_info


class ReturnDateTests(unittest.TestCase):
    def player(self, news, added='2026-01-10T10:00:00Z'):
        return {'id':1, 'status':'i', 'chance_of_playing_next_round':0,
                'news':news, 'news_added':added}

    def test_invalid_dates_warn_and_use_assumed_unknown_return(self):
        for news, added in [('Expected back 29 Feb','2026-01-10'),
                            ('Suspended until 31 Apr','2026-04-10'),
                            ('Expected back 00 Jan','2026-01-01'),
                            ('Expected back 29 Feb','2024-12-10'),
                            ('Expected back 12 Mar','not-a-date')]:
            with self.subTest(news=news, added=added):
                p=self.player(news, added)
                with self.assertWarnsRegex(RuntimeWarning, 'Invalid return date'):
                    ret=return_date(p)
                self.assertEqual(ret, 'unknown')
                self.assertEqual(availability_info(p, 0, ret=ret), (0.0, False))
                self.assertEqual(availability_info(p, 1, ret=ret), (1/6, True))

    def test_valid_dates_and_rollover(self):
        for news, added, expected in [('Expected back 29 Feb','2024-01-10',dt.date(2024,2,29)),
                                      ('Expected back 29 Feb','2023-12-10',dt.date(2024,2,29)),
                                      ('Suspended until 3 Jan','2026-12-10',dt.date(2027,1,3)),
                                      ('Expected back 21 Nov','2026-11-01',dt.date(2026,11,21))]:
            with self.subTest(news=news,added=added):
                self.assertEqual(return_date(self.player(news,added)),expected)

    def test_absent_or_unknown_dates_unchanged(self):
        self.assertIsNone(return_date(self.player('Knock - being assessed')))
        self.assertIsNone(return_date(self.player('Expected back 21 Nov',None)))
        self.assertEqual(return_date(self.player('Unknown return date')),'unknown')

    def test_projection_survives_invalid_return_date_and_labels_assumption(self):
        from fplmodel import prepare, project
        p=dict(self.player('Expected back 29 Feb'), team=1, element_type=3, now_cost=50)
        boot={'teams':[{'id':1},{'id':2}], 'events':[], 'elements':[p], 'game_config':{'scoring':{}}}
        boot['game_config']['scoring'] = dict(short_play=1,long_play=2,assists=3,
            goals_scored={'MID':5},clean_sheets={'MID':1},goals_conceded={'MID':0},
            defensive_contribution={'MID':2})
        fixtures=[dict(id=g,event=g,team_h=1,team_a=2,team_h_score=None,team_a_score=None,
                       finished=False,team_h_difficulty=2,team_a_difficulty=2,
                       kickoff_time=f'2026-02-{g:02d}T15:00:00Z') for g in (2,3)]
        fixtures.append(dict(id=1,event=1,team_h=1,team_a=2,team_h_score=1,team_a_score=0,
                             finished=True,team_h_difficulty=2,team_a_difficulty=2))
        stats=dict(minutes=90,starts=1,total_points=5,expected_goals='0.2',expected_assists='0.1',
                   bonus=0,saves=0,yellow_cards=0,defensive_contribution=0)
        ctx=prepare(boot,fixtures,{1:{'elements':[dict(id=1,stats=stats,explain=[])]}})
        with self.assertWarnsRegex(RuntimeWarning, 'Invalid return date'):
            result=project(ctx,2,2,{'xmins':False,'sim':0,'today':dt.date(2026,1,10)})['players'][1]
        self.assertEqual(result['xp'][2],0)
        self.assertGreater(result['xp'][3],0)
        self.assertIn(3,result['assumed'])
