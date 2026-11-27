from fastapi import HTTPException

from infra.db import tx

from .classifier import predict
from .storage import locked_row, new_code, utc_now


def record(db, form):
    if db.one('SELECT code FROM mat_segments WHERE code = %s', (form.segment_code,)) is None:
        raise HTTPException(404, '毯段不存在。')
    code = new_code('RB')
    db.execute(
        '''INSERT INTO roll_trials
           (code, segment_code, observed_at, slope_pct, moisture_pct, rut_mm, observed_result)
           VALUES (%s,%s,%s,%s,%s,%s,%s)''',
        (code, form.segment_code, utc_now(), form.slope_pct, form.moisture_pct,
         form.rut_mm, form.observed_result),
    )
    return db.one('SELECT * FROM roll_trials WHERE code = %s', (code,))


def confirm(db, code, outcome):
    row = locked_row(db, 'roll_trials', code)
    if row['observed_result'] is not None:
        raise HTTPException(409, '现场结果已登记，请另建测验以保留原始记录。')
    if row['predicted_result'] is None:
        raise HTTPException(409, '请先完成模型推演，再登记这次实测结果。')
    db.execute('UPDATE roll_trials SET observed_result = %s WHERE code = %s', (outcome, code))
    return db.one('SELECT * FROM roll_trials WHERE code = %s', (code,))


def classify_job(payload):
    code = payload['code']
    with tx() as db:
        probe = locked_row(db, 'roll_trials', code)
        if probe['predicted_result'] is not None:
            return {'code': code, 'predicted_result': probe['predicted_result'],
                    'clear_probability': float(probe['clear_probability']), 'sample_count': probe['sample_count']}
        if probe['observed_result'] is not None:
            raise ValueError('模型仅推演未登记判读的测验，以便留出现场验证。')
        if probe['blind_batch_code'] is not None:
            batch = db.one('SELECT status FROM blind_batches WHERE code=%s',
                           (probe['blind_batch_code'],))
            if batch is not None and batch['status'] == 'sealed':
                raise ValueError('密封盲测测验只能由盲测任务按开测快照推演。')
        # 密封盲测中的判读（含参测毯段以往判读若被纳入批次）不参与日常拟合；
        # 已揭晓批次的样本则正常回流训练。
        rows = db.all(
            '''SELECT * FROM roll_trials
               WHERE observed_result IS NOT NULL
                 AND (blind_batch_code IS NULL
                      OR blind_batch_code IN (
                          SELECT code FROM blind_batches WHERE status = 'revealed'))
               ORDER BY code'''
        )
        result = predict(rows, probe)
        db.execute(
            '''UPDATE roll_trials SET predicted_result=%s, clear_probability=%s, sample_count=%s
               WHERE code=%s''',
            (result['predicted_result'], result['clear_probability'], result['sample_count'], code),
        )
    return {'code': code, **result}
