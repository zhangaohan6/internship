import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import pandas as pd
from pydantic import ValidationError
from statistics_query import execute_statistics
from tool_contracts import PatientFeatures, StatisticsArguments
import rag_pipeline


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.df=pd.DataFrame({'age':[70,80,90,100,60,50],'asa':[4,4,3,3,4,2],
                              'sex':[1,2,1,2,2,1],'mort30d':[2,1,1,1,None,2]})
    def test_asa_subgroup_not_overall(self):
        r=execute_statistics(self.df,{'question':'ASA IV mortality','metric':'proportion','filters':[{'column':'asa','value':4}], 'event':{'column':'mort30d','value':2}})['data']
        self.assertEqual((r['numerator'],r['denominator'],r['cohort_size']),(1,2,3))
        self.assertEqual(r['value'],.5)
    def test_legacy_asa_question_preserves_filter(self):
        self.assertEqual(execute_statistics(self.df,{'question':'What is the 30-day mortality rate for ASA IV patients?'})['data']['value'],.5)
    def test_ambiguous_legacy_subgroup_does_not_return_global(self):
        with self.assertRaises(ValueError): execute_statistics(self.df,{'question':'30-day mortality for female patients'})
    def test_combined_filters(self):
        r=execute_statistics(self.df,{'question':'count','metric':'count','filters':[{'column':'age','op':'ge','value':80},{'column':'sex','value':2}]})
        self.assertEqual(r['data']['value'],2)
    def test_missing_values_are_not_in_proportion_denominator(self):
        r=execute_statistics(self.df,{'question':'rate','metric':'proportion','event':{'column':'mort30d','value':2}})['data']
        self.assertEqual((r['value'],r['denominator'],r['missing_count']),(.4,5,1))
    def test_empty_cohort_reports_no_data(self):
        r=execute_statistics(self.df,{'question':'mean','metric':'mean','column':'age','filters':[{'column':'age','op':'gt','value':120}]})
        self.assertFalse(r['ok']); self.assertIsNone(r['data']['value'])
    def test_distribution_and_median(self):
        self.assertEqual(execute_statistics(self.df,{'question':'median','metric':'median','column':'age'})['data']['value'],75)
        self.assertEqual(execute_statistics(self.df,{'question':'dist','metric':'distribution','column':'asa'})['data']['value'],{'2':1,'3':2,'4':3})
    def test_unknown_columns_and_boolean_codes_rejected(self):
        for args in [{'question':'x','metric':'mean','column':'patient_name'},
                     {'question':'x','metric':'count','filters':[{'column':'sex','value':True}]}]:
            with self.assertRaises(ValidationError): StatisticsArguments.model_validate(args)
    def test_list_operator_and_nonfinite_values_rejected(self):
        for rule in [{'column':'asa','op':'eq','value':[3,4]}, {'column':'age','op':'eq','value':float('nan')}]:
            with self.assertRaises(ValidationError): StatisticsArguments(question='x',metric='count',filters=[rule])
    def test_invalid_patient_fields_rejected(self):
        for features in [{'age':200},{'age':80,'asa':6},{'age':80,'frailty':0},{'age':80,'secret':'x'},{}]:
            with self.assertRaises(ValidationError):PatientFeatures.model_validate(features)


class RetrievalTests(unittest.TestCase):
    def setUp(self): rag_pipeline._load_chunks.cache_clear()
    def test_only_explicit_source_directory_is_read_and_cited(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'allowed').mkdir()
            (root/'allowed'/'guideline-2023.pdf').write_bytes(b'fixture')
            (root/'unrelated-private.pdf').write_bytes(b'not a source')
            fake=NS(pages=[NS(extract_text=lambda:'Early mobilisation and rehabilitation assessment. '*30)])
            with patch.dict('os.environ',{'HIP_GUIDELINES_DIR':str(root/'allowed'),'HIP_RAG_MODE':'lexical'}),patch('pypdf.PdfReader',return_value=fake) as reader:
                r=rag_pipeline.search_guidelines('mobilisation',k=2)
                self.assertEqual(reader.call_count,1)
                self.assertTrue(all(x['page']==1 and x['document']=='guideline-2023.pdf' and len(x['sha256'])==64 for x in r))
    def test_missing_pdf_never_uses_invented_summary(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{'HIP_GUIDELINES_DIR':directory}):
            with self.assertRaises(FileNotFoundError): rag_pipeline.search_guidelines('surgery')
    def test_no_lexical_match_returns_no_evidence(self):
        chunk={'id':'a','content':'rehabilitation','superseded':False}
        with patch.object(rag_pipeline,'_sources',return_value=()),patch.object(rag_pipeline,'_load_chunks',return_value=[chunk]),patch.dict('os.environ',{'HIP_RAG_MODE':'lexical'}):
            self.assertEqual(rag_pipeline.search_guidelines('unrelatedxyz'),[])
    def test_hybrid_combines_rankings(self):
        chunks=[{'id':'a','content':'surgery surgery','superseded':False},{'id':'b','content':'surgery recovery','superseded':False}]
        with patch.object(rag_pipeline,'_sources',return_value=()),patch.object(rag_pipeline,'_load_chunks',return_value=chunks),patch.object(rag_pipeline,'_semantic_rank',return_value=[1,0]),patch.dict('os.environ',{'HIP_RAG_MODE':'hybrid'}):
            r=rag_pipeline.search_guidelines('surgery',k=2)
            self.assertEqual(len(r),2);self.assertEqual(r[0]['retrieval_mode'],'hybrid_rrf')
    def test_superseded_sources_are_opt_in(self):
        chunks=[{'id':'a','content':'surgery recovery','superseded':True}]
        with patch.object(rag_pipeline,'_sources',return_value=()),patch.object(rag_pipeline,'_load_chunks',return_value=chunks),patch.dict('os.environ',{'HIP_RAG_MODE':'lexical'}):
            self.assertEqual(rag_pipeline.search_guidelines('surgery'),[])
            self.assertEqual(len(rag_pipeline.search_guidelines('2016 surgery')),1)
