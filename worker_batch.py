import asyncio
import os
import json

from app.db import AsyncSessionLocal, fetch_discharges
from app.hl7_generator import generate_hl7_file

QUEUE = "/tmp/hl7_queue"


async def process_job(job):
    async with AsyncSessionLocal() as session:
        discharges = await fetch_discharges(
            session,
            job["start_date"],
            job["end_date"]
        )

    out_path = f"/tmp/{job['job_id']}.hl7"
    await generate_hl7_file(discharges, out_path)


async def worker_loop():
    os.makedirs(QUEUE, exist_ok=True)

    while True:
        jobs = [f for f in os.listdir(QUEUE) if f.endswith(".json")]

        for jf in jobs:
            path = os.path.join(QUEUE, jf)

            with open(path) as f:
                job = json.load(f)

            if job.get("type") == "HL7_FILE_DISCHARGES":
                await process_job(job)

            os.remove(path)

        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(worker_loop())
