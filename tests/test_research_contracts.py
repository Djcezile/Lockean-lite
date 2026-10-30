from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from lockean_lite.research.contracts import Experiment, Observation

T = datetime(2026, 6, 1, 14, tzinfo=timezone.utc)

def test_nested_parameters_are_detached_and_immutable():
    params={'threshold':Decimal('1'), 'nested':{'values':[1,2]}}
    spec=Experiment('demo', T, params)
    params['nested']['values'].append(3)
    assert spec.parameters['nested']['values']==(1,2)
    with pytest.raises(TypeError):spec.parameters['nested']['x']=1
    with pytest.raises(FrozenInstanceError):spec.name='other'

@pytest.mark.parametrize('value',[float('nan'),1.2,object()])
def test_unsupported_parameters_rejected(value):
    with pytest.raises(ValueError):Experiment('demo',T,{'x':value})

def test_observation_is_frozen():
    row=Observation(T,T,Decimal('100'),'fixture','synthetic','sha256:'+'a'*64)
    with pytest.raises(FrozenInstanceError):row.price=Decimal('1')
