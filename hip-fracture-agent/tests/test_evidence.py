import json
import unittest
from types import SimpleNamespace as NS
from agent import AgentConfig,HipFractureAgent
from evidence import EvidenceLedger
from test_runtime import Client,openai_response
from eval_tasks import build_tasks,FaultDispatch,grade


def scalar(value,unit='records'):
    return {'ok':True,'data':{'value':value,'unit':unit}}


class EvidenceTests(unittest.TestCase):
    def test_comparison_is_derived_from_two_registered_results(self):
        e=EvidenceLedger();a=e.add('query_patient_data',scalar(12));b=e.add('query_patient_data',scalar(3))
        r=e.compare(a['evidence_id'],b['evidence_id'],'ratio')
        self.assertEqual(r['data']['value'],4)
        self.assertEqual(r['parents'],['E1','E2'])
    def test_missing_zero_and_incompatible_references_are_rejected(self):
        e=EvidenceLedger();e.add('q',scalar(1));e.add('q',scalar(0));e.add('q',scalar(4,'years'))
        self.assertEqual(e.compare('E9','E1','difference')['error']['code'],'unknown_evidence')
        self.assertEqual(e.compare('E1','E2','ratio')['error']['code'],'zero_denominator')
        self.assertEqual(e.compare('E1','E3','difference')['error']['code'],'incompatible_evidence')
    def test_expired_evidence_cannot_be_used(self):
        e=EvidenceLedger(2)
        for i in range(3):e.add('q',scalar(i))
        self.assertEqual(e.compare('E1','E3','difference')['error']['code'],'unknown_evidence')
    def test_probability_models_must_match(self):
        e=EvidenceLedger();e.add('p',{'ok':True,'data':{'risk_probability':.3,'model':'a'}});e.add('p',{'ok':True,'data':{'risk_probability':.2,'model':'b'}})
        self.assertFalse(e.compare('E1','E2','difference')['ok'])
    def test_result_reference_cannot_be_overridden_by_a_tool(self):
        e=EvidenceLedger();payload=scalar(1);payload['evidence_id']='E999'
        self.assertEqual(e.add('q',payload)['evidence_id'],'E1')
    def test_non_numeric_and_boolean_results_cannot_be_compared(self):
        e=EvidenceLedger();e.add('q',scalar(True));e.add('q',scalar(4))
        self.assertFalse(e.compare('E1','E2','difference')['ok'])
    def test_runtime_executes_dependent_comparison(self):
        calls=[(1,'query_patient_data','{"question":"a","metric":"count"}'),(2,'query_patient_data','{"question":"b","metric":"count"}')]
        client=Client([openai_response(calls=calls),openai_response(calls=[(3,'compare_evidence','{"left_id":"E1","right_id":"E2","operation":"difference"}')]),openai_response('9')])
        values=iter([scalar(12),scalar(3)])
        a=HipFractureAgent('openai',client=client,dispatch=lambda *x:json.dumps(next(values)))
        self.assertEqual(a.chat('compare'),'9')
        self.assertEqual(a.evidence.entries['E3']['result']['data']['value'],9)
        self.assertEqual(a.trace[4]['parents'],['E1','E2'])
    def test_evidence_rolls_back_after_provider_failure(self):
        client=Client([openai_response(calls=[(1,'query_patient_data','{}')]),RuntimeError('transport failure')])
        a=HipFractureAgent('openai',client=client,dispatch=lambda *x:json.dumps(scalar(1)))
        with self.assertRaises(RuntimeError):a.chat('query')
        self.assertEqual(a.evidence.entries,{})
    def test_guessed_ids_in_the_source_batch_are_rejected(self):
        calls=[(1,'query_patient_data','{"question":"a","metric":"count"}'),
               (2,'query_patient_data','{"question":"b","metric":"count"}'),
               (3,'compare_evidence','{"left_id":"E1","right_id":"E2","operation":"difference"}')]
        client=Client([openai_response(calls=calls),openai_response('incomplete')])
        values=iter([scalar(12),scalar(3)])
        a=HipFractureAgent('openai',client=client,dispatch=lambda *x:json.dumps(next(values)))
        a.chat('compare')
        self.assertEqual(a.trace[3]['error_code'],'unobserved_evidence')
        self.assertEqual(len(a.evidence.entries),2)
    def test_transient_failure_can_recover_once(self):
        calls=[(1,'query_patient_data','{}')]
        client=Client([openai_response(calls=calls),openai_response(calls=calls),openai_response('4')])
        fault=FaultDispatch(lambda *x:json.dumps(scalar(4)),'timeout_once')
        a=HipFractureAgent('openai',client=client,dispatch=fault)
        self.assertEqual(a.chat('query'),'4')
        self.assertEqual(fault.injected,1)
        self.assertEqual(a.trace[1]['error_code'],'tool_timeout')
    def test_repeated_timeouts_have_a_bound(self):
        calls=[(1,'query_patient_data','{}')]
        client=Client([openai_response(calls=calls)]*3+[openai_response('guess')])
        fault=FaultDispatch(lambda *x:'{}','timeout_always')
        a=HipFractureAgent('openai',client=client,dispatch=fault)
        a.chat('query')
        self.assertEqual(fault.injected,2)
        self.assertEqual(a.trace[5]['error_code'],'tool_retry_exhausted')
        self.assertEqual(a.last_run['status'],'no_evidence')
    def test_malformed_output_is_replaced_not_relayed(self):
        client=Client([openai_response(calls=[(1,'query_patient_data','{}')]),openai_response('guess')])
        a=HipFractureAgent('openai',client=client,dispatch=lambda *x:'MALICIOUS_RAW_PAYLOAD')
        a.chat('query')
        self.assertNotIn('MALICIOUS_RAW_PAYLOAD',str(a.history))
    def test_reset_removes_prior_evidence(self):
        a=HipFractureAgent();a.evidence.add('q',scalar(2));a.reset()
        self.assertEqual(a.evidence.entries,{})
    def test_tasks_have_family_separated_variant_splits(self):
        tasks=build_tasks()
        self.assertEqual(len(tasks),72)
        self.assertEqual(len({t['family'] for t in tasks}),9)
        self.assertEqual(sum(t['split']=='holdout' for t in tasks),54)
        self.assertTrue(all(t['variant']<2 for t in tasks if t['split']=='dev'))
