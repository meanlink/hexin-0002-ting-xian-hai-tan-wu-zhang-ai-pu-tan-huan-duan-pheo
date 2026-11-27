from fastapi import HTTPException

from .connectivity import ROUTES, check_routes
from .states import OrderState, SegmentState, TrialResult
from .storage import locked_row, new_code, segment_map, utc_now


def validate_pairs(segments, retire, deploy):
    if retire is None or deploy is None or retire == deploy:
        raise HTTPException(422, '请选择两个不同且存在的毯段。')
    if segments[retire]['state'] != SegmentState.LAID or segments[deploy]['state'] != SegmentState.STANDBY:
        raise HTTPException(409, '需撤下铺设中的毯段，并启用备用毯段。请刷新当前铺设状态。')


def propose(db, form, actor):
    segments = segment_map(db)
    retire, deploy = form.retire_code, form.deploy_code
    if retire not in segments or deploy not in segments:
        raise HTTPException(404, '拟换的毯段不存在。')
    validate_pairs(segments, retire, deploy)
    start, end = form.tide_window.split('–')
    if end <= start:
        raise HTTPException(422, '换段窗口结束时刻必须晚于开始时刻。')
    trial = db.one('SELECT * FROM roll_trials WHERE code = %s', (form.trial_code,))
    validate_trial(trial, deploy)
    code = new_code('SW')
    db.execute(
        '''INSERT INTO mat_orders
           (code, retire_code, deploy_code, trial_code, tide_window, remarks, state, author_name)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (code, retire, deploy, form.trial_code, form.tide_window, form.remarks, OrderState.DRAFT, actor),
    )
    return detail(db, code, segments)


def validate_trial(trial, deploy):
    if trial is None or trial['segment_code'] != deploy:
        raise HTTPException(409, '换段测验必须来自拟铺设的毯段。')
    if trial['predicted_result'] != TrialResult.CLEAR or trial['observed_result'] != TrialResult.CLEAR:
        raise HTTPException(409, '拟铺段必须同时通过模型筛查和现场滚轮实测。')


def detail(db, code, segments=None):
    order = db.one('SELECT * FROM mat_orders WHERE code=%s', (code,))
    if order is None:
        raise HTTPException(404, '找不到换段令。')
    if order['state'] == OrderState.DRAFT:
        segments = segments if segments is not None else segment_map(db)
        order['routes'] = check_routes(segments.values(), order['retire_code'], order['deploy_code'])
    else:
        order['routes'] = [
            {'purpose': purpose, 'label': label, 'connected': True,
             'segments': order[f'signed_{purpose}_path'].split(',')}
            for purpose, label, _, _ in ROUTES
        ]
    return order


def approve(db, code, actor):
    order = locked_row(db, 'mat_orders', code)
    if order['state'] != OrderState.DRAFT:
        raise HTTPException(409, '仅草拟换段令可以签发。')
    segments = segment_map(db, lock=True)
    retire, deploy = order['retire_code'], order['deploy_code']
    validate_pairs(segments, retire, deploy)
    trial = locked_row(db, 'roll_trials', order['trial_code'])
    validate_trial(trial, deploy)
    routes = check_routes(segments.values(), retire, deploy)
    broken = [route['label'] for route in routes if not route['connected']]
    if broken:
        raise HTTPException(409, '换段将切断 ' + '、'.join(broken))
    db.execute('UPDATE mat_segments SET state=%s WHERE code=%s', (SegmentState.LAID, deploy))
    db.execute('UPDATE mat_segments SET state=%s WHERE code=%s', (SegmentState.STANDBY, retire))
    db.execute(
        '''UPDATE mat_orders SET state=%s, signatory=%s, signed_at=%s,
           signed_access_path=%s, signed_rescue_path=%s WHERE code=%s''',
        (OrderState.APPROVED, actor, utc_now(),
         ','.join(routes[0]['segments']), ','.join(routes[1]['segments']), code),
    )
    return detail(db, code)


def hand(db, code, recipient):
    order = locked_row(db, 'mat_orders', code)
    if order['state'] != OrderState.APPROVED:
        raise HTTPException(409, '请先签发换段令，再交给当班人员。')
    db.execute(
        'UPDATE mat_orders SET state=%s, handed_to=%s, handed_at=%s WHERE code=%s',
        (OrderState.HANDED, recipient, utc_now(), code),
    )
    return detail(db, code)
