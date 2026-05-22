from fastapi import APIRouter
from datetime import datetime
import json
import os

router = APIRouter()

QUEUE_DIR = "/tmp/hl7_queue"
os.makedirs(QUEUE_DIR, exist_ok=True)


def to_hl7_range(date_str: str, end=False):
    """
    Μετατρέπει YYYY-MM-DD → YYYYMMDD000000 ή YYYYMMDD235959
    ώστε να ταιριάζει με Neon timestamps.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%Y%m%d235959" if end else "%Y%m%d000000")


@router.get("/generate-hl7")
async def generate_hl7(from_date: str, to_date: str):
    # Μετατροπή σε HL7 timestamps
    start_hl7 = to_hl7_range(from_date)
    end_hl7 = to_hl7_range(to_date, end=True)

    job_id = f"hl7_discharges_{from_date}_{to_date}"

    job = {
        "job_id": job_id,
        "type": "HL7_FILE_DISCHARGES",
        "start_date": start_hl7,
        "end_date": end_hl7
    }

    # Αποθήκευση job στο queue
    job_path = f"{QUEUE_DIR}/{job_id}.json"
    with open(job_path, "w") as f:
        json.dump(job, f)

    return {
        "status": "queued",
        "job_id": job_id,
        "start_date": start_hl7,
        "end_date": end_hl7,
        "check_status": f"/job-status/{job_id}"
    }
