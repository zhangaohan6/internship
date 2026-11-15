import unittest
import pandas as pd
from eval_v2 import build_cases, canonical_plan, reference_value, score_answer, summarise, wilson


class EvaluationTests(unittest.TestCase):
    def test_manifest_has_144_unique_cases_in_12_families(self):
        cases=build_cases()
        self.assertEqual((len(cases),len({c['id'] for c in cases}),len({c['family'] for c in cases})),(144,144,12))
    def test_splits_do_not_share_query_families(self):
        cases=build_cases()
        dev={c['family'] for c in cases if c['split']=='dev'}
        holdout={c['family'] for c in cases if c['split']=='holdout'}
        self.assertFalse(dev&holdout)
        self.assertEqual(sum(c['split']=='dev' for c in cases),48)
    def test_no_expected_value_leaks_into_manifest(self):
        self.assertTrue(all('expected_value' not in c for c in build_cases()))
    def test_free_text_with_matching_number_does_not_pass(self):
        self.assertEqual(score_answer('The answer could be 0.2 or 0.9',.2,'fraction'),(False,False))
    def test_wrong_unit_and_boolean_number_do_not_pass(self):
        self.assertFalse(score_answer('{"value":0.2,"unit":"records","abstained":false}',.2,'fraction')[1])
        self.assertFalse(score_answer('{"value":true,"unit":"records","abstained":false}',1,'records')[1])
    def test_json_numeric_and_explicit_abstention(self):
        self.assertEqual(score_answer('{"value":0.2,"unit":"fraction","abstained":false}',.2,'fraction'),(True,True))
        self.assertEqual(score_answer('{"value":null,"unit":"numeric","abstained":true}',None,'numeric'),(True,True))
    def test_repeats_are_not_counted_as_independent_cases(self):
        rows=[{'id':'a','family':'f','answer_correct':True},{'id':'a','family':'f','answer_correct':False}]
        result=summarise(rows,'live')
        self.assertEqual((result['n_runs'],result['n_unique_cases']),(2,1))
        self.assertEqual(result['metrics']['answer_correct']['consistent_pass_cases'],0)
    def test_perfect_small_sample_does_not_imply_certainty(self):
        low,high=wilson(12,12)
        self.assertLess(low,.8);self.assertEqual(high,1)
    def test_independent_reference_applies_filters_and_missingness(self):
        case=next(c for c in build_cases() if c['id']=='mort30-03')
        df=pd.DataFrame({'asa':[4,4,4,3],'mort30d':[2,1,None,1]})
        self.assertEqual(reference_value(df,case),(.5,'fraction'))
    def test_filter_order_is_not_a_scoring_artifact(self):
        case=next(c for c in build_cases() if c['id']=='mort30-10')
        other=dict(case['plan']);other['filters']=list(reversed(other['filters']))
        self.assertEqual(canonical_plan(case['plan']),canonical_plan(other))

    def test_live_runner_contract_with_fake_transport_is_not_a_real_model_result(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from types import SimpleNamespace as NS
        from eval_v2 import run
        responses=iter([
            NS(choices=[NS(message=NS(content=None,tool_calls=[NS(id='1',function=NS(name='query_patient_data',arguments='{"question":"count","metric":"count"}'))]))],usage=NS(total_tokens=2)),
            NS(choices=[NS(message=NS(content='{"value":3,"unit":"records","abstained":false}',tool_calls=[]))],usage=NS(total_tokens=2))
        ])
        client=NS(chat=NS(completions=NS(create=lambda **kwargs:next(responses))))
        with tempfile.TemporaryDirectory() as directory, patch('agent.HipFractureAgent._get_client',return_value=client):
            path=Path(directory)/'fictional.csv'
            pd.DataFrame({'age':[70,80,90]}).to_csv(path,index=False)
            report=run('live','dev',1,1,'openai',str(path))
        self.assertEqual(report['summary']['n_unique_cases'],1)
        self.assertTrue(report['results'][0]['end_to_end_correct'])
        self.assertNotIn('agent_answer',report['results'][0])
