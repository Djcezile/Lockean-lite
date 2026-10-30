"""Finite retrospective synthetic mark differences, never fills or future returns."""
from decimal import Decimal,localcontext,ROUND_HALF_EVEN,Context
from .contracts import Costs,Experiment
from .validation import validate_observations
from .reporting import digest,plain


def input_digest(rows):return digest(rows)


def evaluate(spec,rows,costs=None,*,approved_input_digest=None):
    if type(spec) is not Experiment:raise ValueError('experiment_type')
    if set(spec.parameters)-{'nested','threshold'}:raise ValueError('unsupported_configuration')
    if 'threshold' in spec.parameters and spec.parameters['threshold']!=Decimal('1'):raise ValueError('frozen_threshold')
    if costs is not None and type(costs) is not Costs:raise ValueError('cost_type')
    validate_observations(rows,spec.decision_at)
    actual=input_digest(rows)
    if type(approved_input_digest) is not str or approved_input_digest!=actual:raise ValueError('input_integrity')
    with localcontext(Context(prec=80,rounding=ROUND_HALF_EVEN)) as ctx:
        ctx.prec=80;ctx.rounding=ROUND_HALF_EVEN
        gross=rows[-1].price-rows[0].price
        selected=gross>=Decimal('1')
        cost=sum((costs.commission,costs.spread,costs.slippage),Decimal(0)) if costs else None
        candidate={'candidate':'synthetic_mark_up','decision':'TRADE_PROXY' if selected else 'NO_TRADE',
                   'reason':'fixed_mark_difference' if selected else 'threshold_not_met',
                   'gross':gross if selected else Decimal(0),'cost':cost if selected else Decimal(0),
                   'net':gross-cost if selected and cost is not None else None if selected else Decimal(0)}
        baseline={'candidate':'always_no_trade','decision':'NO_TRADE','reason':'comparator',
                  'gross':Decimal(0),'cost':Decimal(0),'net':Decimal(0)}
        result={'schema':'lite.research.m0.v1','specification':plain(spec),'input_sha256':actual,
                'inputs':plain(rows),'cost_assumptions':plain(costs),'evidence_kind':'SYNTHETIC_ONLY',
                'measurement':'SYNTHETIC_MARK_TO_MARK_NOT_EXECUTABLE_PNL','decisions':[candidate,baseline],
                'cost_status':'KNOWN_SYNTHETIC_ASSUMPTIONS' if costs else 'UNKNOWN',
                'options_profit_qualification':'UNKNOWN','options_missing_evidence':['option_chain','executable_quotes','fills'],
                'limitations':['RETROSPECTIVE_SYNTHETIC_DIAGNOSTIC','NO_PREDICTIVE_OR_OPTIONS_PROFITABILITY','NO_DEPLOYMENT_AUTHORITY']}
        return plain(result)
