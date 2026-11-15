"""Verify published v4 regression metadata and the current evaluated source.

No restricted data or API required. This is not independent answer regrading.
"""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/2026-11-15-output-validation'

def require(condition, message):
    if not condition:raise ValueError(message)


def verify():
    rows=json.loads((REPORT/'trials.json').read_text())
    summary=json.loads((REPORT/'summary.json').read_text())
    manifest=json.loads((REPORT/'manifest.json').read_text())
    allowed={'job_id','suite','id','family','split','repeat','transport','tool_selected','plan_correct',
             'answer_schema_valid','numeric_correct','dependency_correct','citation_consistent','task_success',
             'model_abstained','runtime_abstained','fault','fault_injections','run_status','latency_ms',
             'model_steps','tokens','resolved_models','tool_calls','answer_repairs','answer_validated'}
    require(summary['complete'] and len(rows)==manifest['planned_jobs']==300,'Incomplete trial set')
    require(len({r['job_id'] for r in rows})==300,'Duplicate trial')
    require(all(set(r)<=allowed for r in rows),'Unexpected public field')
    require(all(r['transport']=='real_api' and r['model_steps']>0 for r in rows),'Missing model metadata')
    groups=defaultdict(list)
    for r in rows:
        groups[(r['suite'],r['id'])].append(r)
        require(not (r['model_abstained'] and r['runtime_abstained']),'Abstention counted twice')
    require(len(groups)==150 and all(Counter(r['repeat'] for r in g)=={1:1,2:1} for g in groups.values()),'Repeat groups differ')
    require(sum(r['task_success'] for r in rows)==summary['overall']['passed_runs']==296,'Pass count differs')
    require(sum(all(r['task_success'] for r in g) for g in groups.values())==summary['overall']['all_repeats_passed_tasks']==147,'Consistency differs')
    require(sum(r['answer_repairs'] for r in rows)==summary['answer_repairs']==4,'Repair count differs')
    for key in ('tokens','model_steps'):
        require(sum(r[key] for r in rows)==summary['total_'+key],key+' count differs')
    module=ast.parse((ROOT/'run_live_suite.py').read_text())
    files=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id=='SOURCE_FILES' for t in n.targets))
    actual=hashlib.sha256(b''.join((ROOT/f).read_bytes() for f in files)).hexdigest()
    require(actual==manifest['source_sha256'],'Current source is not this evaluated version')
    print('Verified 296/300 passes, 147/150 tasks passing both repeats, no duplicate abstentions, and matching source fingerprint.')
    print('Regression of inspected tasks, not a fresh blind holdout. Private answers were not regraded.')

if __name__=='__main__':verify()
