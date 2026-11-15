"""Check published counts and source fingerprint, without API calls or private data.

This validates internal consistency, not the truth of private model answers.
"""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports' / '2026-11-15-deepseek'
BASELINE_COMMIT = 'acb3cfa991b9d5047f2bf90772a16e8ba9f749f8'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    rows = json.loads((REPORT / 'trials.json').read_text())
    summary = json.loads((REPORT / 'summary.json').read_text())
    manifest = json.loads((REPORT / 'manifest.json').read_text())
    require(summary['complete'] is True, 'Run is incomplete')
    require(len(rows) == manifest['planned_jobs'] == 300, 'Trial count mismatch')
    require(len({r['job_id'] for r in rows}) == len(rows), 'Duplicate trial IDs')
    require(all(r['transport'] == 'real_api' and r['model_steps'] > 0 for r in rows), 'Missing API-response metadata')
    require(not any({'audit', 'answer', 'question', 'arguments', 'evidence', 'api_key'} & r.keys() for r in rows), 'Private field in public report')
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['suite'], row['id'])].append(row)
    require(len(grouped) == 150, 'Unique task count mismatch')
    require(all(Counter(r['repeat'] for r in group) == {1: 1, 2: 1} for group in grouped.values()), 'Each task must have exactly two repeats')

    def check_group(subset, expected):
        tasks = defaultdict(list)
        for row in subset:
            tasks[(row['suite'], row['id'])].append(row)
        actual = dict(runs=len(subset), unique_tasks=len(tasks),
                      passed_runs=sum(r['task_success'] for r in subset),
                      all_repeats_passed_tasks=sum(all(r['task_success'] for r in group) for group in tasks.values()),
                      runtime_enforced_abstentions=sum(r.get('runtime_abstained', False) for r in subset),
                      model_reported_abstentions=sum(r.get('model_abstained', False) for r in subset),
                      provider_errors=sum(r['run_status'] == 'provider_error' for r in subset),
                      trials_with_model_response=sum(r['model_steps'] > 0 for r in subset))
        require(all(expected[k] == v for k, v in actual.items()), 'Summary counts differ from trial records')
        require(abs(expected['run_success_rate'] - actual['passed_runs'] / actual['runs']) < 1e-12, 'Rate mismatch')
        require(abs(expected['consistent_task_rate'] - actual['all_repeats_passed_tasks'] / actual['unique_tasks']) < 1e-12, 'Consistency rate mismatch')

    check_group(rows, summary['overall'])
    for suite, expected in summary['by_suite'].items():
        check_group([r for r in rows if r['suite'] == suite], expected)
    for key, expected in summary['by_family'].items():
        suite, family = key.split('/')
        check_group([r for r in rows if r['suite'] == suite and r['family'] == family], expected)
    require(sum(r['tokens'] for r in rows) == summary['total_tokens'], 'Token count mismatch')
    require(sum(r['model_steps'] for r in rows) == summary['total_model_steps'], 'Step count mismatch')
    require(sorted({m for r in rows for m in r['resolved_models']}) == summary['resolved_models'], 'Model name mismatch')

    # The baseline is immutable. Later upgrades must not pretend its score applies
    # to the working tree; resolve the exact evaluated source from the public commit.
    def baseline_file(name):
        return subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                        f'{BASELINE_COMMIT}:hip-fracture-agent/{name}'])
    module = ast.parse(baseline_file('run_live_suite.py').decode())
    files = next(ast.literal_eval(node.value) for node in module.body
                 if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCE_FILES' for t in node.targets))
    source_hash = hashlib.sha256(b''.join(baseline_file(name) for name in files)).hexdigest()
    require(source_hash == manifest['source_sha256'], 'Pinned baseline source differs from the evaluated version')
    o = summary['overall']
    print(f"Verified {o['passed_runs']}/{o['runs']} trial passes and {o['all_repeats_passed_tasks']}/{o['unique_tasks']} tasks passing both repeats.")
    print(f'Evaluated source fingerprint matches historical commit {BASELINE_COMMIT}.')
    print('This does not validate the current working tree. Private answers and data were not regraded.')


if __name__ == '__main__':
    verify()
