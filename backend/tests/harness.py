"""Offline harness: drive the blind-test domain against in-memory SQLite.

The real stack runs MySQL + Redis + FastAPI. This fixture swaps only the
persistence seam (infra.db.tx / storage.new_code / queue.enqueue) so the same
sandmat.blind and sandmat.trials functions run unchanged under unittest.
"""

import json
import sqlite3
import unittest
from unittest import mock

from sandmat import blind, trials
from sandmat.classifier import predict
from sandmat.demo import SEGMENTS, TRAINING
from sandmat.states import TrialResult

DDL = [
    '''CREATE TABLE mat_segments (
        code TEXT PRIMARY KEY, label TEXT, from_node TEXT, to_node TEXT,
        length_m REAL, priority TEXT, state TEXT)''',
    '''CREATE TABLE roll_trials (
        code TEXT PRIMARY KEY, segment_code TEXT, observed_at TEXT,
        slope_pct REAL, moisture_pct REAL, rut_mm REAL,
        observed_result TEXT, predicted_result TEXT,
        clear_probability REAL, sample_count INTEGER,
        blind_batch_code TEXT, blind_sample_count INTEGER)''',
    '''CREATE TABLE blind_batches (
        code TEXT PRIMARY KEY, title TEXT, status TEXT, locked_at TEXT,
        locked_sample_count INTEGER, locked_snapshot TEXT, opened_by TEXT,
        revealed_at TEXT, trial_total INTEGER, false_clear_count INTEGER)''',
]


class Row(dict):
    """Attribute access over a dict row, matching pymysql DictCursor usage."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc


class SqliteSession:
    def __init__(self, conn):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    @staticmethod
    def _adapt(sql):
        # MySQL FOR UPDATE is a no-op under SQLite's single-writer model;
        # pymysql uses %s placeholders while sqlite3 uses ?.
        return sql.replace(' FOR UPDATE', '').replace('%s', '?')

    def one(self, sql, params=()):
        cursor = self.conn.execute(self._adapt(sql), params)
        found = cursor.fetchone()
        return Row(dict(found)) if found is not None else None

    def all(self, sql, params=()):
        cursor = self.conn.execute(self._adapt(sql), params)
        return [Row(dict(row)) for row in cursor.fetchall()]

    def execute(self, sql, params=()):
        cursor = self.conn.execute(self._adapt(sql), params)
        return cursor.rowcount


class BlindTestBase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        for statement in DDL:
            self.conn.execute(statement)
        for segment in SEGMENTS:
            self.conn.execute(
                '''INSERT INTO mat_segments
                   (code,label,from_node,to_node,length_m,priority,state)
                   VALUES (?,?,?,?,?,?,?)''',
                segment,
            )
        for pos, row in enumerate(TRAINING, start=1):
            segment, slope, moisture, rut, result = row
            self.conn.execute(
                '''INSERT INTO roll_trials
                   (code,segment_code,observed_at,slope_pct,moisture_pct,rut_mm,observed_result)
                   VALUES (?,?,?,?,?,?,?)''',
                (f'TR-{pos:03}', segment, f'2026-11-24T08:{pos:02}:00Z',
                 slope, moisture, rut, result),
            )
        self.conn.commit()
        self._counters = {}
        self.jobs = []

        import contextlib

        @contextlib.contextmanager
        def fake_tx():
            yield SqliteSession(self.conn)
            self.conn.commit()

        def fake_code(prefix):
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            return f'{prefix}-T{self._counters[prefix]:04d}'

        def fake_enqueue(kind, payload):
            job_id = f'job-{len(self.jobs) + 1}'
            self.jobs.append((job_id, kind, payload))
            return job_id

        self._patches = [
            mock.patch('infra.db.tx', fake_tx),
            mock.patch('sandmat.storage.new_code', fake_code),
            mock.patch('sandmat.storage.utc_now', lambda: '2026-11-27T01:00:00Z'),
        ]
        # blind/trials import tx at module import time, so patch the bound name.
        self._patches.append(mock.patch.object(blind, 'tx', fake_tx))
        self._patches.append(mock.patch.object(trials, 'tx', fake_tx))
        self._patches.append(mock.patch('infra.queue.enqueue', fake_enqueue))
        for patch in self._patches:
            patch.start()
            self.addCleanup(patch.stop)

    def db(self):
        return SqliteSession(self.conn)

    def add_trial(self, code, segment='D4', slope=2.5, moisture=22.3, rut=3.0,
                  observed=None, predicted=None):
        self.conn.execute(
            '''INSERT INTO roll_trials
               (code,segment_code,observed_at,slope_pct,moisture_pct,rut_mm,
                observed_result,predicted_result)
               VALUES (?,?,?,?,?,?,?,?)''',
            (code, segment, '2026-11-27T00:00:00Z', slope, moisture, rut, observed, predicted),
        )
        self.conn.commit()

    def open_batch(self, codes, title='潮前盲测'):
        form = mock.Mock(title=title, trial_codes=codes)
        return blind.open_batch(self.db(), form, 'admin@demo.test')

    def run_blind_job(self, payload):
        return blind.predict_job(payload)

    def snapshot_count(self, tested_segments=()):
        """盲测快照条数 = 全部公开判读 − 参测毯段的历史判读。"""
        excluded = set(tested_segments)
        return sum(1 for row in TRAINING if row[0] not in excluded)
