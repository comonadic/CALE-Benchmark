#!/usr/bin/env python3
"""Combine selected independent runs without exposing host paths or tracebacks."""
import argparse
import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from collect_results import FIELDS, collect

ROOT = Path(__file__).resolve().parents[1]


def reward_value(rewards):
    if not isinstance(rewards, dict):
        return None
    value = rewards.get('reward') if 'reward' in rewards else next(iter(rewards.values())) if len(rewards) == 1 else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if not 0 <= value <= 1:
        raise ValueError('Reward is outside the published 0..1 range')
    return value


def usage_totals(records):
    result = {field: sum((r.get('usage') or {}).get(field, 0) or 0 for r in records) for field in FIELDS}
    result.update(
        responses=len(records),
        responses_without_usage=sum(not isinstance(r.get('usage'), dict) for r in records),
        incomplete_responses=sum(r.get('stream_complete', r.get('complete')) is not True for r in records),
        thinking_tokens_known=sum(((r.get('usage') or {}).get('output_tokens_details') or {}).get('thinking_tokens', 0) or 0 for r in records),
        responses_with_thinking_breakdown=sum(isinstance((r.get('usage') or {}).get('output_tokens_details'), dict) for r in records),
    )
    prompt = sum(result[field] for field in FIELDS[:3])
    result['cache_read_share_of_reported_prompt'] = round(result['cache_read_input_tokens'] / prompt, 4) if prompt else None
    return result


def combine(summaries, expected, now=None):
    task_ids = [t['task_id'] for s in summaries for t in s['trials']]
    scheduled = [t for s in summaries for t in s['policy']['task_ids']]
    if len(task_ids) != len(set(task_ids)) or len(scheduled) != len(set(scheduled)):
        raise ValueError('Multiple attempts for a task; explicitly select the intended runs')
    expected_ids = {t['id'] for t in expected}
    if set(scheduled) != expected_ids or not set(task_ids) <= expected_ids:
        raise ValueError('Selected runs do not cover exactly the published tasks')
    trials = copy.deepcopy([t for s in summaries for t in s['trials']])
    # Private local receipts keep the complete exception. Published reports expose its type.
    for trial in trials:
        if trial.get('exception'):
            trial['exception'] = {'exception_type': trial['exception'].get('exception_type')}
    transport = [r for s in summaries for r in s.get('agent_transport', [])]
    agents = {r['response_id']: r for r in transport if r.get('response_id')}
    judges = {r['response_id']: r for s in summaries for r in s['judge_responses']}
    usage = {'agent_provider': usage_totals(list(agents.values())), 'judge': usage_totals(list(judges.values()))}
    usage['agent_provider']['requests_without_response_id'] = sum(not r.get('response_id') for r in transport)
    usage['agent_provider']['http_requests'] = len(transport)
    scored = [reward_value(t['reward']) for t in trials if reward_value(t['reward']) is not None]
    all_finished = set(task_ids) == expected_ids and all(t['completed'] for t in trials)
    status = ('complete' if len(scored) == len(expected) else 'completed_with_errors') if all_finished else 'partial'
    current = now or datetime.now(timezone.utc)
    starts = [datetime.fromisoformat(s['policy']['started_at'].replace('Z', '+00:00')) for s in summaries]
    finishes = [datetime.fromisoformat(t['finished_at'].replace('Z', '+00:00')) for t in trials if t.get('finished_at')]
    end = max(finishes) if all_finished else current
    return {
        'status': status, 'model': 'claude-opus-5-5', 'agent': 'claude-code',
        'as_of': current.isoformat(), 'started_at': min(starts).isoformat(),
        'finished_at': end.isoformat() if all_finished else None,
        'elapsed_wall_seconds': round((end - min(starts)).total_seconds(), 3),
        'expected_tasks': len(expected), 'completed_trials': sum(t['completed'] for t in trials),
        'valid_scored_trials': len(scored),
        'mean_reward_valid_trials': round(sum(scored) / len(scored), 6) if scored else None,
        'usage': usage, 'trials': sorted(trials, key=lambda t: t['task_id']),
        'runtime_agents': [s.get('runtime_agents', []) for s in summaries],
        'provider_invoice_cost_usd': None,
        'usage_note': 'Observed counters include incomplete responses. Missing final usage and missing thinking breakdowns are unknown, not zero. CLI dollar costs are estimates, not the Heju invoice.',
    }


def write_report(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Claude Code + Heju Opus 5.5 实际试解', '',
             f'状态：{result["status"]}；完成 {result["completed_trials"]}/{result["expected_tasks"]} 条 trial；有效评分 {result["valid_scored_trials"]} 条。', '',
             f'整体经过 {result["elapsed_wall_seconds"]} 秒，包含并行运行与评分。未完成时的平均分只描述已评分题目。', '',
             '| 题目 | reward | 启动秒 | 解题秒 | 评分秒 | 总秒 | 状态 |',
             '|---|---:|---:|---:|---:|---:|---|']
    for trial in result['trials']:
        secs = trial['seconds']
        error = (trial.get('exception') or {}).get('exception_type')
        row = [trial['task_id'], str(reward_value(trial['reward'])), str(secs['environment_setup']),
               str(secs['agent_execution']), str(secs['verifier']), str(secs['total']),
               error or ('完成' if trial['completed'] else '运行中')]
        lines.append('| ' + ' | '.join(row) + ' |')
    lines += ['', '| 调用侧 | 普通输入 | 缓存写入 | 缓存读取 | 输出 | 已知推理输出 | 不完整回包 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for role, usage in result['usage'].items():
        values = [usage[k] for k in FIELDS] + [usage['thinking_tokens_known'], usage['incomplete_responses']]
        lines.append('| ' + ' | '.join([role] + list(map(str, values))) + ' |')
    lines += ['', '解题输入缓存采用真实 provider usage。评分对每题唯一候选调用一次，未开启缓存写入。输入总量包括普通输入、缓存写入和缓存读取。部分回包缺少最终 usage；未提供的推理分项不按零处理，完整费用需与 Heju 账单核对。CLI 美元成本属于估计。', '',
              '此前 DNS/启动失败记录单独保留，没有纳入本次独立试解成绩。原始轨迹、产物和评分证据保存在本地运行目录；公开报告只保留异常类型。']
    (output / 'report.md').write_text('\n'.join(lines) + '\n')


def report(runs, output):
    summaries = [collect(p.resolve()) for p in runs]
    expected = json.loads((ROOT / 'manifest.json').read_text())['tasks']
    result = combine(summaries, expected)
    result['run_sources'] = [p.name for p in runs]
    write_report(result, output)
    print(json.dumps({k: result[k] for k in ['status', 'completed_trials', 'valid_scored_trials', 'mean_reward_valid_trials']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report(args.runs, args.output)
