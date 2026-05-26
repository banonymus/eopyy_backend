from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_session
from models import HL7Job
from datetime import datetime

router = APIRouter()

@router.get("/generate-hl7")
async def generate_hl7(from_date: str, to_date: str, db: AsyncSession = Depends(get_session)):
    job_id = f"hl7_discharges_{from_date}_{to_date}"

    # Check if job already exists
    result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
    existing = result.scalar_one_or_none()

    if existing:
        return {
            "job_id": job_id,
            "status": existing.status,
            "check_status": f"/job-status/{job_id}"
        }

    job = HL7Job(
        job_id=job_id,
        from_date=datetime.strptime(from_date, "%Y-%m-%d"),
        to_date=datetime.strptime(to_date, "%Y-%m-%d"),
        status="queued"
    )

    db.add(job)
    await db.commit()

    return {
        "job_id": job_id,
        "status": "queued",
        "check_status": f"/job-status/{job_id}"
    }
