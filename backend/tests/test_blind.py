import json
import unittest

from fastapi import HTTPException

from sandmat import blind, trials
from sandmat.blind_states import BlindStatus
from sandmat.states import TrialResult

from tests.harness import BlindTestBase


class OpeningProtocolTests(BlindTestBase):
    def test_only_trials_without_prediction_or_observation_qualify(self):
        self.add_trial('NEW-01')
        self.add_trial('NEW-02')
        batch = self.open_batch(['NEW-01', 'NEW-02'])
        self.assertEqual(batch['status'], BlindStatus.SEALED)
        self.assertEqual(batch['trial_total'], 2)
        # 两条均在 D4，快照剔除 D4 的两条历史判读（12 → 10）。
        self.assertEqual(batch['locked_sample_count'], self.snapshot_count(('D4',)))

    def test_rejects_trial_that_already_has_prediction(self):
        self.add_trial('NEW-01', predicted=TrialResult.CLEAR)
        with self.assertRaises(HTTPException) as ctx:
            self.open_batch(['NEW-01'])
        self.assertEqual(ctx.exception.status_code, 409)

    def test_rejects_trial_that_already_has_observation(self):
        self.add_trial('NEW-01', observed=TrialResult.STUCK)
        with self.assertRaises(HTTPException) as ctx:
            self.open_batch(['NEW-01'])
        self.assertEqual(ctx.exception.status_code, 409)

    def test_rejects_duplicate_codes(self):
        self.add_trial('NEW-01')
        form = _form(['NEW-01', 'NEW-01'])
        with self.assertRaises(HTTPException) as ctx:
            blind.open_batch(self.db(), form, 'admin@demo.test')
        self.assertEqual(ctx.exception.status_code, 422)

    def test_locked_snapshot_freezes_training_and_excludes_later_labels(self):
        self.add_trial('NEW-01')
        batch = self.open_batch(['NEW-01'])
        snapshot = json.loads(self.db().one(
            'SELECT locked_snapshot AS s FROM blind_batches WHERE code=%s',
            (batch['code'],))['s'])
        self.assertEqual(len(snapshot), self.snapshot_count(('D4',)))
        # 参测毯段 D4 的两条历史判读不得进入开测快照。
        self.assertFalse(any(row['segment_code'] == 'D4' for row in snapshot))

        # A brand-new labelled trial registered after the batch opens must not
        # change the frozen snapshot used by blind predictions.
        self.add_trial('LATE-LABEL', slope=9.0, moisture=95.0, rut=40.0,
                       observed=TrialResult.STUCK)
        again = blind.detail(self.db(), batch['code'])
        self.assertEqual(again['locked_sample_count'], self.snapshot_count(('D4',)))

    def test_trial_cannot_join_two_batches(self):
        self.add_trial('NEW-01')
        self.open_batch(['NEW-01'], title='第一批')
        with self.assertRaises(HTTPException) as ctx:
            self.open_batch(['NEW-01'], title='第二批')
        self.assertEqual(ctx.exception.status_code, 409)

    def test_participating_segment_history_is_excluded_from_fit(self):
        # B2 参测：它在演示训练集中有 1 条 clear、2 条 stuck 历史判读，
        # 这些都不得进入本批快照（防“模型提前见过该段”泄漏）。
        self.add_trial('B2-PROBE', segment='B2', slope=4.0, moisture=40.0, rut=8.0)
        batch = self.open_batch(['B2-PROBE'])
        snapshot = json.loads(self.db().one(
            'SELECT locked_snapshot AS s FROM blind_batches WHERE code=%s',
            (batch['code'],))['s'])
        self.assertEqual(batch['locked_sample_count'], self.snapshot_count(('B2',)))
        self.assertFalse(any(row['segment_code'] == 'B2' for row in snapshot))
        # 剔除 B2 的 3 条后，每类仍不少于分类器要求的 4 条下限，推演可正常完成。
        result = self.run_blind_job({'batch_code': batch['code'], 'code': 'B2-PROBE'})
        self.assertEqual(result['sample_count'], self.snapshot_count(('B2',)))
        self.assertIn(result['predicted_result'], list(TrialResult))

    def test_open_rejected_when_segment_exclusion_starves_a_class(self):
        # B2 与 C3 同时参测会剔除 4 条受阻历史判读，受阻类仅剩 2 条，低于每类 4 条。
        self.add_trial('B2-PROBE', segment='B2', slope=4.0, moisture=40.0, rut=8.0)
        self.add_trial('C3-PROBE', segment='C3', slope=5.0, moisture=50.0, rut=10.0)
        with self.assertRaises(HTTPException) as ctx:
            self.open_batch(['B2-PROBE', 'C3-PROBE'])
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn('stuck', ctx.exception.detail)
        # 被拒后测验仍保持未入批状态，可用于后续合格批次。
        row = self.db().one('SELECT blind_batch_code AS b FROM roll_trials WHERE code=%s',
                            ('B2-PROBE',))
        self.assertIsNone(row['b'])


class SealedPredictionTests(BlindTestBase):
    def _open_with_two_probes(self):
        # One probe near the clear cluster, one near the stuck cluster.
        self.add_trial('PR-CLEAR', slope=2.4, moisture=20.0, rut=2.5)
        self.add_trial('PR-STUCK', slope=7.0, moisture=72.0, rut=20.0)
        return self.open_batch(['PR-CLEAR', 'PR-STUCK'])

    def test_predictions_use_the_frozen_snapshot_only(self):
        batch = self._open_with_two_probes()
        stuck = self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-STUCK'})
        self.assertEqual(stuck['sample_count'], self.snapshot_count(('D4',)))
        self.assertEqual(stuck['predicted_result'], TrialResult.STUCK)

        # Even after many new labelled rows arrive, the blind retry keeps the
        # original sample count: the open-time training set never changes.
        for i in range(6):
            self.add_trial(f'EXTRA-{i}', slope=8.0, moisture=88.0, rut=30.0,
                           observed=TrialResult.STUCK)
        retry = self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-STUCK'})
        self.assertEqual(retry['sample_count'], self.snapshot_count(('D4',)))
        self.assertEqual(retry['predicted_result'], TrialResult.STUCK)

    def test_retry_after_interruption_is_idempotent_and_keeps_snapshot(self):
        batch = self._open_with_two_probes()
        first = self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-CLEAR'})
        row = self.db().one('SELECT * FROM roll_trials WHERE code=%s', ('PR-CLEAR',))
        # Simulate a duplicate job delivery after a worker restart.
        second = self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-CLEAR'})
        self.assertEqual(second['predicted_result'], first['predicted_result'])
        self.assertEqual(second['clear_probability'], float(row['clear_probability']))
        self.assertEqual(second['sample_count'], row['blind_sample_count'])

    def test_sealed_results_are_hidden_from_detail_view(self):
        batch = self._open_with_two_probes()
        blind.assess(self.db(), batch['code'], 'PR-CLEAR', TrialResult.CLEAR)
        view = blind.detail(self.db(), batch['code'])
        trial = next(item for item in view['trials'] if item['code'] == 'PR-CLEAR')
        self.assertTrue(trial['has_observation'])
        self.assertNotIn('observed_result', trial)
        self.assertNotIn('predicted_result', trial)

    def test_sealed_blind_labels_never_enter_daily_training(self):
        batch = self._open_with_two_probes()
        blind.assess(self.db(), batch['code'], 'PR-STUCK', TrialResult.STUCK)
        # A normal daily probe must train only on the original public rows.
        self.add_trial('DAILY-01')
        result = trials.classify_job({'code': 'DAILY-01'})
        stored = self.db().one('SELECT * FROM roll_trials WHERE code=%s', ('DAILY-01',))
        self.assertEqual(result['sample_count'], self.snapshot_count())
        self.assertEqual(stored['sample_count'], self.snapshot_count())

    def test_daily_predict_rejects_a_sealed_blind_trial(self):
        batch = self._open_with_two_probes()
        with self.assertRaises(ValueError):
            trials.classify_job({'code': 'PR-CLEAR'})


class AssessmentAndRevealTests(BlindTestBase):
    def _open_batch(self):
        self.add_trial('PR-CLEAR', slope=2.4, moisture=20.0, rut=2.5)
        self.add_trial('PR-FALSE', slope=7.0, moisture=72.0, rut=20.0)
        return self.open_batch(['PR-CLEAR', 'PR-FALSE'])

    def test_field_assessment_can_be_sealed_before_prediction(self):
        batch = self._open_batch()
        view = blind.assess(self.db(), batch['code'], 'PR-CLEAR', TrialResult.CLEAR)
        self.assertTrue(view['trials'][0]['has_observation'])
        with self.assertRaises(HTTPException) as ctx:
            blind.assess(self.db(), batch['code'], 'PR-CLEAR', TrialResult.STUCK)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_final_trial_accepts_prediction_and_observation_together(self):
        batch = self._open_batch()
        blind.assess(self.db(), batch['code'], 'PR-CLEAR', TrialResult.CLEAR)
        self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-CLEAR'})
        # Last trial: both land through the same predict-job payload, one result.
        result = self.run_blind_job({
            'batch_code': batch['code'], 'code': 'PR-FALSE',
            'observed_result': TrialResult.STUCK,
        })
        row = self.db().one('SELECT * FROM roll_trials WHERE code=%s', ('PR-FALSE',))
        self.assertEqual(row['observed_result'], TrialResult.STUCK)
        self.assertEqual(row['predicted_result'], result['predicted_result'])

    def test_reveal_blocked_until_every_trial_has_both_outcomes(self):
        batch = self._open_batch()
        blind.assess(self.db(), batch['code'], 'PR-CLEAR', TrialResult.CLEAR)
        self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-CLEAR'})
        with self.assertRaises(HTTPException) as ctx:
            blind.reveal(self.db(), batch['code'])
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn('PR-FALSE', ctx.exception.detail)

    def test_reveal_counts_stuck_misread_as_clear_and_publishes_once(self):
        batch = self._open_batch()
        # PR-FALSE sits in the stuck feature cluster; the model should call it
        # stuck, but force a false-clear scenario by picking boundary features
        # is avoided — instead assert the report matches stored columns.
        for code, observed in (('PR-CLEAR', TrialResult.CLEAR),
                               ('PR-FALSE', TrialResult.STUCK)):
            blind.assess(self.db(), batch['code'], code, observed)
            self.run_blind_job({'batch_code': batch['code'], 'code': code})
        # Overwrite PR-FALSE's prediction to clear to emulate a directional miss,
        # then reveal must count exactly one "stuck judged passable".
        self.conn.execute(
            "UPDATE roll_trials SET predicted_result='clear' WHERE code='PR-FALSE'")
        self.conn.commit()
        report = blind.reveal(self.db(), batch['code'])
        self.assertEqual(report['status'], BlindStatus.REVEALED)
        self.assertEqual(report['false_clear_count'], 1)
        self.assertEqual(report['report']['false_clear_codes'], ['PR-FALSE'])
        self.assertEqual(report['report']['checked'], 2)

        with self.assertRaises(HTTPException) as ctx:
            blind.reveal(self.db(), batch['code'])
        self.assertEqual(ctx.exception.status_code, 409)

    def test_revealed_trials_flow_back_into_daily_training(self):
        batch = self._open_batch()
        for code, observed in (('PR-CLEAR', TrialResult.CLEAR),
                               ('PR-FALSE', TrialResult.STUCK)):
            blind.assess(self.db(), batch['code'], code, observed)
            self.run_blind_job({'batch_code': batch['code'], 'code': code})
        blind.reveal(self.db(), batch['code'])

        self.add_trial('DAILY-02')
        result = trials.classify_job({'code': 'DAILY-02'})
        # 日常训练池仍是 12 条公开判读（盲测样本揭晓前不加入）；本批揭晓后
        # 两条盲测结果回流，共 14 条。注意参测段历史判读只在盲测快照中剔除，
        # 不影响日常训练池。
        self.assertEqual(result['sample_count'], self.snapshot_count() + 2)

    def test_revealed_detail_exposes_full_columns(self):
        batch = self._open_batch()
        for code, observed in (('PR-CLEAR', TrialResult.CLEAR),
                               ('PR-FALSE', TrialResult.STUCK)):
            blind.assess(self.db(), batch['code'], code, observed)
            self.run_blind_job({'batch_code': batch['code'], 'code': code})
        view = blind.reveal(self.db(), batch['code'])
        for trial in view['trials']:
            self.assertIn('predicted_result', trial)
            self.assertIn('observed_result', trial)
            self.assertIn('clear_probability', trial)


class RecordIntoSealedBatchTests(BlindTestBase):
    def test_new_trial_inside_batch_stays_sealed_and_unlabelled_to_daily_model(self):
        self.add_trial('PR-01')
        batch = self.open_batch(['PR-01'])
        form = _blind_form('D4', 6.5, 70.0, 18.0, TrialResult.STUCK)
        view = blind.record_trial(self.db(), batch['code'], form)
        self.assertEqual(view['trial_total'], 2)
        new_code = next(item['code'] for item in view['trials'] if item['code'] != 'PR-01')
        self.assertTrue(new_code.startswith('BT-'))
        # Even with an observation recorded, daily training ignores the sealed row.
        self.add_trial('DAILY-03')
        result = trials.classify_job({'code': 'DAILY-03'})
        self.assertEqual(result['sample_count'], self.snapshot_count())

    def test_cannot_record_into_revealed_batch(self):
        self.add_trial('PR-01')
        batch = self.open_batch(['PR-01'])
        blind.assess(self.db(), batch['code'], 'PR-01', TrialResult.CLEAR)
        self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-01'})
        blind.reveal(self.db(), batch['code'])
        with self.assertRaises(HTTPException) as ctx:
            blind.record_trial(self.db(), batch['code'],
                               _blind_form('D4', 2.0, 20.0, 2.0))
        self.assertEqual(ctx.exception.status_code, 409)


class SnapshotFidelityTests(BlindTestBase):
    def test_frozen_snapshot_keeps_probability_identical_after_new_labels(self):
        self.add_trial('PR-01', slope=6.4, moisture=68.0, rut=17.0)
        batch = self.open_batch(['PR-01'])
        before = self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-01'})

        # Reopen the same probe against a deliberately shifted daily pool:
        # extra stuck labels would move a non-frozen model, but the blind job
        # must reproduce the exact open-time probability and sample count.
        for i in range(8):
            self.add_trial(f'SHIFT-{i}', slope=8.5, moisture=92.0, rut=33.0,
                           observed=TrialResult.STUCK)
        # Reset the prediction so the model genuinely recomputes from snapshot.
        self.conn.execute(
            'UPDATE roll_trials SET predicted_result=NULL, clear_probability=NULL, '
            "blind_sample_count=NULL WHERE code='PR-01'")
        self.conn.commit()
        after = self.run_blind_job({'batch_code': batch['code'], 'code': 'PR-01'})
        self.assertEqual(after['clear_probability'], before['clear_probability'])
        self.assertEqual(after['sample_count'], self.snapshot_count(('D4',)))

    def test_report_counts_correct_and_false_clear_and_false_stuck_separately(self):
        # clear->clear correct, stuck predicted while observed clear (false stuck),
        # and the headline directional miss: observed stuck predicted clear.
        self.add_trial('T-OK', slope=2.4, moisture=20.0, rut=2.5)
        self.add_trial('T-FC', slope=6.6, moisture=70.0, rut=18.0)
        self.add_trial('T-FS', slope=3.0, moisture=24.0, rut=3.0)
        batch = self.open_batch(['T-OK', 'T-FC', 'T-FS'])
        outcomes = {'T-OK': TrialResult.CLEAR, 'T-FC': TrialResult.STUCK,
                    'T-FS': TrialResult.CLEAR}
        for code, observed in outcomes.items():
            blind.assess(self.db(), batch['code'], code, observed)
            self.run_blind_job({'batch_code': batch['code'], 'code': code})
        # Pin predictions to exercise every reporting branch deterministically.
        self.conn.executescript(
            "UPDATE roll_trials SET predicted_result='clear' WHERE code IN ('T-OK','T-FC');"
            "UPDATE roll_trials SET predicted_result='stuck' WHERE code='T-FS';")
        self.conn.commit()
        report = blind.reveal(self.db(), batch['code'])['report']
        self.assertEqual(report['checked'], 3)
        self.assertEqual(report['correct_count'], 1)
        self.assertEqual(report['false_clear_count'], 1)
        self.assertEqual(report['false_clear_codes'], ['T-FC'])


def _form(codes, title='潮前盲测'):
    form = unittest.mock.Mock()
    form.title = title
    form.trial_codes = codes
    return form


def _blind_form(segment, slope, moisture, rut, observed=None):
    form = unittest.mock.Mock()
    form.segment_code = segment
    form.slope_pct = slope
    form.moisture_pct = moisture
    form.rut_mm = rut
    form.observed_result = observed
    return form


if __name__ == '__main__':
    unittest.main()
