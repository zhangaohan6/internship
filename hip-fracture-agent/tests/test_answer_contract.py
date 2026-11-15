import json
import unittest
from answer_contract import AnswerContract
from agent import AgentConfig, HipFractureAgent, _call_tool
from evidence import EvidenceLedger
from test_runtime import Client, openai_response, anthropic_response


def answer(value=12, unit='records', evidence_id='E1', **kwargs):
    return json.dumps(dict(value=value, unit=unit, abstained=False, evidence_id=evidence_id, **kwargs))


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = EvidenceLedger()
        self.ledger.add('query_patient_data', {'ok': True, 'data': {'value': 12, 'unit': 'records', 'metric': 'count'}})
        self.contract = AnswerContract(unit='records')

    def test_rejects_wrong_values_units_ids_and_nonfinite_values(self):
        for text in [answer(13), answer(unit='fraction'), answer(evidence_id='E99'),
                     answer(True), answer(float('nan')), answer(float('inf')), '```json\n'+answer()+'\n```']:
            with self.subTest(text=text):
                self.assertTrue(self.contract.check(text, self.ledger.entries)[1])
        self.assertEqual(self.contract.check(answer(), self.ledger.entries)[1], [])

    def test_abstention_cannot_carry_numeric_claim_or_citation(self):
        for value, eid in [(1, None), (None, 'E1')]:
            text=json.dumps(dict(value=value, unit='records', abstained=True, evidence_id=eid))
            self.assertTrue(self.contract.check(text, self.ledger.entries)[1])
        self.assertEqual(self.contract.check(self.contract.abstention(), {})[1], [])

    def test_citation_requires_matching_document_page_and_exact_substring(self):
        quote='Early mobilisation should occur following individual clinical assessment.'
        self.ledger.add('search_clinical_guideline', {'ok': True, 'references': [dict(document='original.pdf', page=4, content=quote)]})
        contract=AnswerContract(unit='records', require_citation=True)
        citation=dict(document='original.pdf', page=4, quote=quote)
        self.assertEqual(contract.check(answer(citation=citation), self.ledger.entries)[1], [])
        for bad in [dict(citation, page=5), dict(citation, quote='Fabricated text that was never returned by the retrieval tool.'),
                    dict(citation, quote=quote*4), dict(citation, page=True)]:
            self.assertTrue(contract.check(answer(citation=bad), self.ledger.entries)[1])

    def test_bounded_repair_works_with_both_provider_protocols(self):
        for provider, response, args in [('openai', openai_response, '{}'), ('anthropic', anthropic_response, {})]:
            client=Client([response(calls=[(1, 'query_patient_data', args)]), response(answer(999)), response(answer())])
            agent=HipFractureAgent(provider, client=client, dispatch=lambda *a: json.dumps(self.ledger.entries['E1']['result']))
            self.assertEqual(json.loads(agent.chat('count', answer_contract=self.contract))['value'],12)
            self.assertEqual(agent.last_run['answer_repairs'],1)
            self.assertTrue(agent.last_run['answer_validated'])
            self.assertNotIn('999', json.dumps(agent.trace))
            self.assertIn('value_does_not_match_evidence', json.dumps(agent.trace))

    def test_exhausted_repairs_withhold_unsupported_answer(self):
        client=Client([openai_response(answer(999))]*3)
        agent=HipFractureAgent('openai', client=client)
        result=json.loads(agent.chat('count', answer_contract=self.contract))
        self.assertTrue(result['abstained'])
        self.assertEqual(agent.last_run['status'], 'answer_rejected')
        self.assertEqual(len(client.requests),3)
        self.assertFalse(agent.last_run['answer_validated'])

    def test_repairs_share_global_step_budget_and_provider_failure_rolls_back(self):
        client=Client([openai_response(answer(999))])
        agent=HipFractureAgent(config=AgentConfig(provider='openai',max_steps=1), client=client)
        self.assertTrue(json.loads(agent.chat('count',answer_contract=self.contract))['abstained'])
        client=Client([openai_response(calls=[(1,'query_patient_data','{}')]), openai_response(answer(999)), RuntimeError('secret')])
        agent=HipFractureAgent('openai',client=client,dispatch=lambda *a:json.dumps(self.ledger.entries['E1']['result']))
        with self.assertRaises(RuntimeError):agent.chat('count',answer_contract=self.contract)
        self.assertEqual(agent.history,[])
        self.assertEqual(agent.evidence.entries,{})

    def test_legacy_projection_keeps_grounding_check_before_removing_id(self):
        contract=AnswerContract(unit='records',export_evidence=False)
        validated,errors=contract.check(answer(),self.ledger.entries)
        self.assertFalse(errors)
        self.assertEqual(set(json.loads(contract.render(validated))),{'value','unit','abstained'})

    def test_validation_feedback_does_not_echo_user_secrets(self):
        result=json.loads(_call_tool('predict_walking_recovery',{'patient':{'age':'PRIVATE_SECRET','PRIVATE_FIELD':1}}))
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(result['error']['code'],'invalid_arguments')
        self.assertIn('patient.age',str(result['error']['issues']))
        count=json.loads(_call_tool('query_patient_data',{'question':'count','metric':'count','event':{'column':'age','value':80}}))
        self.assertIn('omit event',count['error']['message'])

    def test_expired_and_cross_session_evidence_is_rejected(self):
        self.assertIn('unknown_evidence_id',self.contract.check(answer(),{})[1])
        ledger=EvidenceLedger(capacity=2)
        for n in range(3):ledger.add('query_patient_data',{'ok':True,'data':{'value':12,'unit':'records'}})
        self.assertIn('unknown_evidence_id',self.contract.check(answer(),ledger.entries)[1])

    def test_runtime_json_abstention_is_not_credited_to_model(self):
        from types import SimpleNamespace
        from eval_tasks import build_tasks, grade, FaultDispatch
        task=next(t for t in build_tasks() if t['id']=='permanent_failure-00')
        fault=FaultDispatch(lambda *a:'{}','unavailable')
        fault('query_patient_data',task['plans'][0])
        agent=SimpleNamespace(evidence=self.ledger,last_run={'status':'no_evidence'},trace=[])
        result=grade(task,AnswerContract(unit='numeric').abstention(),None,task['plans'],agent,[],fault)
        self.assertTrue(result['task_success'])
        self.assertTrue(result['runtime_abstained'])
        self.assertFalse(result['model_abstained'])
