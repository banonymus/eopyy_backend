import os
import ssl
import asyncio
import logging
import asyncpg
import datetime
from app.hl7_generator import generate_hl7_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hl7-worker")

raw_url = os.getenv("WORKER_DATABASE_URL")
if not raw_url:
    raise RuntimeError("WORKER_DATABASE_URL missing")

ssl_ctx = ssl.create_default_context()

# ---------------------------------------------------------
# WORKER LOOP (pure asyncpg)
# ---------------------------------------------------------
async def worker_loop():
    logger.info("worker_batch 🚀 HL7 Worker started")

    while True:
        try:
            # ---------------------------------------------------------
            # CONNECT TO NEON
            # ---------------------------------------------------------
            conn = await asyncpg.connect(raw_url, ssl=ssl_ctx)

            # ---------------------------------------------------------
            # FETCH NEXT QUEUED JOB
            # ---------------------------------------------------------
            job = await conn.fetchrow("""
                SELECT *
                FROM hl7_jobs
                WHERE status = 'queued_batch'
                ORDER BY created_at
                LIMIT 1
            """)

            if not job:
                await conn.close()
                await asyncio.sleep(2)
                continue

            job_id = job["job_id"]
            logger.info(f"worker_batch 📥 Processing job: {job_id}")

            # ---------------------------------------------------------
            # MARK AS PROCESSING
            # ---------------------------------------------------------
            await conn.execute("""
                UPDATE hl7_jobs
                SET status = 'processing'
                WHERE job_id = $1
            """, job_id)

            # ---------------------------------------------------------
            # DATE RANGE → HL7 TIMESTAMP FORMAT
            # ---------------------------------------------------------
            start_hl7 = job["from_date"].strftime("%Y%m%d000000")
            end_hl7 = job["to_date"].strftime("%Y%m%d235959")

            # ---------------------------------------------------------
            # FETCH DISCHARGES
            # ---------------------------------------------------------
            country = job.get("country_code")

            query = """
                SELECT *
                FROM discharges
                WHERE discharge_datetime BETWEEN $1 AND $2
                  AND installation_code = $3
            """

            if country == "GR":
                query += " AND country_code = 'GR'"
            elif country == "**":
                query += " AND country_code <> 'GR'"

            query += " ORDER BY discharge_datetime ASC"

            rows = await conn.fetch(query, start_hl7, end_hl7, job["installation_code"])
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
            out_path = f"/tmp/{job_id}.hl7"

            await generate_hl7_file(
                discharges,
                out_path,
                job_id,
                job["installation_code"],
                total_amount,
                covered_amount,
                patient_amount
            )

            with open(out_path, "r", encoding="utf-8") as f:
                hl7_text = f.read()

            # ---------------------------------------------------------
            # STORE HL7 CONTENT IN NEON
            # ---------------------------------------------------------
            await conn.execute("""
                UPDATE hl7_jobs
                SET status = 'completed',
                    file_data = $1,
                    result_file = $2,
                    updated_at = $3
                WHERE job_id = $4
            """, hl7_text, out_path, datetime.datetime.utcnow(), job_id)

            await conn.close()

            logger.info(f"worker_batch 📤 Completed job: {job_id}")

        except Exception:
            logger.exception("Worker_batch crashed")
            await asyncio.sleep(5)
