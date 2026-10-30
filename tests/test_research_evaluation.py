from datetime import datetime,timezone,timedelta
from decimal import Decimal,localcontext
import json
import pytest
from lockean_lite.research.contracts import Experiment,Observation,Costs
from lockean_lite.research.evaluation import evaluate as kernel_evaluate, input_digest

def evaluate(spec,rows,costs=None):
    return kernel_evaluate(spec,rows,costs,approved_input_digest=input_digest(rows))
from lockean_lite.research.reporting import canonical,digest

T=datetime(2026,6,1,14,tzinfo=timezone.utc)
def inputs():
    return tuple(Observation(T-timedelta(minutes=2-i),T-timedelta(minutes=2-i),Decimal(p),'fixture','synthetic','sha256:'+'a'*64) for i,p in enumerate(('100','101')))
def spec():return Experiment('demo',T,{'nested':{'x':[1,2]}})

def test_reproducible_and_explicit_no_trade():
    a=evaluate(spec(),inputs());b=evaluate(spec(),inputs())
    assert canonical(a)==canonical(b) and digest(a)==digest(b)
    assert a['decisions'][1]['decision']=='NO_TRADE'
    assert a['options_profit_qualification']=='UNKNOWN'
    assert a['decisions'][0]['net'] is None
    assert json.loads(canonical(a))['evidence_kind']=='SYNTHETIC_ONLY'

def test_cost_reconciliation_is_hypothetical_not_profitability():
    a=evaluate(spec(),inputs(),Costs(Decimal('.1'),Decimal('.2'),Decimal('.3')))
    d=a['decisions'][0]
    assert Decimal(d['gross'])-Decimal(d['cost'])==Decimal(d['net'])
    assert a['options_profit_qualification']=='UNKNOWN'
    assert a['measurement']=='SYNTHETIC_MARK_TO_MARK_NOT_EXECUTABLE_PNL'

def test_decimal_context_does_not_change_result():
    a=canonical(evaluate(spec(),inputs(),Costs(Decimal('.1'),Decimal('.2'),Decimal('.3'))))
    with localcontext() as c:
        c.prec=3
        assert canonical(evaluate(spec(),inputs(),Costs(Decimal('.1'),Decimal('.2'),Decimal('.3'))))==a

@pytest.mark.parametrize('value',[Decimal('-1'),Decimal('NaN'),1.2])
def test_invalid_costs_fail(value):
    with pytest.raises(ValueError):Costs(value,Decimal('0'),Decimal('0'))

def test_empty_evidence_and_unsupported_configuration_fail():
    with pytest.raises(ValueError):evaluate(spec(),())
    with pytest.raises(ValueError):evaluate(Experiment('x',T,{'candidate':'tuned'}),inputs())


def test_integrity_pin_required_and_tampering_rejected():
    with pytest.raises(ValueError):kernel_evaluate(spec(),inputs())
    with pytest.raises(ValueError):kernel_evaluate(spec(),inputs(),approved_input_digest='0'*64)


def interval_inputs(start,end):
    """Generated marks only; never load protected historical observations."""
    return tuple(Observation(datetime.fromisoformat(t),datetime.fromisoformat(t),
                             Decimal(p),'fixture','synthetic','sha256:'+'a'*64)
                 for t,p in ((start,'100'),(end,'102')))


def test_evaluation_rejects_interval_enclosing_holdout_with_matching_digest():
    rows=interval_inputs('2026-10-19T14:00:00Z','2027-01-04T14:00:00Z')
    experiment=Experiment('protected-span',rows[-1].available_at,{})
    with pytest.raises(ValueError,match='^protected_holdout_overlap$'):
        kernel_evaluate(experiment,rows,approved_input_digest=input_digest(rows))


@pytest.mark.parametrize('start,end,allowed',[
    ('2026-10-18T14:00:00Z','2026-10-19T14:00:00Z',True),
    ('2027-01-04T14:00:00Z','2027-01-05T14:00:00Z',True),
    # UTC October 20 is still October 19 in New York before 04:00Z.
    ('2026-10-19T23:00:00Z','2026-10-20T03:59:59Z',True),
    ('2027-01-01T05:00:00Z','2027-01-01T06:00:00Z',True),
    ('2026-10-20T03:59:59Z','2026-10-20T04:00:00Z',False),
    ('2026-12-31T23:00:00Z','2027-01-01T05:00:00Z',False),
    # UTC January 1 remains protected December 31 in New York before 05:00Z.
    ('2027-01-01T04:00:00Z','2027-01-01T04:59:59Z',False),
])
def test_evaluation_interval_boundaries_use_new_york_dates(start,end,allowed):
    rows=interval_inputs(start,end)
    experiment=Experiment('interval-boundary',rows[-1].available_at,{})
    if not allowed:
        with pytest.raises(ValueError,match='^protected_holdout_overlap$'):
            kernel_evaluate(experiment,rows,approved_input_digest=input_digest(rows))
        return
    result=kernel_evaluate(experiment,rows,approved_input_digest=input_digest(rows))
    assert result['decisions'][0]['gross']=='2'
    assert result['decisions'][1]['decision']=='NO_TRADE'
    assert result['options_profit_qualification']=='UNKNOWN'
