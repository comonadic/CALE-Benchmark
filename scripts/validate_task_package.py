#!/usr/bin/env python3
"""Static Harbor package preflight.

Checks the machine-checkable parts of the authoring contract: package layout,
assertion contract (scale / independence metadata / criterion coverage),
reward plumbing, derived reference solution, and lineage schema. Runtime
behaviour and professional quality remain untested -- see verification.md.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tomllib

ASSERTION_MIN = 20
ASSERTION_MAX = 50

REQUIRED_FILES = [
    'instruction.md',
    'task.toml',
    'environment/Dockerfile',
    'solution/solve.sh',
    'solution/build_reference.py',
    'tests/test.sh',
    'tests/assertions.json',
    'tests/grade.py',
]

LINEAGE_REQUIRED = [
    'task_id', 'industry', 'design', 'sources', 'derivation',
]

FORBIDDEN_IN_AGENT_VIEW = ['assertions.json', 'grade.py', 'solve.sh', 'build_reference.py']


def _finite(value):
    return (not isinstance(value, bool)) and isinstance(value, (int, float)) and math.isfinite(value)


def _check_files(p, errors, hashes):
    for rel in REQUIRED_FILES:
        q = p / rel
        if not q.is_file() or q.stat().st_size == 0:
            errors.append(f'Missing or empty {rel}')
        else:
            hashes[rel] = hashlib.sha256(q.read_bytes()).hexdigest()


def _check_assertions(p, errors, records):
    """The assertion contract: scale, uniqueness, independence metadata, coverage."""
    q = p / 'tests/assertions.json'
    if not q.is_file():
        return
    try:
        doc = json.loads(q.read_text())
    except ValueError as exc:
        errors.append(f'assertions.json: invalid JSON: {exc}')
        return
    if not isinstance(doc, dict):
        errors.append('assertions.json: top level must be an object')
        return

    scale = doc.get('scale')
    if not _finite(scale) or scale <= 0:
        errors.append('assertions.json: scale must be a finite number > 0')

    assertions = doc.get('assertions')
    if not isinstance(assertions, list) or not assertions:
        errors.append('assertions.json: assertions must be a non-empty list')
        return

    ids, units, criteria_seen = [], {}, set()
    for i, a in enumerate(assertions):
        if not isinstance(a, dict):
            errors.append(f'assertions.json: assertion[{i}] must be an object')
            continue
        aid = a.get('id')
        if not isinstance(aid, str) or not aid:
            errors.append(f'assertions.json: assertion[{i}] missing non-empty id')
        else:
            ids.append(aid)
        kind = a.get('kind')
        if kind not in ('outcome', 'evidence'):
            errors.append(f'assertions.json: {aid or i} kind must be outcome or evidence')
        unit = a.get('unit')
        if not isinstance(unit, str) or not unit.strip():
            errors.append(f'assertions.json: {aid or i} missing unit (needed to check independence)')
        else:
            units.setdefault(unit.strip(), []).append(aid or str(i))
        crit = a.get('criterion')
        if not isinstance(crit, str) or not crit:
            errors.append(f'assertions.json: {aid or i} missing criterion')
        else:
            criteria_seen.add(crit)

    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        errors.append(f'assertions.json: duplicate assertion ids: {dupes}')

    for unit, members in units.items():
        if len(members) > 1:
            errors.append(
                'assertions.json: assertions share one work unit and must be merged: '
                f'{unit!r} -> {members}')

    n = len(assertions)
    if scale is not None and _finite(scale) and int(scale) != n:
        errors.append(f'assertions.json: scale ({scale}) must equal assertion count ({n})')
    # Reference range only: knowledge-work tasks are judged on whether the whole
    # task is verifiable, so an out-of-range count is reported, not rejected.
    if not (ASSERTION_MIN <= n <= ASSERTION_MAX):
        records.setdefault('warnings', []).append(
            f'assertions.json: {n} assertions outside the {ASSERTION_MIN}-{ASSERTION_MAX} '
            'reference range; check the score still separates good and poor work')

    for ce in doc.get('critical_errors') or []:
        if not isinstance(ce, dict):
            errors.append('assertions.json: critical_errors entries must be objects')
            continue
        ref = ce.get('assertion')
        if ref not in ids:
            errors.append(f'assertions.json: critical_error references unknown assertion {ref!r}')
        cap = ce.get('cap')
        if not _finite(cap) or not (0 <= cap <= 1):
            errors.append(f'assertions.json: critical_error cap must be within [0, 1]')

    records['assertion_count'] = n
    records['criteria_covered'] = sorted(criteria_seen)


def _check_rubric_coverage(p, errors, records):
    """Every criterion in the rubric must carry at least one assertion."""
    criteria_seen = set(records.get('criteria_covered') or [])
    if not criteria_seen:
        return
    for q in sorted((p / 'tests').glob('*rubric*.json')):
        try:
            rubric = json.loads(q.read_text())
        except ValueError as exc:
            errors.append(f'{q.name}: invalid JSON: {exc}')
            continue
        total = rubric.get('total_points')
        if total is not None and (not _finite(total) or total <= 0):
            errors.append(f'{q.name}: invalid total_points')
        ids = []
        for group in ['criteria', 'objective_criteria']:
            rows = rubric.get(group, [])
            if not isinstance(rows, list):
                errors.append(f'{q.name}: {group} must be a list')
                continue
            for item in rows:
                if not isinstance(item, dict):
                    errors.append(f'{q.name}: {group} entries must be objects')
                    continue
                ident = item.get('id', item.get('criterion_id', item.get('label')))
                if ident is not None:
                    ids.append(ident)
                pts = item.get('points')
                if pts is not None and (not _finite(pts) or pts < 0):
                    errors.append(f'{q.name}: invalid criterion points')
        if len(set(ids)) != len(ids):
            errors.append(f'{q.name}: duplicate criterion identifiers')
        uncovered = sorted(set(ids) - criteria_seen)
        if uncovered:
            errors.append(f'{q.name}: criteria without any assertion: {uncovered}')


def _check_reference_is_derived(p, errors):
    """A copy-only oracle cannot show the task is solvable from visible inputs."""
    q = p / 'solution/solve.sh'
    if not q.is_file():
        return
    body = q.read_text(errors='replace')
    if 'build_reference.py' not in body:
        errors.append(
            'solution/solve.sh does not invoke build_reference.py; a derived reference '
            'solution is required (copy-only oracles do not prove solvability)')


def _check_reward_plumbing(p, errors):
    """grade.py must write both reward.json and report.json under /logs/verifier."""
    grade = p / 'tests/grade.py'
    test_sh = p / 'tests/test.sh'
    if grade.is_file():
        body = grade.read_text(errors='replace')
        if 'reward.json' not in body:
            errors.append('tests/grade.py does not write /logs/verifier/reward.json')
        if 'report.json' not in body:
            errors.append('tests/grade.py does not write /logs/verifier/report.json')
        if 'reward.txt' in body:
            errors.append('tests/grade.py writes reward.txt; the contract uses reward.json only')
    if test_sh.is_file():
        body = test_sh.read_text(errors='replace')
        if 'grade.py' not in body:
            errors.append('tests/test.sh does not invoke tests/grade.py')


def _check_verifier_failure_channel(p, errors):
    """Verifier failure must be recorded distinctly from a candidate scoring zero."""
    grade = p / 'tests/grade.py'
    if not grade.is_file():
        return
    body = grade.read_text(errors='replace')
    for token in ('verifier_failure', 'graded_candidate_defect', 'graded'):
        if token not in body:
            errors.append(f'tests/grade.py does not use the status {token!r}; '
                          'scoring failures must be distinguishable from candidate defects')


def _check_agent_view_isolated(p, errors):
    for name in FORBIDDEN_IN_AGENT_VIEW:
        for q in (p / 'environment').rglob(name):
            errors.append(f'grading/reference file visible to the agent: {q.relative_to(p)}')


def _check_lineage(p, errors):
    q = p / 'lineage.json'
    if not q.is_file():
        errors.append('Missing lineage.json')
        return
    try:
        doc = json.loads(q.read_text())
    except ValueError as exc:
        errors.append(f'lineage.json: invalid JSON: {exc}')
        return
    for field in LINEAGE_REQUIRED:
        if field not in doc:
            errors.append(f'lineage.json: missing {field}')
    if doc.get('task_id') and doc.get('task_id') != p.name:
        errors.append(f'lineage.json: task_id {doc["task_id"]!r} does not match directory {p.name!r}')


def _check_no_host_paths(p, errors):
    """Author machine paths must never ship inside the package."""
    needles = ('/Users/', '/home/', 'C:\\Users\\')
    for q in p.rglob('*'):
        if not q.is_file() or '.git' in q.parts:
            continue
        if q.suffix.lower() not in ('.json', '.md', '.toml', '.sh', '.py', '.yaml', '.yml', '.txt'):
            continue
        try:
            text = q.read_text(errors='replace')
        except OSError:
            continue
        for needle in needles:
            if needle in text:
                errors.append(f'host path leaked in {q.relative_to(p)}: {needle}')
                break


def validate(path, require_harbor=False):
    p = Path(path).resolve()
    errors, hashes, records = [], {}, {}
    _check_files(p, errors, hashes)

    cfg = {}
    try:
        cfg = tomllib.loads((p / 'task.toml').read_text())
    except (OSError, ValueError) as exc:
        errors.append(f'Invalid task.toml: {exc}')

    inputs = p / 'environment/input-data'
    if not inputs.exists() or not any(q.is_file() and q.stat().st_size for q in inputs.rglob('*')):
        errors.append('No nonempty visible input files')

    if cfg.get('verifier', {}).get('environment_mode') == 'separate':
        q = p / 'tests/Dockerfile'
        if not q.is_file() or not q.stat().st_size:
            errors.append('Separate verifier requires tests/Dockerfile in this delivery contract')

    _check_assertions(p, errors, records)
    _check_rubric_coverage(p, errors, records)
    _check_reference_is_derived(p, errors)
    _check_reward_plumbing(p, errors)
    _check_verifier_failure_channel(p, errors)
    _check_agent_view_isolated(p, errors)
    _check_lineage(p, errors)
    _check_no_host_paths(p, errors)

    harbor_status = 'not_available'
    try:
        from harbor.models.task.task import Task
        Task(p).config
        harbor_status = 'passed'
    except ImportError:
        if require_harbor:
            errors.append('Harbor is required but unavailable')
    except Exception as exc:
        harbor_status = 'failed'
        errors.append(f'Harbor parsing failed: {type(exc).__name__}: {exc}')

    return {
        'task': p.name,
        'path': str(p),
        'static_preflight': 'passed' if not errors else 'failed',
        'harbor_schema': harbor_status,
        'errors': errors,
        'warnings': records.get('warnings', []),
        'entrypoint_sha256': hashes,
        'assertion_count': records.get('assertion_count'),
        'criteria_covered': records.get('criteria_covered'),
        'runtime_validation': 'not_run',
        'professional_quality': 'not_evaluated',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--require-harbor', action='store_true')
    args = parser.parse_args()
    records = [validate(p, args.require_harbor) for p in args.paths]
    print(json.dumps({'results': records}, ensure_ascii=False, indent=2))
    raise SystemExit(any(r['errors'] for r in records))
