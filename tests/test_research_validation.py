from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from lockean_lite.research.contracts import Observation
from lockean_lite.research.validation import validate_observations, validate_partition, utc

T=datetime(2026,6,1,14,tzinfo=timezone.utc)
def row(**kw):
    fields=dict(event_at=T,available_at=T,price=Decimal('100'),provider='fixture',feed='synthetic',source_digest='sha256:'+'a'*64)
    fields.update(kw);return Observation(**fields)

@pytest.mark.parametrize('bad',[datetime(2026,6,1),T.astimezone(timezone(timedelta(hours=-4))),T.replace(fold=1),'bad'])
def test_timestamps_fail_explicitly(bad):
    with pytest.raises(ValueError):utc(bad)

@pytest.mark.parametrize('field',['event_at','available_at'])
def test_future_information_rejected(field):
    with pytest.raises(ValueError):validate_observations((row(event_at=T-timedelta(seconds=2),available_at=T-timedelta(seconds=2)),row(**{field:T+timedelta(seconds=1)})),T)

@pytest.mark.parametrize('kw',[{'provider':''},{'feed':'iex'},{'source_digest':'bad'},{'price':Decimal('NaN')},{'price':Decimal('-1')},{'available_at':T-timedelta(seconds=1)}])
def test_bad_provenance_or_prices_rejected(kw):
    with pytest.raises(ValueError):validate_observations((row(event_at=T-timedelta(seconds=2),available_at=T-timedelta(seconds=2)),row(**kw)),T)

@pytest.mark.parametrize('start,end',[('2026-10-20','2026-12-31'),('2026-01-01','2027-01-01'),('2026-12-31','2027-01-02')])
@pytest.mark.parametrize('purpose',['development','validation'])
def test_holdout_and_overlapping_ranges_rejected(start,end,purpose):
    with pytest.raises(ValueError):validate_partition(start,end,purpose)

def test_valid_partition_and_ordering():
    validate_partition('2026-06-01','2026-06-02','development')
    validate_observations((row(event_at=T-timedelta(seconds=1),available_at=T-timedelta(seconds=1)),row()),T)
    with pytest.raises(ValueError):validate_observations((row(),row()),T)
    with pytest.raises(ValueError):validate_partition('2026-06-02','2026-06-01','development')


def test_protected_observation_rejected_even_with_later_decision():
    protected=datetime(2026,11,2,14,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match='protected_holdout_overlap'):
        validate_observations((row(event_at=protected,available_at=protected),row(event_at=protected+timedelta(minutes=1),available_at=protected+timedelta(minutes=1))),datetime(2027,1,4,14,tzinfo=timezone.utc))
