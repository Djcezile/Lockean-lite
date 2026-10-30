"""Canonical UTF-8 JSON and result digests; no files or runtime metadata."""
from collections.abc import Mapping
from dataclasses import fields,is_dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json


def plain(value):
    if is_dataclass(value):return {f.name:plain(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,Mapping):return {k:plain(v) for k,v in value.items()}
    if type(value) in (tuple,list):return [plain(v) for v in value]
    if type(value) is datetime:return value.isoformat().replace('+00:00','Z')
    if type(value) is Decimal:
        if not value.is_finite():raise ValueError('invalid_decimal')
        text=format(value,'f')
        return (text.rstrip('0').rstrip('.') if '.' in text else text) if value else '0'
    if type(value) in (str,int,bool,type(None)):return value
    raise ValueError('unsupported_serialization')


def canonical(value):
    return json.dumps(plain(value),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
