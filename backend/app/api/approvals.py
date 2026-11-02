from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas import ApprovalDecisionRequest
from app.db.models import Approval
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("")
async def list_approvals():
    async with async_session_factory() as session:
        stmt = select(Approval).order_by(Approval.decided_at.desc().nulls_first())
        res = await session.execute(stmt)
        return res.scalars().all()


@router.post("/{approval_id}/decide")
async def decide_approval(approval_id: str, req: ApprovalDecisionRequest):
    async with async_session_factory() as session:
        appr = await session.get(Approval, approval_id)
        if not appr:
            raise HTTPException(status_code=404, detail="Approval request not found")

        appr.status = req.decision
        appr.decided_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(appr)

    await event_bus.emit(
        event_type=EventType.APPROVAL_DECIDED,
        project_id=appr.project_id,
        task_id=appr.task_id,
        payload={"approval_id": appr.id, "status": appr.status},
    )
    return appr
