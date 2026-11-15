import json
import unittest
from types import SimpleNamespace as NS
from eval_tasks import build_tasks,grade,expected
from evidence import EvidenceLedger
from eval_v2 import canonical_plan
from run_live_suite import summarise


class TaskScoringTests(unittest.TestCase):
    def test_redundant_filter_is_not_a_false_negative(self):
        p={'question':'q','metric':'count','filters':[{'column':'sex','op':'eq','value':2}]}
        q=dict(p);q['filters']=p['filters']*2
        self.assertEqual(canonical_plan(p),canonical_plan(q))
    def test_correct_number_without_dependency_evidence_fails(self):
        task=build_tasks()[0]
        agent=NS(evidence=EvidenceLedger(),last_run={'status':'completed'},trace=[])
        result=grade(task,json.dumps({'value':2,'unit':'years','abstained':False,'evidence_id':'E3'}),2,task['plans'],agent,[],NS(injected=0,calls=[]))
        self.assertTrue(result['numeric_correct'])
        self.assertFalse(result['task_success'])
    def test_runtime_and_model_abstentions_are_separate(self):
        task=next(t for t in build_tasks() if t['family']=='permanent_failure')
        agent=NS(evidence=EvidenceLedger(),last_run={'status':'no_evidence'},trace=[])
        result=grade(task,'No evidence',None,task['plans'],agent,[],NS(injected=1,calls=[('query_patient_data',task['plans'][-1])]))
        self.assertTrue(result['task_success']);self.assertTrue(result['runtime_abstained'])
        self.assertFalse(result['model_abstained'])
    def test_fault_needs_to_be_exercised(self):
        task=next(t for t in build_tasks() if t['family']=='permanent_failure')
        agent=NS(evidence=EvidenceLedger(),last_run={'status':'no_evidence'},trace=[])
        self.assertFalse(grade(task,'No evidence',None,task['plans'],agent,[],NS(injected=0,calls=[]))['task_success'])
    def test_aggregate_does_not_count_repeats_as_independent_tasks(self):
        rows=[dict(suite='workflow',id='a',family='f',task_success=True,latency_ms=20,repeat=1),
              dict(suite='workflow',id='a',family='f',task_success=False,latency_ms=30,repeat=2)]
        s=summarise(rows)['overall']
        self.assertEqual((s['runs'],s['unique_tasks'],s['all_repeats_passed_tasks']),(2,1,0))
    def test_formal_suites_have_150_unique_tasks(self):
        from eval_v2 import build_cases
        self.assertEqual(sum(c['split']=='holdout' for c in build_cases())+sum(c['split']=='holdout' for c in build_tasks()),150)
    def test_conditional_branch_requires_a_later_model_step(self):
        task=next(t for t in build_tasks() if t['family']=='conditional_followup')
        plans=[task['plans'][0],task['branches'][1]]
        ledger=EvidenceLedger()
        for p,value in zip(plans,[81,10]):
            ledger.add('query_patient_data',{'ok':True,'data':{'value':value}},p)
        trace=[dict(evidence_id='E1',model_step=1),dict(evidence_id='E2',model_step=1)]
        agent=NS(evidence=ledger,last_run={'status':'completed'},trace=trace)
        answer=json.dumps(dict(value=10,unit='records',abstained=False,evidence_id='E2'))
        self.assertFalse(grade(task,answer,10,plans,agent,[],NS())['task_success'])
        trace[1]['model_step']=2
        self.assertTrue(grade(task,answer,10,plans,agent,[],NS())['task_success'])
