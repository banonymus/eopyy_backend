from fastapi import APIRouter, HTTPException
from db import async_session, Admission
from sqlalchemy import select
import os
import httpx
import logging

router = APIRouter()
logger = logging.getLogger("retry-endpoint")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")


async def send_webhook(event_type: str, payload: dict):
    if not WEBHOOK_URL:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(WEBHOOK_URL, json={"event": event_type, "data": payload})
        except Exception as e:
            logger.error(f"Webhook failed: {e}")


@router.post("/admissions/{ticket}/retry")
async def retry_admission(ticket: str):
    async with async_session() as session:
        result = await session.execute(
            select(Admission).where(Admission.ticket_number == ticket)
        )
        admission = result.scalar_one_or_none()

        if not admission:
            raise HTTPException(status_code=404, detail="Admission not found")

        if admission.status not in ("rejected", "error"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry admission with status '{admission.status}'",
            )

        admission.status = "pending"
        admission.error_code = None
        admission.error_details = None
        admission.updated_at = None

        await session.commit()

        await send_webhook("admission_retry", {"ticket_number": ticket})

        return {"status": "ok", "message": "Admission moved to pending"}
