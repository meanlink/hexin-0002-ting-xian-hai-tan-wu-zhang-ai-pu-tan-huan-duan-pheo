from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from infra.auth import access
from infra.db import tx
from infra.queue import enqueue
from sandmat import blind, orders, trials
from sandmat.connectivity import check_routes
from sandmat.schemas import (
    BatchInput,
    BlindAssessment,
    BlindPredictionInput,
    BlindTrialInput,
    HandoverInput,
    OrderInput,
    TrialInput,
)
from sandmat.seed import seed as seed_domain
from sandmat.states import TrialResult
from sandmat.storage import segment_map

router = APIRouter()
Reader = Annotated[dict, Depends(access())]
Operator = Annotated[dict, Depends(access('operator', 'admin'))]
Supervisor = Annotated[dict, Depends(access('admin'))]
JOBS = {
    'sandmat-classify': trials.classify_job,
    'sandmat-blind-classify': blind.predict_job,
}
seed = seed_domain


class Confirmation(BaseModel):
    outcome: TrialResult


@router.get('/segments')
def segments(_user: Reader):
    with tx() as db:
        current = list(segment_map(db).values())
    return {'segments': current, 'routes': check_routes(current)}


@router.get('/trials')
def list_trials(_user: Reader):
    with tx() as db:
        return db.all('SELECT * FROM roll_trials ORDER BY observed_at DESC, code')


@router.post('/trials', status_code=201)
def record_trial(form: TrialInput, _user: Operator):
    with tx() as db:
        return trials.record(db, form)


@router.post('/trials/{code}/predict', status_code=202)
def classify_trial(code: str, _user: Operator):
    with tx() as db:
        trial = db.one('SELECT * FROM roll_trials WHERE code=%s', (code,))
        if not trial:
            raise HTTPException(404, '测验不存在。')
        if trial['observed_result'] is not None and trial['predicted_result'] is None:
            raise HTTPException(409, '已判读训练样本不能作为模型留出测验。')
        if trial['blind_batch_code'] is not None:
            batch = db.one('SELECT status FROM blind_batches WHERE code=%s',
                           (trial['blind_batch_code'],))
            if batch and batch['status'] == 'sealed':
                raise HTTPException(409, '该测验属于密封盲测批次，须用盲测推演以锁定开测样本。')
    return {'id': enqueue('sandmat-classify', {'code': code})}


@router.post('/trials/{code}/confirm')
def confirm_trial(code: str, form: Confirmation, _user: Operator):
    with tx() as db:
        return trials.confirm(db, code, form.outcome)


@router.get('/blind-batches')
def list_blind_batches(_user: Reader):
    with tx() as db:
        return {'batches': blind.list_batches(db)}


@router.post('/blind-batches', status_code=201)
def open_blind_batch(form: BatchInput, user: Supervisor):
    with tx() as db:
        return blind.open_batch(db, form, user['email'])


@router.get('/blind-batches/{code}')
def blind_batch_detail(code: str, _user: Reader):
    with tx() as db:
        return blind.detail(db, code)


@router.post('/blind-batches/{code}/trials', status_code=201)
def record_blind_trial(code: str, form: BlindTrialInput, _user: Operator):
    with tx() as db:
        return blind.record_trial(db, code, form)


@router.post('/blind-batches/{code}/trials/{trial_code}/predict', status_code=202)
def predict_blind_trial(code: str, trial_code: str, form: BlindPredictionInput, _user: Operator):
    with tx() as db:
        batch = db.one('SELECT status FROM blind_batches WHERE code=%s', (code,))
        if not batch:
            raise HTTPException(404, '找不到该盲测批次。')
        trial = db.one(
            'SELECT code FROM roll_trials WHERE code=%s AND blind_batch_code=%s',
            (trial_code, code),
        )
        if not trial:
            raise HTTPException(404, '该测验不属于此盲测批次。')
    payload = {'batch_code': code, 'code': trial_code}
    if form.observed_result is not None:
        payload['observed_result'] = form.observed_result
    return {'id': enqueue('sandmat-blind-classify', payload)}


@router.post('/blind-batches/{code}/trials/{trial_code}/assess')
def assess_blind_trial(code: str, trial_code: str, form: BlindAssessment, _user: Operator):
    with tx() as db:
        return blind.assess(db, code, trial_code, form.outcome)


@router.post('/blind-batches/{code}/reveal')
def reveal_blind_batch(code: str, _user: Supervisor):
    with tx() as db:
        return blind.reveal(db, code)


@router.get('/moves')
def list_orders(_user: Reader):
    with tx() as db:
        return db.all('SELECT * FROM mat_orders ORDER BY signed_at DESC, code')


@router.get('/moves/{code}')
def order_detail(code: str, _user: Reader):
    with tx() as db:
        return orders.detail(db, code)


@router.post('/moves', status_code=201)
def propose_move(form: OrderInput, user: Operator):
    with tx() as db:
        return orders.propose(db, form, user['email'])


@router.post('/moves/{code}/approve')
def sign_move(code: str, user: Supervisor):
    with tx() as db:
        return orders.approve(db, code, user['email'])


@router.post('/moves/{code}/handover')
def handover_move(code: str, form: HandoverInput, _user: Operator):
    with tx() as db:
        return orders.hand(db, code, form.recipient)
