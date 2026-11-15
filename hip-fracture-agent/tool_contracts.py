"""Validated, provider-independent contracts for the five read-only agent tools."""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

Column = Literal['age', 'sex', 'asa', 'frailty', 'walk', 'cogstat', 'ftype',
                 'ptype', 'uresidence', 'mort30d', 'mort365d', 'fwalk2',
                 'delay', 'gerimed', 'wdest', 'anaesth', 'analges']
Number = StrictInt | StrictFloat


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class CohortFilter(Contract):
    column: Column
    op: Literal['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'in'] = 'eq'
    value: Number | list[Number]

    @model_validator(mode='after')
    def check_value(self):
        if self.op == 'in':
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 20:
                raise ValueError('in requires a list of 1 to 20 numeric codes')
        elif isinstance(self.value, list):
            raise ValueError('comparison requires one numeric value')
        return self


class StatisticsArguments(Contract):
    question: str = Field(min_length=1, max_length=2000)
    metric: Literal['count', 'proportion', 'mean', 'median', 'distribution'] | None = None
    column: Column | None = None
    filters: list[CohortFilter] = Field(default_factory=list, max_length=8,
        description='ALL conditions restricting the cohort. For a conditional COUNT, put the condition here, not in event.')
    event: CohortFilter | None = Field(default=None,
        description='Only for metric=proportion. For count, omit event and add its condition to filters.')

    @model_validator(mode='after')
    def coherent_plan(self):
        if self.metric in ('mean', 'median', 'distribution') and self.column is None:
            raise ValueError('column is required for this metric')
        if self.metric == 'proportion' and self.event is None:
            raise ValueError('proportion requires an event; its valid observations form the denominator')
        if self.metric != 'proportion' and self.event is not None:
            raise ValueError('event is only valid for proportion')
        return self


class PatientFeatures(Contract):
    age: Number = Field(ge=0, le=120)
    sex: StrictInt | None = Field(default=None, ge=1, le=3, description='1 male; 2 female. Omit if not supplied; use any other code only if explicitly provided.')
    asa: StrictInt | None = Field(default=None, ge=1, le=5, description='ASA I=1, II=2, III=3, IV=4, V=5. Omit if not supplied.')
    frailty: StrictInt | None = Field(default=None, ge=1, le=9)
    walk: StrictInt | None = Field(default=None, ge=1, le=4,
        description='Pre-admission mobility: 1 without aids; 2 walking stick; 3 walking frame; 4 wheelchair. Omit if not supplied.')
    cogstat: StrictInt | None = Field(default=None, ge=1, le=2)
    ftype: StrictInt | None = Field(default=None, ge=1, le=4)
    ptype: StrictInt | None = Field(default=None, ge=1, le=2)
    uresidence: StrictInt | None = Field(default=None, ge=1, le=3)
    analges: StrictInt | None = Field(default=None, ge=1, le=4)


class PredictionArguments(Contract):
    patient: PatientFeatures

    @model_validator(mode='before')
    @classmethod
    def legacy_json(cls, value):
        # Compatibility for existing callers; new model-facing schemas use an object.
        if isinstance(value, dict) and set(value) == {'patient_json'}:
            return {'patient': json.loads(value['patient_json'])}
        return value


class GuidelineArguments(Contract):
    query: str = Field(min_length=2, max_length=2000)


class ComparisonArguments(Contract):
    left_id: str = Field(pattern=r'^E[1-9][0-9]*$')
    right_id: str = Field(pattern=r'^E[1-9][0-9]*$')
    operation: Literal['difference', 'ratio', 'relative_change']


CONTRACTS = {
    'compare_evidence': ComparisonArguments,
    'query_patient_data': StatisticsArguments,
    'predict_walking_recovery': PredictionArguments,
    'predict_rehab_access': PredictionArguments,
    'search_clinical_guideline': GuidelineArguments,
}
DESCRIPTIONS = {
    'compare_evidence': 'Compute a comparison from evidence IDs already returned by tools. First obtain both source results. difference = left-right; ratio = left/right; relative_change = (left-right)/right. Matching units/outcomes required; zero denominator rejected. Never invent evidence IDs or supply guessed numbers.',
    'query_patient_data': (
        'Read-only aggregate query over LOCAL SYNTHETIC Datathon data. Always supply a structured '
        'metric and all cohort filters. For a COUNT with conditions use filters and OMIT event. '
        'For a proportion, event describes the numerator and its '
        'column defines the non-missing denominator. Example ASA IV 30-day mortality: metric '
        'proportion, filters [{column:asa,op:eq,value:4}], event {column:mort30d,op:eq,value:2}. '
        'Codes: sex 1 male/2 female; mortality 1 alive/2 deceased; fwalk2 1 recovered/2 not; '
        'gerimed 0 no/1 yes/8 no service/9 unknown; wdest 3 public rehab/4 private rehab. '
        'For age 80+ proportion, event={column:age,op:ge,value:80}. No raw rows or executable code.'
    ),
    'predict_walking_recovery': 'Research-only 120-day walking recovery model. Supply known patient features only; never invent missing features. Trained on synthetic data, not clinically validated.',
    'predict_rehab_access': 'Research-only rehabilitation discharge model. Supply known patient features only. Missing fields are imputed; trained on synthetic data, not clinically validated.',
    'search_clinical_guideline': 'Retrieve original local guideline PDF passages with filename, page and source hash. If no original evidence is available, ask for the document; do not invent a guideline.',
}
ANTHROPIC_TOOLS = [dict(name=name, description=DESCRIPTIONS[name], input_schema=model.model_json_schema())
                   for name, model in CONTRACTS.items()]
OPENAI_TOOLS = [dict(type='function', function=dict(name=t['name'], description=t['description'],
                                                 parameters=t['input_schema'])) for t in ANTHROPIC_TOOLS]
