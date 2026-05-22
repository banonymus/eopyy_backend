from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.responses import FileResponse

from database import get_session
from models import HL7Job

router = APIRouter()


@router.get("/job-status/{job_id}")
async def job_status(job_id: str, db: AsyncSession = Depends(get_session)):
    # Fetch job from DB
    result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        return {"job_id": job_id, "status": "unknown"}

    return {
        "job_id": job.job_id,
        "status": job.status,
        "download": f"/download/{job.job_id}" if job.status == "completed" else None
    }


@router.get("/download/{job_id}")
async def download(job_id: str, db: AsyncSession = Depends(get_session)):
    # Fetch job from DB
    result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(404, "Job not found")

    if job.status != "completed":
        raise HTTPException(400, "Job not completed yet")

    if not job.result_file:
        raise HTTPException(500, "Job completed but no file stored")

    return FileResponse(
        job.result_file,
        media_type="text/plain",
        filename=f"{job.job_id}.hl7"
    )
