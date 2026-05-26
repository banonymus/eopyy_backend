import os
import ssl
import asyncio
import logging
import asyncpg
from sqlalchemy import select
from database import async_session
from models import HL7Job
from app.hl7_generator import generate_hl7_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hl7-worker")

raw_url = os.getenv("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL missing")

if "sslmode=" in raw_url:
    raw_url = raw_url.split("?")[0]

ssl_ctx = ssl.create_default_context()

async def worker_loop():
    logger.info("🚀 HL7 Worker started")

    while True:
        try:
            async with async_session() as db:

                result = await db.execute(
                    select(HL7Job)
                    .where(HL7Job.status == "queued")
                    .order_by(HL7Job.created_at)
                    .limit(1)
                )
                job = result.scalar_one_or_none()

                if not job:
                    await asyncio.sleep(2)
                    continue

                logger.info(f"📥 Processing job: {job.job_id}")

                job.status = "processing"
                await db.commit()

                start_hl7 = job.from_date.strftime("%Y%m%d000000")
                end_hl7 = job.to_date.strftime("%Y%m%d235959")

                conn = await asyncpg.connect(raw_url, ssl=ssl_ctx)

                rows = await conn.fetch("""
                    SELECT *
                    FROM discharges
                    WHERE discharge_datetime BETWEEN $1 AND $2
                    ORDER BY discharge_datetime ASC
                """, start_hl7, end_hl7)

                await conn.close()

                discharges = [dict(r) for r in rows]

                out_path = f"/tmp/{job.job_id}.hl7"
                await generate_hl7_file(discharges, out_path)

                job.status = "completed"
                job.result_file = out_path
                await db.commit()

                logger.info(f"📤 Completed job: {job.job_id}")

        except Exception:
            logger.exception("Worker crashed")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(worker_loop())

