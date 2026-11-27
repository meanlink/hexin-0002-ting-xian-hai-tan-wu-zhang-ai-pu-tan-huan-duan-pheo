"""Prospective blind tests over roll trials.

开测时把当时所有已判读且已公开的测验冻结成快照；批次揭晓前，参测毯段的
既有判读与新登记的盲测结果都不参与日常拟合，也不互相影响。全组预测和现场
判读齐备后由班长统一揭晓，揭晓结果只出一份，并统计把受阻判成可通行的次数。
"""

import json

from fastapi import HTTPException

from infra.db import tx

from .classifier import MIN_CLASS_ROWS, InsufficientLabels, predict
from .blind_states import BlindStatus
from .states import TrialResult
from .storage import locked_row, new_code, utc_now

SNAPSHOT_FEATURES = ('code', 'segment_code', 'slope_pct', 'moisture_pct', 'rut_mm', 'observed_result')


def _public_training(db):
    """日常推演的训练集：已判读、且不属于任何密封盲测批次的测验。"""
    return db.all(
        '''SELECT * FROM roll_trials
           WHERE observed_result IS NOT NULL
             AND (blind_batch_code IS NULL
                  OR blind_batch_code IN (SELECT code FROM blind_batches WHERE status = %s))
           ORDER BY code''',
        (BlindStatus.REVEALED,),
    )


def open_batch(db, form, actor):
    codes = list(dict.fromkeys(form.trial_codes))
    if len(codes) != len(form.trial_codes):
        raise HTTPException(422, '参测号码重复，请去掉重复项。')
    trials = []
    for code in codes:
        trial = locked_row(db, 'roll_trials', code)
        # 尚无预测和判读的滚轮测验才可入选盲测。
        if trial['predicted_result'] is not None or trial['observed_result'] is not None:
            raise HTTPException(409, f'{code} 已有预测或判读，不能进入盲测。')
        if trial['blind_batch_code'] is not None:
            raise HTTPException(409, f'{code} 已在盲测批次 {trial["blind_batch_code"]} 中。')
        trials.append(trial)
    # 防泄漏：参测毯段以往的判读不参与本批拟合，从开测快照中剔除这些段的历史样本。
    tested_segments = {trial['segment_code'] for trial in trials}
    training = [row for row in _public_training(db)
                if row['segment_code'] not in tested_segments]
    # 开测即校验快照充分性，避免把样本不足的任务推到 worker 才异步失败。
    for label in TrialResult:
        count = sum(1 for row in training if row['observed_result'] == label)
        if count < MIN_CLASS_ROWS:
            raise HTTPException(
                409, f'剔除参测毯段历史判读后，{label.value} 类仅 {count} 条，'
                f'少于开测所需的每类 {MIN_CLASS_ROWS} 条，无法盲测。')
    snapshot = [
        {name: (row[name].value if hasattr(row[name], 'value') else row[name])
         for name in SNAPSHOT_FEATURES}
        for row in training
    ]
    batch_code = new_code('BB')
    db.execute(
        '''INSERT INTO blind_batches
           (code,title,status,locked_at,locked_sample_count,locked_snapshot,opened_by,trial_total)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (batch_code, form.title, BlindStatus.SEALED, utc_now(), len(training),
         json.dumps(snapshot, ensure_ascii=False), actor, len(trials)),
    )
    for trial in trials:
        db.execute(
            'UPDATE roll_trials SET blind_batch_code=%s WHERE code=%s',
            (batch_code, trial['code']),
        )
    return detail(db, batch_code)


def _get_batch(db, code, lock=False):
    suffix = ' FOR UPDATE' if lock else ''
    batch = db.one(f'SELECT * FROM blind_batches WHERE code=%s{suffix}', (code,))
    if batch is None:
        raise HTTPException(404, '找不到该盲测批次。')
    return batch


def list_batches(db):
    return db.all('SELECT * FROM blind_batches ORDER BY locked_at DESC, code')


def detail(db, code):
    batch = _get_batch(db, code)
    members = db.all(
        'SELECT * FROM roll_trials WHERE blind_batch_code=%s ORDER BY code',
        (code,),
    )
    sealed = batch['status'] == BlindStatus.SEALED
    summary = {
        'code': batch['code'],
        'title': batch['title'],
        'status': batch['status'],
        'locked_at': batch['locked_at'],
        'locked_sample_count': batch['locked_sample_count'],
        'opened_by': batch['opened_by'],
        'trial_total': batch['trial_total'],
        'revealed_at': batch['revealed_at'],
        'false_clear_count': batch['false_clear_count'],
        'trials': [_trial_view(trial, sealed) for trial in members],
    }
    if not sealed:
        summary['report'] = _report(members)
    return summary


def _trial_view(trial, sealed):
    """密封期对模型列与现场列脱敏，只暴露进度，避免现场判读提前泄露。"""
    view = {
        'code': trial['code'],
        'segment_code': trial['segment_code'],
        'slope_pct': float(trial['slope_pct']),
        'moisture_pct': float(trial['moisture_pct']),
        'rut_mm': float(trial['rut_mm']),
        'observed_at': trial['observed_at'],
        'has_prediction': trial['predicted_result'] is not None,
        'has_observation': trial['observed_result'] is not None,
    }
    if not sealed:
        view.update({
            'predicted_result': trial['predicted_result'],
            'observed_result': trial['observed_result'],
            'clear_probability': float(trial['clear_probability'])
            if trial['clear_probability'] is not None else None,
            'blind_sample_count': trial['blind_sample_count'],
        })
    return view


def _report(members):
    checked = [row for row in members
               if row['predicted_result'] is not None and row['observed_result'] is not None]
    # 把现场受阻误判为可通行的次数，是盲测最关注的方向性差错。
    false_clears = [row['code'] for row in checked
                    if row['observed_result'] == TrialResult.STUCK
                    and row['predicted_result'] == TrialResult.CLEAR]
    correct = sum(1 for row in checked
                  if row['predicted_result'] == row['observed_result'])
    return {
        'checked': len(checked),
        'false_clear_codes': false_clears,
        'false_clear_count': len(false_clears),
        'correct_count': correct,
    }


def record_trial(db, batch_code, form):
    batch = _get_batch(db, batch_code, lock=True)
    if batch['status'] != BlindStatus.SEALED:
        raise HTTPException(409, '批次已揭晓，新测验请走日常通行试验流程。')
    if db.one('SELECT code FROM mat_segments WHERE code=%s', (form.segment_code,)) is None:
        raise HTTPException(404, '毯段不存在。')
    code = new_code('BT')
    db.execute(
        '''INSERT INTO roll_trials
           (code,segment_code,observed_at,slope_pct,moisture_pct,rut_mm,
            observed_result,blind_batch_code)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (code, form.segment_code, utc_now(), form.slope_pct, form.moisture_pct,
         form.rut_mm, form.observed_result, batch_code),
    )
    db.execute(
        'UPDATE blind_batches SET trial_total=trial_total+1 WHERE code=%s',
        (batch_code,),
    )
    return detail(db, batch_code)


def _snapshot_rows(batch):
    raw = json.loads(batch['locked_snapshot'])
    return [dict(row, observed_result=TrialResult(row['observed_result'])) for row in raw]


def predict_job(payload):
    batch_code, code = payload['batch_code'], payload['code']
    with tx() as db:
        batch = _get_batch(db, batch_code, lock=True)
        trial = locked_row(db, 'roll_trials', code)
        if trial['blind_batch_code'] != batch_code:
            raise HTTPException(409, '该测验不属于此盲测批次。')
        if batch['status'] != BlindStatus.SEALED:
            raise HTTPException(409, '批次已揭晓，不能再补做盲测推演。')
        # 幂等：中断恢复后的重试直接回写既有结果，训练样本仍是开测快照。
        if trial['predicted_result'] is not None:
            return {'code': code, 'predicted_result': trial['predicted_result'],
                    'clear_probability': float(trial['clear_probability']),
                    'sample_count': trial['blind_sample_count']}
        if payload.get('observed_result') is not None and trial['observed_result'] is None:
            db.execute(
                'UPDATE roll_trials SET observed_result=%s WHERE code=%s',
                (TrialResult(payload['observed_result']), code),
            )
            trial = locked_row(db, 'roll_trials', code)
        try:
            result = predict(_snapshot_rows(batch), trial)
        except InsufficientLabels as exc:
            raise HTTPException(409, str(exc)) from exc
        db.execute(
            '''UPDATE roll_trials
               SET predicted_result=%s,clear_probability=%s,blind_sample_count=%s
               WHERE code=%s''',
            (result['predicted_result'], result['clear_probability'],
             result['sample_count'], code),
        )
    return {'code': code, **result}


def assess(db, batch_code, code, outcome):
    batch = _get_batch(db, batch_code, lock=True)
    if batch['status'] != BlindStatus.SEALED:
        raise HTTPException(409, '批次已揭晓，现场判读已冻结。')
    trial = locked_row(db, 'roll_trials', code)
    if trial['blind_batch_code'] != batch_code:
        raise HTTPException(409, '该测验不属于此盲测批次。')
    if trial['observed_result'] is not None:
        raise HTTPException(409, '现场判读已密封提交，请另建测验以保留原始记录。')
    db.execute('UPDATE roll_trials SET observed_result=%s WHERE code=%s', (outcome, code))
    return detail(db, batch_code)


def reveal(db, code):
    batch = _get_batch(db, code, lock=True)
    if batch['status'] != BlindStatus.SEALED:
        raise HTTPException(409, '该批次已经揭晓，盲测结果只出一份。')
    members = db.all(
        'SELECT * FROM roll_trials WHERE blind_batch_code=%s ORDER BY code FOR UPDATE',
        (code,),
    )
    missing = [row['code'] for row in members
               if row['predicted_result'] is None or row['observed_result'] is None]
    if missing:
        raise HTTPException(409, '尚有测验未齐预测或现场判读：' + '、'.join(missing))
    false_clears = sum(1 for row in members
                       if row['observed_result'] == TrialResult.STUCK
                       and row['predicted_result'] == TrialResult.CLEAR)
    db.execute(
        '''UPDATE blind_batches
           SET status=%s, revealed_at=%s, false_clear_count=%s WHERE code=%s''',
        (BlindStatus.REVEALED, utc_now(), false_clears, code),
    )
    return detail(db, code)
