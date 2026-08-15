import asyncio
import asyncpg
import os
import json
import logging
import re
import httpx
import datetime
import ssl

# ---------------------------------------------------------
# DATABASE URL + SSL FIX
# ---------------------------------------------------------
raw_url = os.getenv("WORKER_DATABASE_URL")
if not raw_url:
    raise RuntimeError("WORKER_DATABASE_URL missing")

if "sslmode=" in raw_url:
    raw_url = raw_url.split("?")[0]

ssl_ctx = ssl.create_default_context()

# ---------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------
from hl7_builder_worker import build_hl7_message
from old_eopyy_client import submit_hl7
from discarge_eopyy_client import submit_discarge_hl7
from email_alerts import send_error_email
from models import HL7Job, Admission
from sqlalchemy import select
from app.hl7_generator import generate_hl7_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eopyy-worker")

DB_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# ---------------------------------------------------------
# ENGINE RECREATION (FINAL FIX FOR NEON)
# ---------------------------------------------------------
def get_new_session():
    engine = create_async_engine(
        raw_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)()

# ---------------------------------------------------------
# MINIMAL NEON PATCH (POOL-SAFE)
# ---------------------------------------------------------
async def neon_retry(conn, method, *args):
    try:
        return await method(*args)
    except (asyncpg.InvalidCachedStatementError, asyncpg.exceptions._base.InterfaceError):
        logger.warning("Neon invalidated prepared statement — retrying with fresh connection")
        return await method(*args)

# ---------------------------------------------------------
# HL7 PARSER
# ---------------------------------------------------------
def parse_hl7_response(raw):
    msa_match = re.search(r"MSA\|([A-Z]{2})\|([0-9]+)", raw)
    msa_code = msa_match.group(1) if msa_match else None
    message_id = msa_match.group(2) if msa_match else None

    err_match = re.search(r"ERR\|\|([A-Z0-9\^]+)\|([0-9]+)\|([A-Z])\|([0-9]+)", raw)
    err = {
        "location": err_match.group(1) if err_match else None,
        "code": err_match.group(2) if err_match else None,
        "severity": err_match.group(3) if err_match else None,
        "eopyy_code": err_match.group(4) if err_match else None,
    }

    return msa_code, message_id, err

# ---------------------------------------------------------
# WEBHOOK
# ---------------------------------------------------------
async def send_webhook(event_type: str, payload: dict):
    if not WEBHOOK_URL:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(WEBHOOK_URL, json={"event": event_type, "data": payload})
        except Exception as e:
            logger.error(f"Webhook failed: {e}")

# ---------------------------------------------------------
# SQLALCHEMY UPDATE FOR FASTAPI
# ---------------------------------------------------------
async def save_worker_results(ticket_number, hl7, raw_response, status):
    session = get_new_session()
    try:
        result = await session.execute(
            select(Admission).where(Admission.ticket_number == ticket_number)
        )
        adm = result.scalar_one_or_none()

        if adm:
            adm.hl7 = hl7
            adm.raw_response = raw_response
            adm.status = status
            await session.commit()
    finally:
        await session.close()

# ---------------------------------------------------------
# PROCESS ADMISSION
# ---------------------------------------------------------
# ---------------------------------------------------------
# PROCESS ADMISSION (NO DATABASE VERSION)
# ---------------------------------------------------------
async def process_admission_row(pool, row):
    row_id = row["id"]
    ticket = row["ticket_number"]

    logger.info(f"[{ticket}] Processing ADMISSION (id={row_id})")

    try:
        # Convert row to dict
        data = dict(row)

        # 1. Build HL7
        hl7 = build_hl7_message(data)

        # 2. Send HL7 to EOPYY SOAP
        raw_response = submit_hl7(hl7)

        # 3. Parse HL7 ACK
        msa_code, message_id, err = parse_hl7_response(raw_response)

        # 4. Log result (instead of saving to DB)
        logger.info(f"[{ticket}] HL7 MSA={msa_code}, message_id={message_id}, ERR={err}")

        # 5. Send webhook (optional)
        if msa_code == "AA":
            await send_webhook(
                "admission_completed",
                {"ticket_number": ticket, "message_id": message_id},
            )

        elif msa_code == "AR":
            await send_webhook(
                "admission_rejected",
                {"ticket_number": ticket, "error": err},
            )
            send_error_email(ticket, f"EOPYY rejected admission:\n\n{raw_response}")

        else:
            await send_webhook(
                "worker_error",
                {"ticket_number": ticket, "error": err},
            )
            send_error_email(ticket, f"EOPYY returned error:\n\n{raw_response}")

        # 6. Return result directly (NO DB)
        return {
            "ticket_number": ticket,
            "status": msa_code,
            "hl7": hl7,
            "raw_response": raw_response,
            "error": err,
        }

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"[{ticket}] Admission processing error")

        # Return error directly (NO DB)
        return {
            "ticket_number": ticket,
            "status": "error",
            "hl7": None,
            "raw_response": None,
            "error": error_msg,
        }

# ---------------------------------------------------------
# PROCESS DISCHARGE
# ---------------------------------------------------------
async def process_discharge_row(pool, row):
    row_id = row["id"]
    ticket = row["ticket_number"]

    logger.info(f"[{ticket}] Processing DISCHARGE (id={row_id})")

    async with pool.acquire() as conn:
        await neon_retry(
            conn,
            conn.execute,
            "UPDATE discharges SET status='processing', updated_at=NOW() WHERE id=$1",
            row_id,
        )

    try:
        data = dict(row)
        hl7 = build_hl7_message(data)

        async with pool.acquire() as conn:
            await neon_retry(
                conn,
                conn.execute,
                """
                UPDATE discharges
                SET hl7_a03=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                hl7,
            )

        raw_response = submit_discarge_hl7(hl7)
        msa_code, message_id, err = parse_hl7_response(raw_response)

        if msa_code == "AA":
            async with pool.acquire() as conn:
                await neon_retry(
                    conn,
                    conn.execute,
                    """
                    UPDATE discharges
                    SET status='completed',
                        raw_response_a03=$2,
                        updated_at=NOW()
                    WHERE id=$1
                    """,
                    row_id,
                    raw_response,
                )

            await send_webhook(
                "discharge_completed",
                {"ticket_number": ticket, "message_id": message_id},
            )

        elif msa_code == "AR":
            async with pool.acquire() as conn:
                await neon_retry(
                    conn,
                    conn.execute,
                    """
                    UPDATE discharges
                    SET status='rejected',
                        error_code=$3,
                        error_details=$4,
                        raw_response_a03=$2,
                        updated_at=NOW()
                    WHERE id=$1
                    """,
                    row_id,
                    raw_response,
                    err["eopyy_code"],
                    json.dumps(err),
                )

            await send_webhook(
                "discharge_rejected",
                {"ticket_number": ticket, "error": err},
            )

            send_error_email(ticket, f"EOPYY rejected discharge:\n\n{raw_response}")

        else:
            async with pool.acquire() as conn:
                await neon_retry(
                    conn,
                    conn.execute,
                    """
                    UPDATE discharges
                    SET status='error',
                        error_code=$3,
                        error_details=$4,
                        raw_response_a03=$2,
                        updated_at=NOW()
                    WHERE id=$1
                    """,
                    row_id,
                    raw_response,
                    err["eopyy_code"],
                    json.dumps(err),
                )

            await send_webhook(
                "worker_error",
                {"ticket_number": ticket, "error": err},
            )

            send_error_email(ticket, f"EOPYY returned discharge error:\n\n{raw_response}")

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"[{ticket}] Discharge processing error")

        async with pool.acquire() as conn:
            await neon_retry(
                conn,
                conn.execute,
                """
                UPDATE discharges
                SET status='error',
                    raw_response_a03=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                json.dumps({"error": error_msg}),
            )

        await send_webhook(
            "worker_error",
            {"ticket_number": ticket, "exception": error_msg},
        )

        send_error_email(ticket, error_msg)

# ---------------------------------------------------------
# MAIN WORKER LOOP
# ---------------------------------------------------------
async def worker_loop():
    logger.info("worker 🚀 HL7 Worker started")

    # shared asyncpg pool
    # Create pool with retry (Neon needs 1–2 seconds)
    pool = None
    for _ in range(10):
        try:
            pool = await asyncpg.create_pool(raw_url, ssl=ssl_ctx)
            break
        except Exception as e:
            logger.warning(f"Pool creation failed, retrying... {e}")
            await asyncio.sleep(1)

    if pool is None:
        raise RuntimeError("Failed to create asyncpg pool after retries")

    while True:
        try:
            db = get_new_session()

            # -----------------------------------------
            # PROCESS SINGLE ADMISSION JOBS FIRST
            # -----------------------------------------
            logger.error(f"WORKER_DATABASE_URL = {raw_url!r}")

            async with pool.acquire() as conn:
                schema = await conn.fetchval("SELECT current_schema;")
                logger.error(f"WORKER SCHEMA = {schema}")

                count = await conn.fetchval("SELECT COUNT(*) FROM admissions;")
                logger.error(f"WORKER sees {count} admissions")

            async with pool.acquire() as conn:
                row = await neon_retry(
                    conn,
                    conn.fetchrow,
                    """
                    SELECT *
                    FROM admissions
                    WHERE status = 'queued' OR status IS NULL OR status = ''
                     ORDER BY created_at ASC
                    LIMIT 1
                    """,
                )

            if row:
                await process_admission_row(pool, row)
                await asyncio.sleep(1)
                continue

            # -----------------------------------------
            # THEN PROCESS HL7Job (batch discharges)
            # -----------------------------------------
            try:
                result = await db.execute(
                    select(HL7Job)
                    .where(HL7Job.status == "queued")
                    .order_by(HL7Job.created_at)
                    .limit(1)
                )
            except Exception as exc:
                logger.exception("worker SQLAlchemy SELECT failed")

                if "InvalidCachedStatementError" in str(exc):
                    logger.warning("Worker ⚠️ Invalid cached statement — full engine reset next loop")
                    await asyncio.sleep(1)
                    continue

                raise

            job = result.scalar_one_or_none()

            if not job:
                await asyncio.sleep(2)
                continue

            logger.info(f"worker 📥 Processing job: {job.job_id}")

            job.status = "processing"
            await db.commit()

            start_hl7 = job.from_date.strftime("%Y%m%d000000")
            end_hl7 = job.to_date.strftime("%Y%m%d235959")

            async with pool.acquire() as conn:
                rows = await neon_retry(
                    conn,
                    conn.fetch,
                    """
                    SELECT *
                    FROM discharges
                    WHERE discharge_datetime BETWEEN $1 AND $2
                      AND installation_code = $3
                    ORDER BY discharge_datetime ASC
                    """,
                    start_hl7,
                    end_hl7,
                    job.installation_code,
                )

            discharges = [dict(r) for r in rows]

            total_amount = sum(r.get("amount_total", 0) for r in discharges)
            covered_amount = sum(r.get("amount_covered", 0) for r in discharges)
            patient_amount = sum(r.get("amount_patient", 0) for r in discharges)

            out_path = f"/tmp/worker{job.job_id}.hl7"

            await generate_hl7_file(
                discharges,
                out_path,
                job.installation_code,
                total_amount,
                covered_amount,
                patient_amount,
            )

            with open(out_path, "r", encoding="utf-8") as f:
                hl7_text = f.read()

            job.file_data = hl7_text
            job.result_file = None
            job.status = "worker completed"
            job.updated_at = datetime.datetime.utcnow()

            await db.commit()

            logger.info(f"worker 📤 Completed job: {job.job_id}")

        except Exception:
            logger.exception("Worker crashed")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(worker_loop())
