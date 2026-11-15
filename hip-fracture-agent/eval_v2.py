"""Auditable statistical benchmark, separate from legacy heuristic/clinical scores.

144 query specifications = 12 query families x 12 cohorts, not 144 independent
clinical scenarios. Tools mode never calls an LLM. Live mode is explicit.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time
import pandas as pd
from tool_contracts import StatisticsArguments

VERSION = 'statistics-v2.1'
COHORTS = [
    ('all records', []),
    ('female patients (sex=2)', [('sex','eq',2)]),
    ('male patients (sex=1)', [('sex','eq',1)]),
    ('ASA grade IV patients (asa=4)', [('asa','eq',4)]),
    ('ASA grade III patients (asa=3)', [('asa','eq',3)]),
    ('patients aged at least 80', [('age','ge',80)]),
    ('patients younger than 80', [('age','lt',80)]),
    ('patients aged at least 90', [('age','ge',90)]),
    ('patients with frailty score at least 7', [('frailty','ge',7)]),
    ('aged-care residents (uresidence=2)', [('uresidence','eq',2)]),
    ('female patients aged at least 80', [('sex','eq',2),('age','ge',80)]),
    ('ASA IV patients aged at least 80', [('asa','eq',4),('age','ge',80)]),
]
FAMILIES = [
    ('count','count',None,None,'How many records are there'),
    ('mean_age','mean','age',None,'What is the mean age'),
    ('median_age','median','age',None,'What is the median age'),
    ('mean_frailty','mean','frailty',None,'What is the mean frailty score'),
    ('median_frailty','median','frailty',None,'What is the median frailty score'),
    ('mort30','proportion',None,('mort30d','eq',2),'What fraction have mort30d=2 (30-day death)'),
    ('mort365','proportion',None,('mort365d','eq',2),'What fraction have mort365d=2 (365-day death)'),
    ('walking','proportion',None,('fwalk2','eq',1),'What fraction have fwalk2=1 (walking recovered)'),
    ('rehab','proportion',None,('wdest','in',[3,4]),'What fraction have wdest in [3,4] (rehabilitation discharge)'),
    ('geriatric','proportion',None,('gerimed','eq',1),'What fraction have gerimed=1 (geriatric assessment)'),
    ('female','proportion',None,('sex','eq',2),'What fraction have sex=2 (female)'),
    ('age80','proportion',None,('age','ge',80),'What fraction are aged at least 80'),
]
DEV_FAMILIES = {'count','mean_age','mort30','walking'}


def rule(value):
    return dict(zip(('column','op','value'),value))


def build_cases():
    cases=[]
    for family,metric,column,event,prompt in FAMILIES:
        for c,(description,filters) in enumerate(COHORTS):
            question=f'{prompt} among {description}? Use only non-missing values of the measured/event column as the denominator; keep all other cohort filters.'
            plan=dict(question=question,metric=metric,column=column,filters=[rule(f) for f in filters],event=rule(event) if event else None)
            cases.append(dict(id=f'{family}-{c:02d}',family=family,split='dev' if family in DEV_FAMILIES else 'holdout',question=question,plan=plan))
    return cases


def canonical_plan(arguments):
    p=StatisticsArguments.model_validate(arguments).model_dump(exclude_none=True)
    p.pop('question')
    if p['metric'] not in ('mean','median','distribution'):
        p.pop('column',None)
    p['filters']=[json.loads(x) for x in sorted({json.dumps(r,sort_keys=True) for r in p.get('filters',[])})]
    return p


def reference_value(df, case):
    """Independent pandas oracle; does not call production query/mask functions."""
    plan=case['plan']; subset=df.copy(deep=False)
    operations={'eq':lambda s,v:s==v,'ne':lambda s,v:s!=v,'ge':lambda s,v:s>=v,
                'gt':lambda s,v:s>v,'le':lambda s,v:s<=v,'lt':lambda s,v:s<v,'in':lambda s,v:s.isin(v)}
    for condition in plan['filters']:
        values=pd.to_numeric(subset[condition['column']],errors='coerce')
        subset=subset.loc[values.notna() & operations[condition['op']](values,condition['value'])]
    if plan['metric']=='count':return len(subset),'records'
    if plan['metric']=='proportion':
        condition=plan['event'];valid=pd.to_numeric(subset[condition['column']],errors='coerce').dropna()
        return (float(operations[condition['op']](valid,condition['value']).mean()) if len(valid) else None),'fraction'
    values=pd.to_numeric(subset[plan['column']],errors='coerce').dropna()
    return (float(values.mean() if plan['metric']=='mean' else values.median()) if len(values) else None),'numeric'


def numeric_match(value,expected):
    if expected is None:return value is None
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and abs(value-expected)<=0.0001


def score_answer(answer,expected,unit):
    """No first-number heuristic, expected-value-guided parsing, or LLM-as-judge."""
    try:
        result=json.loads(answer)
        if not isinstance(result,dict) or set(result)!={'value','unit','abstained'}:
            return False,False
        valid=type(result['abstained']) is bool and result['unit'] in ('fraction','records','numeric')
        correct=valid and result['unit']==unit and numeric_match(result['value'],expected) and result['abstained']==(expected is None)
        return valid,bool(correct)
    except (ValueError,TypeError):return False,False


def wilson(successes,n):
    if not n:return None
    z=1.959963984540054; p=successes/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(max(0,mid-half),4),round(min(1,mid+half),4)]


def summarise(rows,mode):
    families=sorted({r['family'] for r in rows})
    metrics=('execution_correct',) if mode=='tools' else ('tool_selected','plan_correct','answer_schema_valid','answer_correct','end_to_end_correct')
    result=dict(mode=mode,n_runs=len(rows),n_unique_cases=len({r['id'] for r in rows}),n_families=len(families),metrics={},by_family={})
    for key in metrics:
        # Treat repeated runs of a case as one cluster: all repeats must pass.
        ids={r['id'] for r in rows}
        successes=sum(all(r.get(key,False) for r in rows if r['id']==i) for i in ids)
        result['metrics'][key]=dict(consistent_pass_cases=successes,n_cases=len(ids),rate=successes/len(ids) if ids else None,
                                   nominal_wilson95=wilson(successes,len(ids)) if mode=='live' else None)
    for family in families:
        sub=[r for r in rows if r['family']==family]
        result['by_family'][family]={key:sum(r.get(key,False) for r in sub)/len(sub) for key in metrics}
    result['limitations']=[
        'Self-authored statistical query benchmark; no independent external validation.',
        'Nested cohorts and related query families are correlated; nominal Wilson intervals do not establish generalisation.',
        'Repeated runs are not counted as new questions. Family-level results are reported separately.',
        'Prediction quality, clinical factuality and guideline citation entailment are outside this benchmark.',
        'Tools-mode passes measure local software behaviour, not LLM accuracy.'
    ]
    return result


ANSWER_FORMAT = '\nFor this benchmark return ONLY JSON with exactly value, unit and abstained. Use fraction for proportions, records for counts, numeric for means/medians. Use at least 4 decimal places for non-integers. If the tool has no valid observations, set value=null and abstained=true. Do not include prose or code fences.'


def run(mode='tools',split='dev',repeats=1,limit=None,provider='openai',data_path=None):
    from agent import HipFractureAgent,_call_tool
    import agent_tools
    if repeats<1:raise ValueError('repeats must be positive')
    cases=[c for c in build_cases() if split=='all' or c['split']==split]
    if limit is not None:
        if limit<1:raise ValueError('limit must be positive')
        cases=cases[:limit]
    path=Path(data_path or agent_tools.DATA_PATH)
    df=pd.read_csv(path,low_memory=False)
    # Ensure oracle and production tool use precisely the same authorised local file.
    old_cache=agent_tools._df_cache
    agent_tools._df_cache=df
    rows=[]
    try:
        for repeat in range(repeats):
            for case in cases:
                expected,unit=reference_value(df,case)
                row=dict(id=case['id'],family=case['family'],split=case['split'],repeat=repeat+1)
                start=time.monotonic()
                try:
                    if mode=='tools':
                        payload=json.loads(_call_tool('query_patient_data',case['plan']))
                        value=payload.get('data',{}).get('value')
                        status_ok=payload.get('ok') is True if expected is not None else payload.get('error',{}).get('code')=='no_data'
                        row['execution_correct']=status_ok and numeric_match(value,expected)
                    elif mode=='live':
                        calls=[]
                        def capture(name,arguments):
                            result=_call_tool(name,arguments)
                            calls.append((name,arguments,json.loads(result)))
                            return result
                        agent=HipFractureAgent(provider=provider,dispatch=capture)
                        answer=agent.chat(case['question']+ANSWER_FORMAT)
                        row['tool_selected']=any(n=='query_patient_data' for n,_,_ in calls)
                        row['plan_correct']=False
                        for name,args,payload in calls:
                            if name=='query_patient_data' and (payload.get('ok') or payload.get('error',{}).get('code')=='no_data'):
                                try:row['plan_correct'] |= canonical_plan(args)==canonical_plan(case['plan'])
                                except ValueError:pass
                        row['answer_schema_valid'],row['answer_correct']=score_answer(answer,expected,unit)
                        row['end_to_end_correct']=row['plan_correct'] and row['answer_correct']
                        row['run_status']=agent.last_run['status']
                    else:raise ValueError('mode must be tools or live')
                except Exception as exc:
                    # No data, raw answers, tool arguments or credentials in saved reports.
                    row['error_type']=type(exc).__name__
                row['latency_ms']=round((time.monotonic()-start)*1000,2)
                rows.append(row)
    finally:
        agent_tools._df_cache=old_cache
    manifest=[{k:c[k] for k in ('id','family','split','question','plan')} for c in cases]
    source_root=Path(__file__).resolve().parent
    source_hash=hashlib.sha256(b''.join((source_root/name).read_bytes() for name in ('agent.py','agent_tools.py','tool_contracts.py','statistics_query.py','eval_v2.py'))).hexdigest()
    model=os.environ.get('ANTHROPIC_MODEL' if provider=='anthropic' else 'OPENAI_MODEL', 'claude-sonnet-4-6' if provider=='anthropic' else 'gpt-4o')
    return dict(version=VERSION,source_sha256=source_hash,provider=provider if mode=='live' else None,model=model if mode=='live' else None,case_manifest_sha256=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
                dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                summary=summarise(rows,mode),results=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['tools','live'],default='tools')
    parser.add_argument('--split',choices=['dev','holdout','all'],default='dev')
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--provider',choices=['openai','anthropic'],default='openai')
    parser.add_argument('--data')
    parser.add_argument('--output',default='eval_results_v2.json')
    args=parser.parse_args()
    report=run(args.mode,args.split,args.repeats,args.limit,args.provider,args.data)
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps(report['summary'],indent=2,ensure_ascii=False))
