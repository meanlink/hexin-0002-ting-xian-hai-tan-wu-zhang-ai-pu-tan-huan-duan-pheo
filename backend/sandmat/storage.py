"""Segment topology, trial evidence and signed orders as typed relational rows."""

from datetime import datetime, timezone
from secrets import token_hex

from fastapi import HTTPException


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def new_code(prefix):
    return f'{prefix}-{token_hex(7).upper()}'


def locked_row(db, table, code):
    if table not in {'mat_orders', 'roll_trials'}:
        raise ValueError(table)
    row = db.one(f'SELECT * FROM {table} WHERE code = %s FOR UPDATE', (code,))
    if row is None:
        raise HTTPException(404, '找不到这条记录。')
    return row


def segment_map(db, lock=False):
    suffix = ' FOR UPDATE' if lock else ''
    rows = db.all(f'SELECT * FROM mat_segments ORDER BY code{suffix}')
    return {row['code']: row for row in rows}
