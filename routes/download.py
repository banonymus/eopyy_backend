from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.responses import FileResponse
from database import get_session
from models import HL7Job

router = APIRouter()

@router.get("/download/{job_id}")
async def download(job_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
    job = result.scalar_one_or_none()

    if not job or job.status != "completed":
        raise HTTPException(404, "Not ready")

    return FileResponse(job.result_file, filename=f"{job.job_id}.hl7")
