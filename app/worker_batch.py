import os
import ssl
import asyncio
import logging
import asyncpg
import datetime
from sqlalchemy import select
from models import HL7Job
from app.hl7_generator import generate_hl7_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hl7-worker")

raw_url = os.getenv("WORKER_DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL missing")

if "sslmode=" in raw_url:
    raw_url = raw_url.split("?")[0]

ssl_ctx = ssl.create_default_context()

# ---------------------------------------------------------
# NEW: Create fresh engine + sessionmaker each loop
# ---------------------------------------------------------
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

def get_new_session():
    engine = create_async_engine(
        raw_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False
    )
    return async_sessionmaker(engine, expire_on_commit=False)()

# ---------------------------------------------------------
# WORKER LOOP
# ---------------------------------------------------------
async def worker_loop():
    logger.info("🚀 HL7 Worker started")

    while True:
        try:
            # NEW: recreate engine + session each loop
            db = get_new_session()

            # ---------------------------------------------------------
            # FETCH NEXT QUEUED JOB
            # ---------------------------------------------------------
            try:
                result = await db.execute(
                    select(HL7Job)
                    .where(HL7Job.status == "queued")
                    .order_by(HL7Job.created_at)
                    .limit(1)
                )
            except Exception as exc:
                logger.exception("SQLAlchemy SELECT failed")

                if "InvalidCachedStatementError" in str(exc):
                    logger.warning("⚠️ Invalid cached statement — full engine reset next loop")
                    await asyncio.sleep(1)
                    continue

                raise

            job = result.scalar_one_or_none()

            if not job:
                await asyncio.sleep(2)
                continue

            logger.info(f"📥 Processing job: {job.job_id}")

            job.status = "processing"
            await db.commit()

            # ---------------------------------------------------------
            # DATE RANGE → HL7 TIMESTAMP FORMAT
            # ---------------------------------------------------------
            start_hl7 = job.from_date.strftime("%Y%m%d000000")
            end_hl7 = job.to_date.strftime("%Y%m%d235959")

            # ---------------------------------------------------------
            # FETCH DISCHARGES FOR THIS INSTALLATION
            # ---------------------------------------------------------
            conn = await asyncpg.connect(raw_url, ssl=ssl_ctx)

            rows = await conn.fetch("""
                SELECT *
                FROM discharges
                WHERE discharge_datetime BETWEEN $1 AND $2
                  AND installation_code = $3
                ORDER BY discharge_datetime ASC
            """, start_hl7, end_hl7, job.installation_code)

            await conn.close()

            discharges = [dict(r) for r in rows]

            # ---------------------------------------------------------
            # DYNAMIC Z03 TOTALS
            # ---------------------------------------------------------
            total_amount = sum(r.get("amount_total", 0) for r in discharges)
            covered_amount = sum(r.get("amount_covered", 0) for r in discharges)
            patient_amount = sum(r.get("amount_patient", 0) for r in discharges)

            # ---------------------------------------------------------
            # GENERATE HL7 FILE
            # ---------------------------------------------------------
            out_path = f"/tmp/{job.job_id}.hl7"

            await generate_hl7_file(
                discharges,
                out_path,
                job.installation_code,
                total_amount,
                covered_amount,
                patient_amount
            )

            # ---------------------------------------------------------
            # STORE HL7 CONTENT IN NEON
            # ---------------------------------------------------------
            with open(out_path, "r", encoding="utf-8") as f:
                hl7_text = f.read()

            job.file_data = hl7_text
            job.result_file = None
            job.status = "completed"
            job.updated_at = datetime.datetime.utcnow()

            await db.commit()

            logger.info(f"📤 Completed job: {job.job_id}")

        except Exception:
            logger.exception("Worker crashed")
            await asyncio.sleep(5)
