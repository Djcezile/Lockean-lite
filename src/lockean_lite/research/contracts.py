"""Immutable experiment inputs; only built-in containers and exact decimal numbers."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType


def number(value):
    if (type(value) is not Decimal or not value.is_finite()
            or value.adjusted()>18 or value.as_tuple().exponent < -12):
        raise ValueError('invalid_decimal')
    return value


def freeze(value):
    if type(value) is dict:
        if any(type(k) is not str for k in value):raise ValueError('parameter_key')
        return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if type(value) in (list,tuple):return tuple(freeze(v) for v in value)
    if type(value) is Decimal:return number(value)
    if type(value) in (str,int,bool,type(None)):return value
    raise ValueError('unsupported_parameter')


@dataclass(frozen=True)
class Experiment:
    name: str
    decision_at: datetime
    parameters: object

    def __post_init__(self):
        from .validation import utc
        utc(self.decision_at)
        if type(self.name) is not str or not self.name:raise ValueError('experiment_name')
        if type(self.parameters) is not dict:raise ValueError('parameter_mapping')
        object.__setattr__(self,'parameters',freeze(self.parameters))


@dataclass(frozen=True)
class Observation:
    event_at: datetime
    available_at: datetime
    price: Decimal
    provider: str
    feed: str
    source_digest: str


@dataclass(frozen=True)
class Costs:
    commission: Decimal
    spread: Decimal
    slippage: Decimal

    def __post_init__(self):
        for v in (self.commission,self.spread,self.slippage):
            if number(v)<0:raise ValueError('negative_cost')
