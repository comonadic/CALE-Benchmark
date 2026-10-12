import importlib.util
import io
import json
import tempfile
import unittest
import copy
from pathlib import Path

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).with_name('host_rubric_bridge.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class Stream(io.BytesIO):
    headers = {'Content-Type': 'text/event-stream; charset=utf-8'}


def stream(events):
    return Stream(''.join('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n'
                          for event in events).encode())


START = {'type': 'message_start', 'message': {'id': 'msg_test', 'model': 'test-model',
         'content': [], 'usage': {'input_tokens': 30, 'output_tokens': 1}}}


class ResponseTests(unittest.TestCase):
    def test_message_stop_finishes_without_waiting_for_connection_close(self):
        class StillOpen:
            headers = Stream.headers

            def __iter__(self):
                yield from stream([START, {'type': 'message_stop'}])
                raise AssertionError('Should not read past the terminal event')

        self.assertTrue(bridge.read_message_response(StillOpen())['stream_complete'])

    def test_complete_stream_collects_text_and_cumulative_usage(self):
        events = [START, {'type': 'content_block_start', 'index': 0,
                  'content_block': {'type': 'thinking', 'thinking': ''}},
                  {'type': 'content_block_delta', 'index': 0,
                   'delta': {'type': 'thinking_delta', 'thinking': 'review'}},
                  {'type': 'content_block_start', 'index': 1,
                   'content_block': {'type': 'text', 'text': ''}},
                  {'type': 'ping'}, {'type': 'future_event'},
                  {'type': 'content_block_delta', 'index': 1,
                   'delta': {'type': 'text_delta', 'text': '{"criteria":[]}'}},
                  {'type': 'message_delta', 'delta': {}, 'usage': {'output_tokens': 14}},
                  {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'},
                   'usage': {'output_tokens': 16}}, {'type': 'message_stop'}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'response.json'
            raw = bridge.read_message_response(stream(events), path)
            self.assertEqual(raw['content'][1]['text'], '{"criteria":[]}')
            self.assertEqual(raw['content'][0]['thinking'], 'review')
            self.assertEqual(raw['usage'], {'input_tokens': 30, 'output_tokens': 16})
            self.assertTrue(raw['stream_complete'])
            self.assertEqual(json.loads(path.read_text()), raw)
            self.assertEqual(len(path.with_suffix('.events.jsonl').read_text().splitlines()), len(events))

    def test_truncated_stream_is_error_and_keeps_partial_evidence(self):
        events = [START, {'type': 'content_block_start', 'index': 0,
                  'content_block': {'type': 'text', 'text': 'partial'}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'response.json'
            with self.assertRaisesRegex(RuntimeError, 'without message_stop'):
                bridge.read_message_response(stream(events), path)
            raw = json.loads(path.read_text())
            self.assertFalse(raw['stream_complete'])
            self.assertEqual(raw['content'][0]['text'], 'partial')
            self.assertEqual(raw['usage']['input_tokens'], 30)

    def test_stream_error_is_not_a_completed_message(self):
        events = [START, {'type': 'error', 'error': {'type': 'overloaded_error'}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'response.json'
            with self.assertRaisesRegex(RuntimeError, 'overloaded_error'):
                bridge.read_message_response(stream(events), path)
            self.assertFalse(json.loads(path.read_text())['stream_complete'])


class PromptCacheTests(unittest.TestCase):
    def request(self):
        return {'schema_version': 1, 'task_id': 'sample', 'instruction': 'Review the supplied work.',
                'rubric': {'criteria': [{'id': 'R1', 'points': 100}]},
                'inputs': {'source.txt': 'source evidence'}, 'outputs': {'report.txt': 'candidate'},
                'objective': {'correct': True}, 'request_sha256': 'first',
                'source_images': [{'name': 'figure', 'data': 'aW1hZ2U='}]}

    def test_changed_candidate_keeps_cached_prefix_and_preserves_all_request_fields(self):
        req = self.request()
        first = bridge.build_grade_body(req, 'test-model', '1h')['messages'][0]['content']
        changed = copy.deepcopy(req)
        changed.update(outputs={'report.txt': 'another candidate'}, objective={'correct': False},
                       request_sha256='second')
        second = bridge.build_grade_body(changed, 'test-model', '1h')['messages'][0]['content']
        self.assertEqual(first[:-1], second[:-1])
        self.assertNotEqual(first[-1], second[-1])
        self.assertEqual(first[-2]['cache_control'], {'type': 'ephemeral', 'ttl': '1h'})
        stable = json.loads(first[0]['text'].partition('Task context: ')[2])
        candidate = json.loads(first[-1]['text'].partition('Review this candidate: ')[2])
        self.assertEqual(stable | candidate, {k: v for k, v in req.items() if k != 'source_images'})
        self.assertNotIn('outputs', stable)
        self.assertNotIn('objective', stable)

    def test_changed_material_invalidates_prefix(self):
        req = self.request()
        first = bridge.build_grade_body(req, 'test-model', '5m')['messages'][0]['content']
        req['inputs']['source.txt'] = 'revised source evidence'
        second = bridge.build_grade_body(req, 'test-model', '5m')['messages'][0]['content']
        self.assertNotEqual(first[:-1], second[:-1])

    def test_one_off_mode_has_no_cache_write_and_keeps_full_candidate_payload(self):
        req = self.request()
        content = bridge.build_grade_body(req, 'test-model')['messages'][0]['content']
        self.assertFalse(any('cache_control' in block for block in content))
        payload = json.loads(content[0]['text'].partition('Review this candidate: ')[2])
        self.assertEqual(payload, {k: v for k, v in req.items() if k != 'source_images'})


class AssessmentRecoveryTests(unittest.TestCase):
    def request(self):
        return {'rubric': {'criteria': [{'id': 'R1', 'points': 10}]}, 'request_sha256': 'same-request'}

    def response(self, score):
        return {'id': 'actual-response', 'model': 'actual-model', 'stop_reason': 'end_turn',
                'stream_complete': True, 'usage': {'input_tokens': 10, 'output_tokens': 20},
                'content': [{'type': 'text', 'text': json.dumps({'criteria': [
                    {'id': 'R1', 'score': score, 'reason': 'source-supported', 'evidence': ['file location']}]})}]}

    def test_numeric_string_preserves_real_score_reason_identity_and_raw_response(self):
        raw = self.response('10')
        before = copy.deepcopy(raw)
        result = bridge.parse_model_assessment(self.request(), raw, 'requested-model')
        self.assertEqual(result['criteria'][0]['score'], 10)
        self.assertEqual(result['criteria'][0]['reason'], 'source-supported')
        self.assertEqual(result['judge_identity']['response_id'], raw['id'])
        self.assertEqual(raw, before)
        for bad in ['10/10', 'NaN', 'Infinity', 'true', True, '11', None]:
            with self.subTest(score=bad), self.assertRaises(ValueError):
                bridge.parse_model_assessment(self.request(), self.response(bad), 'requested-model')

    def test_recovery_requires_exact_request_and_uses_no_http(self):
        req = self.request()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'request.json').write_text(json.dumps(req))
            (directory / 'model-response.json').write_text(json.dumps(self.response('10')))
            (directory / 'model-response.request-metadata.json').write_text(json.dumps(
                {'model': 'requested-model', 'request_sha256': req['request_sha256']}))
            assessment, raw = bridge.recover_model_assessment(req, directory, 'requested-model')
            self.assertFalse(assessment['judge_identity']['recovery']['new_model_call'])
            self.assertEqual(assessment['judge_identity']['response_id'], raw['id'])
            changed = {**req, 'outputs': {'file': 'changed'}}
            with self.assertRaisesRegex(ValueError, 'differs'):
                bridge.recover_model_assessment(changed, directory, 'requested-model')


if __name__ == '__main__':
    unittest.main()
