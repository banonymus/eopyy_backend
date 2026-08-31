import os
import ssl
import asyncio
import logging
import asyncpg
import datetime
from app.hl7_generator import generate_hl7_file
from hl7_builder_worker import build_hl7_discharge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hl7-worker")

raw_url = os.getenv("WORKER_DATABASE_URL")
if not raw_url:
    raise RuntimeError("WORKER_DATABASE_URL missing")

if "postgresql+asyncpg://" in raw_url:
    raw_url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
elif "postgres+asyncpg://" in raw_url:
    raw_url = raw_url.replace("postgres+asyncpg://", "postgres://")
logger.info(f"Worker DSN after cleanup: {raw_url}")


ssl_ctx = ssl.create_default_context()

import re
import httpx
from email_alerts import send_error_email
from hl7_builder_worker import build_hl7_message
from old_eopyy_client import submit_hl7

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
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(WEBHOOK_URL, json={"event": event_type, "data": payload})
        except Exception as e:
            logger.error(f"Webhook failed: {e}")

# ---------------------------------------------------------
# PROCESS ADMISSION (NO DB)
# ---------------------------------------------------------
async def process_admission_row(pool, row):
    ticket = row["ticket_number"]
    logger.info(f"[{ticket}] Processing ADMISSION (no DB mode)")

    try:
        data = dict(row)

        # 1. Build HL7
        hl7 = build_hl7_message(data)

        # 2. Send SOAP
        raw_response = submit_hl7(hl7,"A01")

        # 3. Parse ACK
        msa_code, message_id, err = parse_hl7_response(raw_response)

        logger.info(f"[{ticket}] HL7 MSA={msa_code}, message_id={message_id}, ERR={err}")

        # Optional webhook notifications
        if msa_code == "AA":
            await send_webhook("admission_completed", {
                "ticket_number": ticket,
                "message_id": message_id
            })

        elif msa_code == "AR":
            await send_webhook("admission_rejected", {
                "ticket_number": ticket,
                "error": err
            })
            send_error_email(ticket, f"EOPYY rejected admission:\n\n{raw_response}")

        else:
            await send_webhook("worker_error", {
                "ticket_number": ticket,
                "error": err
            })
            send_error_email(ticket, f"EOPYY returned error:\n\n{raw_response}")

        # ⭐ Return result directly (NO DB)
        return {
            "ticket_number": ticket,
            "status": msa_code,
            "hl7": hl7,
            "raw_response": raw_response,
            "error": err,
        }

    except Exception as e:
        logger.exception(f"[{ticket}] Admission processing error")
        return {
            "ticket_number": ticket,
            "status": "error",
            "hl7": None,
            "raw_response": None,
            "error": str(e),
        }

# ---------------------------------------------------------
# PROCESS DISCHARGE (NO DB MODE)
# ---------------------------------------------------------
async def process_discharge_row(pool, row):
    ticket = row["ticket_number"]
    logger.info(f"[{ticket}] Processing DISCHARGE (no DB mode)")

    try:
        data = dict(row)

        # 1. Build HL7 A03
        hl7 = build_hl7_message(data)

        # 2. Send SOAP
        raw_response = submit_hl7(hl7,"A03")

        # 3. Parse ACK
        msa_code, message_id, err = parse_hl7_response(raw_response)

        logger.info(f"[{ticket}] HL7 MSA={msa_code}, message_id={message_id}, ERR={err}")

        # Optional webhook notifications
        if msa_code == "AA":
            await send_webhook("discharge_completed", {
                "ticket_number": ticket,
                "message_id": message_id
            })

        elif msa_code == "AR":
            await send_webhook("discharge_rejected", {
                "ticket_number": ticket,
                "error": err
            })
            send_error_email(ticket, f"EOPYY rejected discharge:\n\n{raw_response}")

        else:
            await send_webhook("worker_error", {
                "ticket_number": ticket,
                "error": err
            })
            send_error_email(ticket, f"EOPYY returned discharge error:\n\n{raw_response}")

        # ⭐ Return result directly (NO DB writes)
        return {
            "ticket_number": ticket,
            "status": msa_code,
            "hl7": hl7,
            "raw_response": raw_response,
            "error": err,
        }

    except Exception as e:
        logger.exception(f"[{ticket}] Discharge processing error")
        return {
            "ticket_number": ticket,
            "status": "error",
            "hl7": None,
            "raw_response": None,
            "error": str(e),
        }

# ---------------------------------------------------------
# PROCESS DISCHARGE (NO DB MODE)
# ---------------------------------------------------------
async def process_discharge_row(pool, row):
    ticket = row["ticket_number"]
    logger.info(f"[{ticket}] Processing DISCHARGE (no DB mode)")

    try:
        data = dict(row)

        # 1. Build HL7 A03
        hl7 = build_hl7_discharge(data)

        # 2. Send SOAP (same endpoint as A03)
        raw_response = submit_hl7(hl7,"A03")

        # 3. Parse ACK
        msa_code, message_id, err = parse_hl7_response(raw_response)

        logger.info(f"[{ticket}] HL7 MSA={msa_code}, message_id={message_id}, ERR={err}")

        # Optional webhook notifications
        if msa_code == "AA":
            await send_webhook("discharge_completed", {
                "ticket_number": ticket,
                "message_id": message_id
            })

        elif msa_code == "AR":
            await send_webhook("discharge_rejected", {
                "ticket_number": ticket,
                "error": err
            })
            send_error_email(ticket, f"EOPYY rejected discharge:\n\n{raw_response}")

        else:
            await send_webhook("worker_error", {
                "ticket_number": ticket,
                "error": err
            })
            send_error_email(ticket, f"EOPYY returned discharge error:\n\n{raw_response}")

        # ⭐ Return result directly (NO DB writes)
        return {
            "ticket_number": ticket,
            "status": msa_code,
            "hl7": hl7,
            "raw_response": raw_response,
            "error": err,
        }

    except Exception as e:
        logger.exception(f"[{ticket}] Discharge processing error")
        return {
            "ticket_number": ticket,
            "status": "error",
            "hl7": None,
            "raw_response": None,
            "error": str(e),
        }

# ---------------------------------------------------------
# WORKER LOOP (pure asyncpg) INVOICES MONTHLY
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
            total_amount = 0
            covered_amount = 0
            patient_amount = 0

            for r in discharges:
                diags = r.get("diagnoses") or []
                for d in diags:
                    total_amount += float(d.get("total_amount", 0) or 0)
                    covered_amount += float(d.get("covered_amount", 0) or 0)
                    patient_amount += float(d.get("patient_amount", 0) or 0)


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

# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    asyncio.run(worker_loop())
