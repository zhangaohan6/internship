"""Validate structured analytical answers against tools, never benchmark labels.

This checks provenance, not whether the model chose the right cohort or whether a
guideline entails a clinical claim. Those remain separate evaluation dimensions.
"""
from dataclasses import dataclass
import json
import math
import re

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, ValidationError


class Citation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    document: str = Field(min_length=1, max_length=240)
    page: StrictInt = Field(ge=1)
    quote: str = Field(min_length=40, max_length=220)


class AnalyticalAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    value: StrictInt | StrictFloat | None
    unit: str = Field(min_length=1, max_length=64)
    abstained: StrictBool
    evidence_id: str | None = Field(pattern=r'^E[1-9][0-9]*$')
    citation: Citation | None = None


def scalar(payload):
    data = payload.get('data', {})
    if 'risk_probability' in data:
        return data['risk_probability'], 'fraction'
    unit = data.get('unit')
    if unit is None:
        unit = 'years' if data.get('column') == 'age' else 'score:' + str(data.get('column'))
    return data.get('value'), unit


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def normalise(text):
    return re.sub(r'\s+', ' ', text).strip()


@dataclass(frozen=True)
class AnswerContract:
    unit: str | None = None
    require_citation: bool = False
    export_evidence: bool = True

    def __post_init__(self):
        if self.unit is not None and (not isinstance(self.unit, str) or not 1 <= len(self.unit) <= 64):
            raise ValueError('Invalid output unit')

    def instruction(self):
        fields = 'value, unit, abstained, evidence_id' + (', citation' if self.require_citation else '')
        unit = f'Use unit {json.dumps(self.unit)}.' if self.unit else 'Use the unit of the selected evidence.'
        return ('\nApplication output contract: return one raw JSON object with exactly ' + fields + '. '
                'Use a finite numeric value and the actual evidence_id of its tool result; never calculate or invent a value. '
                'For missing evidence set value=null, abstained=true, evidence_id=null. Otherwise abstained=false. '
                + unit + ' Keep at least 4 decimal places for non-integers. '
                + ('citation is {document, page, quote}, with a 40–220 character exact excerpt from a returned original passage; '
                   'use citation=null when abstaining. ' if self.require_citation else 'Do not include citation. ')
                + 'The application checks this contract before displaying the answer.')

    def check(self, text, entries):
        """Return (validated object, safe error codes); never return oracle values."""
        try:
            raw = json.loads(text)
            result = AnalyticalAnswer.model_validate(raw)
        except (ValueError, TypeError, ValidationError):
            return None, ['invalid_answer_schema']
        keys = {'value', 'unit', 'abstained', 'evidence_id'} | ({'citation'} if self.require_citation else set())
        errors = []
        if set(raw) != keys:
            errors.append('unexpected_or_missing_fields')
        if self.unit is not None and result.unit != self.unit:
            errors.append('wrong_requested_unit')
        if result.abstained:
            if result.value is not None or result.evidence_id is not None or result.citation is not None:
                errors.append('abstention_must_not_contain_claims')
        else:
            entry = entries.get(result.evidence_id, {})
            payload = entry.get('result', {})
            expected, unit = scalar(payload)
            if not entry or payload.get('ok') is not True:
                errors.append('unknown_evidence_id')
            elif not finite(result.value) or not finite(expected) or abs(result.value - expected) > 0.0001:
                errors.append('value_does_not_match_evidence')
            # "numeric" is the legacy statistics API representation of a measured scalar.
            numeric_legacy = (result.unit == 'numeric' and entry.get('tool') == 'query_patient_data'
                              and payload.get('data', {}).get('metric') in ('mean', 'median'))
            if entry and result.unit != unit and not numeric_legacy:
                errors.append('unit_does_not_match_evidence')
            if self.require_citation:
                citation = result.citation
                refs = [r for e in entries.values() if e.get('tool') == 'search_clinical_guideline'
                        for r in e.get('result', {}).get('references', [])]
                if citation is None or not any(
                        citation.document == r.get('document') and citation.page == r.get('page')
                        and normalise(citation.quote) in normalise(r.get('content', '')) for r in refs):
                    errors.append('citation_not_in_retrieved_passage')
        return (raw if not errors else None), errors

    def render(self, result):
        public = dict(result)
        if not self.export_evidence:
            public.pop('evidence_id', None)
        return json.dumps(public, ensure_ascii=False, allow_nan=False)

    def abstention(self):
        result = dict(value=None, unit=self.unit or 'numeric', abstained=True, evidence_id=None)
        if self.require_citation:
            result['citation'] = None
        return self.render(result)
