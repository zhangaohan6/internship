import os
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class DemoAgent:
    def __init__(self, **kwargs):
        self.trace=[{'kind':'tool','tool':'query_patient_data','status':'ok','duration_ms':1}]
        self.last_run={'status':'completed','tool_calls':1}
    def chat(self, message): return 'Synthetic fixture response.'


class UITests(unittest.TestCase):
    def test_chat_trace_and_provider_change_are_session_local(self):
        before={k:os.environ.get(k) for k in ('ANTHROPIC_API_KEY','OPENAI_API_KEY')}
        with patch('agent.HipFractureAgent',DemoAgent):
            app=AppTest.from_file('app.py').run(timeout=20)
            self.assertFalse(app.exception)
            app.text_input[0].set_value('test-placeholder-key').run(timeout=20)
            app.chat_input[0].set_value('A fictional fixture question').run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['messages'][-1]['content'],'Synthetic fixture response.')
            self.assertTrue(app.session_state['messages'][-1]['trace'])
            app.selectbox[0].select('openai').run(timeout=20)
            self.assertEqual(app.session_state['messages'],[])
        self.assertEqual({k:os.environ.get(k) for k in before},before)
