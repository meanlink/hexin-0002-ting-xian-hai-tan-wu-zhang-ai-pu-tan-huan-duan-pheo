from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from infra.auth import access
from infra.db import tx
from infra.queue import enqueue
from sandmat import orders, trials
from sandmat.connectivity import check_routes
from sandmat.schemas import HandoverInput, OrderInput, TrialInput
from sandmat.seed import seed as seed_domain
from sandmat.states import TrialResult
from sandmat.storage import segment_map

router = APIRouter()
Reader = Annotated[dict, Depends(access())]
Operator = Annotated[dict, Depends(access('operator', 'admin'))]
Supervisor = Annotated[dict, Depends(access('admin'))]
JOBS = {'sandmat-classify': trials.classify_job}
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
    return {'id': enqueue('sandmat-classify', {'code': code})}


@router.post('/trials/{code}/confirm')
def confirm_trial(code: str, form: Confirmation, _user: Operator):
    with tx() as db:
        return trials.confirm(db, code, form.outcome)


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
