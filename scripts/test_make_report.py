"""Aggregation must preserve failed attempts and unknown provider accounting."""
import unittest
from datetime import datetime, timezone

from make_report import combine, reward_value


class ReportTests(unittest.TestCase):
    def sample(self):
        return {
            'policy': {'task_ids': ['one'], 'started_at': '2026-10-12T09:00:00+00:00'},
            'trials': [{'task_id': 'one', 'completed': True, 'finished_at': '2026-10-12T09:40:00Z',
                        'reward': {'reward': 0.0},
                        'exception': {'exception_type': 'AgentTimeoutError', 'exception_traceback': '/private/host/path'}}],
            'agent_transport': [{'response_id': 'msg_1', 'stream_complete': False,
                                 'usage': {'input_tokens': 2, 'cache_creation_input_tokens': 10, 'cache_read_input_tokens': 90, 'output_tokens': 1}},
                                {'http_status': 502}],
            'judge_responses': [],
        }

    def test_timeout_is_observed_zero_not_missing_grade(self):
        raw = self.sample()
        result = combine([raw], [{'id': 'one'}], datetime(2026, 10, 12, 10, tzinfo=timezone.utc))
        self.assertEqual((result['status'], result['valid_scored_trials'], result['mean_reward_valid_trials']), ('complete', 1, 0.0))
        self.assertEqual(result['elapsed_wall_seconds'], 2400)
        self.assertEqual(result['trials'][0]['exception'], {'exception_type': 'AgentTimeoutError'})
        self.assertIn('exception_traceback', raw['trials'][0]['exception'])
        raw['trials'][0]['reward'] = None
        missing = combine([raw], [{'id': 'one'}])
        self.assertEqual(missing['status'], 'completed_with_errors')
        self.assertIsNone(missing['mean_reward_valid_trials'])

    def test_partial_usage_is_retained_and_unknowns_visible(self):
        result = combine([self.sample()], [{'id': 'one'}])['usage']['agent_provider']
        self.assertEqual(result['cache_read_input_tokens'], 90)
        self.assertEqual(result['incomplete_responses'], 1)
        self.assertEqual(result['requests_without_response_id'], 1)
        self.assertEqual(result['responses_with_thinking_breakdown'], 0)
        self.assertAlmostEqual(result['cache_read_share_of_reported_prompt'], 90 / 102, places=4)

    def test_repeated_attempts_and_wrong_task_coverage_rejected(self):
        with self.assertRaises(ValueError):
            combine([self.sample(), self.sample()], [{'id': 'one'}])
        with self.assertRaises(ValueError):
            combine([self.sample()], [{'id': 'one'}, {'id': 'two'}])

    def test_nonfinite_or_boolean_scores_are_not_numeric_rewards(self):
        for value in [float('nan'), float('inf'), True, '0.9']:
            self.assertIsNone(reward_value({'reward': value}))
        with self.assertRaises(ValueError):
            reward_value({'reward': 1.1})


if __name__ == '__main__':
    unittest.main()
