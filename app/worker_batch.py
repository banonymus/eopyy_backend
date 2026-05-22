import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import async_session
from models import HL7Job
from datetime import datetime

def build_hl7_for_range(from_date, to_date):
    # Your HL7 generation logic here
    return f"HL7 DATA FOR {from_date} → {to_date}"

async def worker_loop():
    while True:
        async with async_session() as db:
            result = await db.execute(
                select(HL7Job)
                .where(HL7Job.status == "pending")
                .order_by(HL7Job.created_at)
                .limit(1)
            )
            job = result.scalar_one_or_none()

            if not job:
                await asyncio.sleep(3)
                continue

            job.status = "processing"
            await db.commit()

            hl7_content = build_hl7_for_range(job.from_date, job.to_date)

            filename = f"/tmp/{job.job_id}.hl7"
            with open(filename, "w") as f:
                f.write(hl7_content)

            job.status = "completed"
            job.result_file = filename
            await db.commit()

        await asyncio.sleep(0.1)
