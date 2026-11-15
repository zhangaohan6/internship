import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from agent import HipFractureAgent, AgentConfig, _call_tool


def openai_response(text=None, calls=()):
    return NS(choices=[NS(message=NS(content=text, tool_calls=[NS(id=str(i), function=NS(name=n, arguments=a)) for i,n,a in calls]))], usage=NS(total_tokens=5))


class Block:
    def __init__(self, **values): self.values = values
    def model_dump(self, **kwargs): return self.values


def anthropic_response(text=None, calls=()):
    content = [Block(type='tool_use', id=str(i), name=n, input=a) for i,n,a in calls]
    if text is not None: content.append(Block(type='text', text=text))
    return NS(content=content, usage=NS(input_tokens=3, output_tokens=2))


class Client:
    def __init__(self, responses):
        self.responses, self.requests = iter(responses), []
        self.chat = NS(completions=NS(create=self.create))
        self.messages = NS(create=self.create)
    def create(self, **kwargs):
        self.requests.append(kwargs)
        result = next(self.responses)
        if isinstance(result, Exception): raise result
        return result


OK = json.dumps({'ok': True, 'data': {'value': 4}})


class RuntimeTests(unittest.TestCase):
    def test_malformed_json_can_recover(self):
        client = Client([openai_response(calls=[(1,'query_patient_data','{')]),
                         openai_response(calls=[(2,'query_patient_data','{"question":"count","metric":"count"}')]),
                         openai_response('4 records')])
        calls = []
        agent = HipFractureAgent('openai', client=client, dispatch=lambda *a: calls.append(a) or OK)
        self.assertEqual(agent.chat('count'), '4 records')
        self.assertEqual(len(calls), 1)
        self.assertEqual([t['status'] for t in agent.trace if t['kind']=='tool'], ['error','ok'])
        self.assertEqual(len(agent.history), 6)

    def test_complete_tool_history_is_carried_to_next_turn(self):
        client = Client([openai_response(calls=[(1,'query_patient_data','{}')]), openai_response('4'), openai_response('previous result')])
        agent = HipFractureAgent('openai', client=client, dispatch=lambda *a: OK)
        agent.chat('count'); agent.chat('explain that')
        self.assertTrue(any(m['role']=='tool' for m in client.requests[-1]['messages']))

    def test_anthropic_protocol_and_evidence_persist(self):
        client = Client([anthropic_response(calls=[(1,'query_patient_data',{})]), anthropic_response('4'), anthropic_response('next')])
        agent = HipFractureAgent(client=client, dispatch=lambda *a: OK)
        agent.chat('count'); agent.chat('follow up')
        contents = client.requests[-1]['messages'][2]['content']
        self.assertEqual(contents[0]['type'], 'tool_result')
        self.assertFalse(contents[0]['is_error'])

    def test_all_tools_failed_cannot_be_reported_as_success(self):
        client = Client([openai_response(calls=[(1,'search_clinical_guideline','{}')]), openai_response('invented guideline')])
        agent = HipFractureAgent('openai', client=client, dispatch=lambda *a: json.dumps({'ok':False,'error':{'code':'no_evidence'}}))
        self.assertNotIn('invented guideline', agent.chat('guideline'))
        self.assertEqual(agent.last_run['status'], 'no_evidence')

    def test_provider_failure_rolls_back_and_redacts(self):
        client = Client([openai_response('hello'), RuntimeError('secret-key-user-value')])
        agent = HipFractureAgent('openai', client=client)
        agent.chat('hi'); before = list(agent.history)
        with self.assertRaisesRegex(RuntimeError, 'this turn was not saved') as raised:
            agent.chat('second')
        self.assertNotIn('secret-key', str(raised.exception))
        self.assertEqual(agent.history, before)

    def test_duplicate_success_is_cached_within_turn_only(self):
        response = openai_response(calls=[(1,'query_patient_data','{}'),(2,'query_patient_data','{}')])
        client = Client([response,openai_response('4'),response,openai_response('4')])
        calls=[]
        agent = HipFractureAgent('openai', client=client, dispatch=lambda *a: calls.append(a) or OK)
        agent.chat('count'); self.assertEqual(len(calls),1)
        self.assertTrue(agent.trace[2]['cached'])
        agent.chat('again'); self.assertEqual(len(calls),2)

    def test_budget_closes_every_tool_call_without_executing_excess(self):
        client=Client([openai_response(calls=[(1,'query_patient_data','{}'),(2,'query_patient_data','{}')])])
        calls=[]
        agent=HipFractureAgent(config=AgentConfig(provider='openai',max_tool_calls=1),client=client,dispatch=lambda *a:calls.append(a) or OK)
        agent.chat('count')
        self.assertEqual(len(calls),1)
        self.assertEqual(sum(m['role']=='tool' for m in agent.history),2)
        self.assertEqual(agent.last_run['status'],'budget_exhausted')

    def test_history_eviction_does_not_leave_orphan_results(self):
        client=Client([openai_response('one'),openai_response('two')])
        agent=HipFractureAgent(config=AgentConfig(provider='openai',max_history_turns=1),client=client)
        agent.chat('first');agent.chat('second')
        self.assertEqual(agent.history,[{'role':'user','content':'second'},{'role':'assistant','content':'two'}])

    def test_trace_contains_no_prompt_arguments_or_results(self):
        client=Client([openai_response(calls=[(1,'query_patient_data','{"question":"PRIVATE_MARKER"}')]),openai_response('answer')])
        agent=HipFractureAgent('openai',client=client,dispatch=lambda *a:OK)
        agent.chat('PRIVATE_MARKER')
        self.assertNotIn('PRIVATE_MARKER',json.dumps(agent.trace))
        self.assertNotIn('value',json.dumps(agent.trace))

    def test_unknown_tool_and_bad_prediction_are_rejected(self):
        self.assertEqual(json.loads(_call_tool('shell',{'command':'ls'}))['error']['code'],'unknown_tool')
        self.assertEqual(json.loads(_call_tool('predict_rehab_access',{'patient':{'age':-2}}))['error']['code'],'invalid_arguments')

    def test_output_budget_fails_instead_of_truncating_evidence(self):
        client=Client([openai_response(calls=[(1,'query_patient_data','{}')]),openai_response('made up')])
        agent=HipFractureAgent(config=AgentConfig(provider='openai',max_output_chars=256),client=client,dispatch=lambda *a: 'x'*300)
        agent.chat('count')
        self.assertEqual(agent.trace[1]['error_code'],'tool_output_too_large')

    def test_provider_config_is_per_instance(self):
        with patch('openai.OpenAI') as constructor:
            a=HipFractureAgent(config=AgentConfig(provider='openai',base_url='http://localhost:9999',timeout=7,max_retries=1),api_key='session-key')
            a._get_client()
            constructor.assert_called_once_with(api_key='session-key',base_url='http://localhost:9999',timeout=7,max_retries=1)

    def test_config_and_empty_messages_rejected(self):
        with self.assertRaises(ValueError): AgentConfig(provider='unknown')
        with self.assertRaises(ValueError): AgentConfig(max_steps=0)
        with self.assertRaises(ValueError): HipFractureAgent().chat(' ')
