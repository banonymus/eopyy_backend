from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()

QUEUE_DIR = "/tmp/hl7_queue"
OUTPUT_DIR = "/tmp"


@router.get("/job-status/{job_id}")
async def job_status(job_id: str):
    job_file = f"{QUEUE_DIR}/{job_id}.json"
    hl7_file = f"{OUTPUT_DIR}/{job_id}.hl7"

    if os.path.exists(job_file):
        return {"job_id": job_id, "status": "processing"}

    if os.path.exists(hl7_file):
        return {
            "job_id": job_id,
            "status": "completed",
            "download": f"/download/{job_id}"
        }

    return {"job_id": job_id, "status": "unknown"}


@router.get("/download/{job_id}")
async def download_hl7(job_id: str):
    file_path = f"{OUTPUT_DIR}/{job_id}.hl7"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="HL7 file not found")

    return FileResponse(
        file_path,
        media_type="text/plain",
        filename=f"{job_id}.hl7"
    )
