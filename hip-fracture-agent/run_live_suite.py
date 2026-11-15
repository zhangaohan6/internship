"""Resumable real-API evaluation runner. Never substitutes a mock for an API result."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import statistics
import threading
import time
from urllib.parse import urlparse
import pandas as pd
from dotenv import dotenv_values
from agent import AgentConfig,HipFractureAgent,_call_tool
from answer_contract import AnswerContract
import agent_tools
from eval_v2 import build_cases,canonical_plan,reference_value,score_answer,ANSWER_FORMAT,wilson
from eval_tasks import build_tasks,expected,grade,FaultDispatch,final_prompt

ROOT=Path(__file__).resolve().parent
SOURCE_FILES=['agent.py','agent_tools.py','train_model.py','tool_contracts.py','statistics_query.py','evidence.py',
              'rag_pipeline.py','eval_v2.py','eval_tasks.py','run_live_suite.py','answer_contract.py']


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def load_config(env_file,provider,model):
    values=dotenv_values(env_file) if env_file else {}
    prefix='ANTHROPIC' if provider=='anthropic' else 'OPENAI'
    key=os.environ.get(prefix+'_API_KEY') or values.get(prefix+'_API_KEY')
    base=os.environ.get(prefix+'_BASE_URL') or values.get(prefix+'_BASE_URL')
    selected=model or os.environ.get(prefix+'_MODEL') or values.get(prefix+'_MODEL')
    if not key:raise ValueError('No API key configured for the selected provider')
    if not selected:raise ValueError('Choose an explicit model version for reproducible evaluation')
    return AgentConfig(provider=provider,model=selected,base_url=base,timeout=45,max_retries=1,max_steps=10,max_tool_calls=20),key


def preflight(config,key):
    a=HipFractureAgent(config=config,api_key=key)
    client=a._get_client()
    if config.provider=='anthropic':
        r=client.messages.create(model=config.model,max_tokens=16,messages=[{'role':'user','content':'Reply exactly OK.'}])
        return {'model':r.model,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens}
    r=client.chat.completions.create(model=config.model,max_tokens=16,messages=[{'role':'user','content':'Reply exactly OK.'}])
    return {'model':r.model,'total_tokens':r.usage.total_tokens}


@lru_cache(maxsize=128)
def prediction_reference(tool,patient_json):
    # Local artifact inference is the tool-output oracle, not a patient outcome label.
    result=json.loads(_call_tool(tool,{'patient':json.loads(patient_json)}))
    if not result.get('ok'):raise RuntimeError('Local prediction oracle unavailable')
    return result['data']['risk_probability']


def run_one(suite,spec,repeat,config,key,df,validated_output=False):
    start=time.monotonic()
    row={'job_id':f'{suite}:{spec["id"]}:{repeat}','suite':suite,'id':spec['id'],
         'family':spec['family'],'split':spec['split'],'repeat':repeat,'transport':'real_api'}
    fault=FaultDispatch(_call_tool,spec.get('fault'))
    agent=HipFractureAgent(config=config,api_key=key,dispatch=fault)
    turns=[]
    prompt=''
    try:
        if suite=='statistics':
            value,unit=reference_value(df,spec)
            prompt=spec['question']+ANSWER_FORMAT
            contract=AnswerContract(unit=unit,export_evidence=False) if validated_output else None
            answer=agent.chat(prompt,answer_contract=contract)
            turns.append({'question':prompt,'answer':answer,'run':dict(agent.last_run),'trace':list(agent.trace)})
            selected=any(n=='query_patient_data' for n,_ in fault.calls)
            correct_plan=False
            for entry in agent.evidence.entries.values():
                if entry['tool']=='query_patient_data':
                    try:correct_plan |= canonical_plan(entry['arguments'])==canonical_plan(spec['plan'])
                    except ValueError:pass
            schema,correct_answer=score_answer(answer,value,unit)
            try:
                parsed=json.loads(answer)
            except (ValueError,TypeError):
                parsed={}
            runtime_abstained=agent.last_run.get('status') in ('no_evidence','budget_exhausted','answer_rejected')
            model_abstained=not runtime_abstained and isinstance(parsed,dict) and parsed.get('abstained') is True and parsed.get('value') is None
            row.update(tool_selected=selected,plan_correct=bool(correct_plan),answer_schema_valid=schema,numeric_correct=correct_answer,
                       task_success=bool(correct_plan and correct_answer),model_abstained=model_abstained,runtime_abstained=runtime_abstained)
        else:
            value,plans=expected(spec,df,lambda t,p:prediction_reference(t,json.dumps(p,sort_keys=True)))
            for i,message in enumerate(spec['messages']):
                prompt=message+(final_prompt(spec) if i==len(spec['messages'])-1 else ANSWER_FORMAT if spec['family']=='context_refinement' else '')
                contract=None
                if validated_output:
                    if i==len(spec['messages'])-1:
                        contract=AnswerContract(unit=spec['unit'],require_citation=spec['expected_kind']=='retrieval')
                    elif spec['family']=='context_refinement':
                        contract=AnswerContract(unit='numeric',export_evidence=False)
                answer=agent.chat(prompt,answer_contract=contract)
                turns.append({'question':prompt,'answer':answer,'run':dict(agent.last_run),'trace':list(agent.trace)})
            row.update(grade(spec,answer,value,plans,agent,turns,fault))
            row['fault']=spec.get('fault')
            row['fault_injections']=fault.injected
        row['run_status']=agent.last_run.get('status')
    except Exception as exc:
        turns.append({'question':prompt,'answer':None,'run':dict(agent.last_run),'trace':list(agent.trace)})
        row.update(task_success=False,error_type=type(exc).__name__,provider_error=agent.last_run.get('provider_error_code'),
                   provider_http_status=agent.last_run.get('provider_http_status'),run_status=agent.last_run.get('status','oracle_error'))
    row['latency_ms']=round((time.monotonic()-start)*1000,2)
    row['model_steps']=sum(t['run'].get('steps',0) for t in turns)
    row['tokens']=sum(t['run'].get('tokens',0) for t in turns)
    row['resolved_models']=sorted({m for t in turns for m in t['run'].get('resolved_models',[])})
    row['tool_calls']=sum(t['run'].get('tool_calls',0) for t in turns)
    row['answer_repairs']=sum(t['run'].get('answer_repairs',0) for t in turns)
    row['answer_validated']=agent.last_run.get('answer_validated',False)
    # Kept only in an ignored private audit directory. Public summaries omit this block.
    row['audit']={'turns':turns,'evidence':agent.evidence.entries,'last_run':agent.last_run}
    return row


def summarise(rows):
    def group(sub):
        ids=sorted({(r['suite'],r['id']) for r in sub})
        n=len(sub);passed=sum(r.get('task_success',False) for r in sub)
        consistent=sum(all(r.get('task_success',False) for r in sub if (r['suite'],r['id'])==key) for key in ids)
        latencies=sorted(r['latency_ms'] for r in sub)
        return {'runs':n,'unique_tasks':len(ids),'passed_runs':passed,'run_success_rate':passed/n if n else None,
                'all_repeats_passed_tasks':consistent,'consistent_task_rate':consistent/len(ids) if ids else None,
                'nominal_wilson95_for_consistent_tasks':wilson(consistent,len(ids)),
                'runtime_enforced_abstentions':sum(r.get('runtime_abstained',False) for r in sub),
                'model_reported_abstentions':sum(r.get('model_abstained',False) for r in sub),
                'provider_errors':sum(r.get('run_status')=='provider_error' for r in sub),
                'trials_with_model_response':sum(r.get('model_steps',0)>0 for r in sub),
                'p50_latency_ms':statistics.median(latencies) if latencies else None,
                'p95_latency_ms':latencies[math_index(.95,len(latencies))] if latencies else None}
    summary={'overall':group(rows),'by_suite':{},'by_family':{}}
    for suite in sorted({r['suite'] for r in rows}):summary['by_suite'][suite]=group([r for r in rows if r['suite']==suite])
    for suite,family in sorted({(r['suite'],r['family']) for r in rows}):
        summary['by_family'][suite+'/'+family]=group([r for r in rows if r['suite']==suite and r['family']==family])
    summary['total_model_steps']=sum(r.get('model_steps',0) for r in rows)
    summary['total_tokens']=sum(r.get('tokens',0) for r in rows)
    summary['resolved_models']=sorted({m for r in rows for m in r.get('resolved_models',[])})
    summary['limitations']=[
        'Self-authored tasks. Related query families and nested cohorts are correlated.',
        'Statistics split holds out query families; workflow split holds out variants within each family.',
        'Repeated runs are not independent tasks. Wilson intervals are nominal, not clinical generalisation guarantees.',
        'Fault scenarios inject errors at tool boundaries while calling a real LLM; they are not naturally observed outage rates.',
        'Success measures task contracts, numeric outputs and citation consistency; it does not establish clinical efficacy or full citation entailment.',
        'Some safe abstentions are enforced by runtime guards, reported separately from model-authored abstentions.'
    ]
    return summary


def math_index(q,n):
    import math
    return max(0,min(n-1,math.ceil(q*n)-1))


def execute(args):
    config,key=load_config(args.env_file,args.provider,args.model)
    if not 1<=args.workers<=4 or not 1<=args.repeats<=5:raise ValueError('workers 1..4, repeats 1..5 required')
    specifications=[]
    if args.suite in ('statistics','all'):
        specifications += [('statistics',c) for c in build_cases() if c['split']==args.split]
    if args.suite in ('workflow','all'):
        specifications += [('workflow',c) for c in build_tasks() if c['split']==args.split]
    if args.limit is not None:specifications=specifications[:args.limit]
    jobs=[(suite,spec,r) for r in range(1,args.repeats+1) for suite,spec in specifications]
    if not jobs or len(jobs)>args.max_jobs:raise ValueError('Empty selection or configured job budget exceeded')
    data_path=Path(args.data or agent_tools.DATA_PATH)
    guideline_dir=Path(os.environ.get('HIP_GUIDELINES_DIR',ROOT/'guidelines'))
    artifact_paths=sorted((ROOT/'models').glob('*.pkl'))+sorted(guideline_dir.glob('*.pdf'))
    manifest={'runner_version':'live-suite-v4.0','validated_output':getattr(args,'validated_output',False),
              'evaluation_use':'regression_after_baseline_inspection',
              'config':{k:v for k,v in asdict(config).items() if k!='base_url'},
              'endpoint_host':urlparse(config.base_url).hostname if config.base_url else ('api.anthropic.com' if config.provider=='anthropic' else 'api.openai.com'),
              'endpoint_path':urlparse(config.base_url).path if config.base_url else '/',
              'split':args.split,'repeats':args.repeats,'planned_jobs':len(jobs),'case_sha256':digest(specifications),
              'source_sha256':hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in SOURCE_FILES)).hexdigest(),
              'dataset_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),
              'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_paths},
              'retrieval':{'mode':os.environ.get('HIP_RAG_MODE','lexical'),'disabled':os.environ.get('HIP_NO_RAG')=='1'},
              'dependencies':{p:version(p) for p in ('anthropic','openai','pydantic','pandas')}}
    out=Path(args.output_dir)
    old=[]
    if out.exists() and (out/'manifest.json').exists():
        if not args.resume:raise ValueError('Output directory already contains a run; choose a new directory or --resume')
        previous=json.loads((out/'manifest.json').read_text())
        if previous!=manifest:raise ValueError('Resume requires identical source, data, cases and model configuration')
        old=[json.loads(line) for line in (out/'records.jsonl').read_text().splitlines() if line.strip()] if (out/'records.jsonl').exists() else []
    # No dataset or results are sent during this connectivity/billing check.
    connection=preflight(config,key)
    connection['checked_at_utc']=datetime.now(timezone.utc).isoformat()
    print(json.dumps({'preflight':'passed','model':connection['model'],'planned_jobs':len(jobs)},ensure_ascii=False),flush=True)
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(out,0o700)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'cases.json').write_text(json.dumps(specifications,indent=2))
    (out/'source').mkdir(exist_ok=True)
    for name in SOURCE_FILES:
        (out/'source'/name).write_bytes((ROOT/name).read_bytes())
    (out/'preflight.json').write_text(json.dumps(connection,indent=2))
    # Keep previous failed provider attempts in the audit; retry them on an explicit resume.
    done={r['job_id'] for r in old if r.get('run_status')!='provider_error'}
    pending=[j for j in jobs if f'{j[0]}:{j[1]["id"]}:{j[2]}' not in done]
    df=pd.read_csv(data_path,low_memory=False)
    original_cache=agent_tools._df_cache
    agent_tools._df_cache=df
    stop=threading.Event()
    def worker(job):
        if stop.is_set():return None
        result=run_one(*job,config,key,df,validated_output=getattr(args,'validated_output',False))
        if result.get('provider_error') in ('insufficient_credit','authentication','permission'):
            stop.set()
        return result
    records=list(old)
    path=out/'records.jsonl'
    path.touch(mode=0o600,exist_ok=True)
    os.chmod(path,0o600)
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool, path.open('a') as stream:
            futures=[pool.submit(worker,j) for j in pending]
            for future in as_completed(futures):
                result=future.result()
                if result is None:continue
                records.append(result)
                stream.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
                latest={r['job_id']:r for r in records}
                summary=summarise(list(latest.values()))
                summary['complete']=len(latest)==len(jobs) and not any(r.get('run_status')=='provider_error' for r in latest.values())
                summary['planned_jobs']=len(jobs)
                (out/'summary.json').write_text(json.dumps(summary,indent=2))
                print(json.dumps({'completed':len(latest),'planned':len(jobs),'job':result['job_id'],'success':result['task_success'],'status':result.get('run_status')},ensure_ascii=False),flush=True)
    finally:agent_tools._df_cache=original_cache
    latest={r['job_id']:r for r in records}
    summary=summarise(list(latest.values()))
    summary['complete']=len(latest)==len(jobs) and not any(r.get('run_status')=='provider_error' for r in latest.values())
    summary['planned_jobs']=len(jobs)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({'complete':summary['complete'],'overall':summary['overall']}),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['anthropic','openai'],default='anthropic')
    parser.add_argument('--model',required=True)
    parser.add_argument('--env-file')
    parser.add_argument('--suite',choices=['statistics','workflow','all'],default='all')
    parser.add_argument('--split',choices=['dev','holdout'],default='dev')
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--max-jobs',type=int,default=300)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--data')
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--validated-output',action='store_true',help='Validate answers against actual tool evidence, with bounded repair')
    args=parser.parse_args()
    try:
        result=execute(args)
        if not result['complete']:raise SystemExit(3)
    except Exception as exc:
        status=getattr(exc,'status_code',None)
        body=getattr(exc,'body',{})
        detail=body.get('error',body) if isinstance(body,dict) else {}
        message=detail.get('message','') if isinstance(detail,dict) else ''
        code='insufficient_credit' if any(w in str(message).lower() for w in ('credit','balance')) else type(exc).__name__
        print(json.dumps({'run_finished':False,'error':code,'http_status':status}),flush=True)
        raise SystemExit(2)
