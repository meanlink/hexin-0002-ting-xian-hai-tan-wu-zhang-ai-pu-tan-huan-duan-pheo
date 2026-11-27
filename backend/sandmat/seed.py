from .classifier import predict
from .demo import SEGMENTS, TRAINING


def seed(db):
    for segment in SEGMENTS:
        db.execute(
            '''INSERT IGNORE INTO mat_segments
               (code,label,from_node,to_node,length_m,priority,state) VALUES (%s,%s,%s,%s,%s,%s,%s)''',
            segment,
        )
    for pos, row in enumerate(TRAINING, start=1):
        db.execute(
            '''INSERT IGNORE INTO roll_trials
               (code,segment_code,observed_at,slope_pct,moisture_pct,rut_mm,observed_result)
               VALUES (%s,%s,%s,%s,%s,%s,%s)''',
            (f'TR-{pos:03}', row[0], f'2026-11-24T08:{pos:02}:00Z', *row[1:]),
        )
    training = [
        dict(slope_pct=slope, moisture_pct=moisture, rut_mm=rut, observed_result=result)
        for _, slope, moisture, rut, result in TRAINING
    ]
    probes = (
        ('TR-D4-DAWN', 'D4', '2026-11-24T23:35:00Z', 2.5, 22.3, 3.0),
        ('TR-R1-PREV', 'R1', '2026-11-24T00:21:00Z', 2.1, 19.3, 2.5),
    )
    for code, segment, timestamp, slope, moisture, rut in probes:
        sample = dict(slope_pct=slope, moisture_pct=moisture, rut_mm=rut)
        assessment = predict(training, sample)
        db.execute(
            """INSERT IGNORE INTO roll_trials
               (code,segment_code,observed_at,slope_pct,moisture_pct,rut_mm,observed_result,
                predicted_result,clear_probability,sample_count)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (code, segment, timestamp, slope, moisture, rut, 'clear',
             assessment['predicted_result'], assessment['clear_probability'], assessment['sample_count']),
        )
    db.execute(
        """INSERT IGNORE INTO mat_orders
           (code,retire_code,deploy_code,trial_code,tide_window,remarks,state,author_name,
            signatory,signed_at,signed_access_path,signed_rescue_path,handed_to,handed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ('SW-PREV-01', 'R2', 'R1', 'TR-R1-PREV', '08:35–09:05', '换回干爽救援旁线。',
         'handed', 'operator@demo.test', 'admin@demo.test', '2026-11-24T00:30:00Z',
         'A1,B2,C3', 'R1,B2', '救生岗 林珀', '2026-11-24T00:36:00Z'),
    )
    return {name: db.one(f'SELECT COUNT(*) AS n FROM {name}')['n']
            for name in ('mat_segments', 'roll_trials', 'mat_orders')}
