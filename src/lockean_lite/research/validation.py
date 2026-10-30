"""Chronology and protected-date checks, without loading protected observations."""
from datetime import datetime,date,timezone
import re
from zoneinfo import ZoneInfo
from .contracts import Observation,number

NY=ZoneInfo('America/New_York')
FIRST=date(2026,10,20)
LAST=date(2026,12,31)


def utc(value):
    if type(value) is not datetime or value.tzinfo is not timezone.utc or value.fold:
        raise ValueError('timestamp_requires_unambiguous_utc')
    return value


def validate_partition(start,end,purpose):
    if purpose not in ('development','validation'):raise ValueError('partition_purpose')
    def day(v):
        if type(v) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):raise ValueError('date_format')
        return date.fromisoformat(v)
    a,b=day(start),day(end)
    if a>b:raise ValueError('reversed_range')
    if a<=LAST and b>=FIRST:raise ValueError('protected_holdout_overlap')


def validate_observations(rows,decision):
    utc(decision)
    d=decision.astimezone(NY).date().isoformat();validate_partition(d,d,'development')
    if type(rows) is not tuple or len(rows)<2:raise ValueError('insufficient_evidence')
    previous=None;identity=None
    for row in rows:
        if type(row) is not Observation:raise ValueError('observation_type')
        event,available=utc(row.event_at),utc(row.available_at)
        if event>available or available>decision:raise ValueError('information_unavailable')
        day=event.astimezone(NY).date().isoformat();validate_partition(day,day,'development')
        arrival=available.astimezone(NY).date().isoformat();validate_partition(arrival,arrival,'development')
        if previous is not None and event<=previous:raise ValueError('unordered_or_duplicate')
        if number(row.price)<=0:raise ValueError('nonpositive_price')
        if row.provider!='fixture' or row.feed!='synthetic':raise ValueError('synthetic_source_required')
        if type(row.source_digest) is not str or not re.fullmatch('sha256:[0-9a-f]{64}',row.source_digest):raise ValueError('source_identity')
        current=(row.provider,row.feed,row.source_digest)
        if identity is not None and identity!=current:raise ValueError('mixed_source')
        identity=current;previous=event
