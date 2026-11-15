"""Deterministic aggregate execution; no generated SQL/Python and no patient rows."""
import re
import pandas as pd
from tool_contracts import CohortFilter, StatisticsArguments


def mask(series, rule):
    numeric = pd.to_numeric(series, errors='coerce')
    operation = {'eq': numeric.eq, 'ne': numeric.ne, 'gt': numeric.gt,
                 'ge': numeric.ge, 'lt': numeric.lt, 'le': numeric.le, 'in': numeric.isin}[rule.op]
    return numeric.notna() & operation(rule.value)


def legacy_plan(question):
    """Compatibility for a small explicit set; ambiguous requests need a plan."""
    q = question.lower().strip(' ?.\n')
    # Do not silently interpret arbitrary subgroup questions as overall statistics.
    asa_match = re.search(r'asa\s*(?:grade\s*)?(iv|iii|ii|v|i|[1-5])\b', q)
    filters = []
    if asa_match:
        code = asa_match[1]
        grade = int(code) if code.isdigit() else {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5}[code]
        filters.append(dict(column='asa', op='eq', value=grade))
    if re.search(r'(30.day mortality|died within 30|30 day death)', q):
        # Other cohort qualifiers are deliberately rejected by this compatibility path.
        if re.search(r'female|male|aged|older|younger|frail|rehab|residen', q):
            raise ValueError('Supply explicit metric, filters and event for this cohort question')
        return StatisticsArguments(question=question, metric='proportion', filters=filters,
                                   event=dict(column='mort30d', op='eq', value=2))
    if q in ('what is the median age of patients', 'what is the median age of hip fracture patients in the registry'):
        return StatisticsArguments(question=question, metric='median', column='age')
    if q in ('how many total patients are in the anzhfr dataset', 'total patients', 'how many patients are in the dataset'):
        return StatisticsArguments(question=question, metric='count')
    raise ValueError('Provide a structured metric and cohort filters; a general summary cannot answer this question')


def execute_statistics(df, arguments):
    plan = StatisticsArguments.model_validate(arguments)
    if plan.metric is None:
        if plan.filters or plan.column or plan.event:
            raise ValueError('Explicit filters require an explicit metric')
        plan = legacy_plan(plan.question)
    cohort = df
    required = {r.column for r in plan.filters}
    if plan.column:
        required.add(plan.column)
    if plan.event:
        required.add(plan.event.column)
    if not required.issubset(df.columns):
        raise ValueError('A requested field is absent from the configured dataset')
    for rule in plan.filters:
        cohort = cohort.loc[mask(cohort[rule.column], rule)]
    data = dict(metric=plan.metric, cohort_size=len(cohort),
                filters=[r.model_dump() for r in plan.filters])
    if plan.metric == 'count':
        data.update(value=len(cohort), unit='records')
    elif plan.metric == 'proportion':
        values = pd.to_numeric(cohort[plan.event.column], errors='coerce')
        valid = values.notna()
        numerator, denominator = int(mask(values, plan.event).sum()), int(valid.sum())
        data.update(event=plan.event.model_dump(), numerator=numerator, denominator=denominator,
                    value=numerator / denominator if denominator else None, unit='fraction',
                    missing_count=int((~valid).sum()))
    else:
        values = pd.to_numeric(cohort[plan.column], errors='coerce').dropna()
        data.update(column=plan.column, denominator=len(values), missing_count=len(cohort)-len(values))
        if plan.metric == 'distribution':
            data['value'] = {str(k): int(v) for k, v in values.value_counts().sort_index().items()}
        else:
            data['value'] = float(getattr(values, plan.metric)()) if len(values) else None
    if data['value'] is None or data['value'] == {}:
        return dict(ok=False, error=dict(code='no_data', message='No valid observations for this cohort; do not estimate a value'), data=data)
    return dict(ok=True, source='ANZHFR Datathon synthetic dataset (local)', data=data,
                limitation='Descriptive research statistics; not estimates for real clinical populations.')
