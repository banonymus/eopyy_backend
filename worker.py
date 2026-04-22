import asyncio
import asyncpg
import os
import json
import logging
import re
import httpx

from hl7_builder_worker import build_hl7_message
from old_eopyy_client import submit_hl7
from discarge_eopyy_client import submit_discarge_hl7
from email_alerts import send_error_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eopyy-worker")

DB_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")


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
# PROCESS ADMISSION
# ---------------------------------------------------------
async def process_admission_row(conn, row):
    row_id = row["id"]
    ticket = row["ticket_number"]

    logger.info(f"[{ticket}] Processing ADMISSION (id={row_id})")

    await conn.execute(
        "UPDATE admissions SET status='processing', updated_at=NOW() WHERE id=$1",
        row_id,
    )

    try:
        data = dict(row)

        hl7 = build_hl7_message(data)
        await conn.execute(
            "UPDATE admissions SET hl7=$2, updated_at=NOW() WHERE id=$1",
            row_id,
            hl7,
        )

        raw_response = submit_hl7(hl7)
        msa_code, message_id, err = parse_hl7_response(raw_response)

        if msa_code == "AA":
            await conn.execute(
                """
                UPDATE admissions
                SET status='completed',
                    raw_response=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                raw_response,
            )

            await send_webhook("admission_completed", {
                "ticket_number": ticket,
                "message_id": message_id,
            })

        elif msa_code == "AR":
            await conn.execute(
                """
                UPDATE admissions
                SET status='rejected',
                    error_code=$3,
                    error_details=$4,
                    raw_response=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                raw_response,
                err["eopyy_code"],
                json.dumps(err),
            )

            await send_webhook("admission_rejected", {
                "ticket_number": ticket,
                "error": err,
            })

            send_error_email(ticket, f"EOPYY rejected admission:\n\n{raw_response}")

        else:
            await conn.execute(
                """
                UPDATE admissions
                SET status='error',
                    error_code=$3,
                    error_details=$4,
                    raw_response=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                raw_response,
                err["eopyy_code"],
                json.dumps(err),
            )

            await send_webhook("worker_error", {
                "ticket_number": ticket,
                "error": err,
            })

            send_error_email(ticket, f"EOPYY returned error:\n\n{raw_response}")

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"[{ticket}] Admission processing error")

        await conn.execute(
            """
            UPDATE admissions
            SET status='error',
                raw_response=$2,
                updated_at=NOW()
            WHERE id=$1
            """,
            row_id,
            json.dumps({"error": error_msg}),
        )

        await send_webhook("worker_error", {
            "ticket_number": ticket,
            "exception": error_msg,
        })

        send_error_email(ticket, error_msg)


# ---------------------------------------------------------
# PROCESS DISCHARGE
# ---------------------------------------------------------
async def process_discharge_row(conn, row):
    row_id = row["id"]
    ticket = row["ticket_number"]

    logger.info(f"[{ticket}] Processing DISCHARGE (id={row_id})")

    await conn.execute(
        "UPDATE discharges SET status='processing', updated_at=NOW() WHERE id=$1",
        row_id,
    )

    try:
        data = dict(row)

        hl7 = build_hl7_message(data)
        await conn.execute(
            "UPDATE discharges SET hl7=$2, updated_at=NOW() WHERE id=$1",
            row_id,
            hl7,
        )

        raw_response = submit_discarge_hl7(hl7)
        msa_code, message_id, err = parse_hl7_response(raw_response)

        if msa_code == "AA":
            await conn.execute(
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

            await send_webhook("discharge_completed", {
                "ticket_number": ticket,
                "message_id": message_id,
            })

        elif msa_code == "AR":
            await conn.execute(
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

            await send_webhook("discharge_rejected", {
                "ticket_number": ticket,
                "error": err,
            })

            send_error_email(ticket, f"EOPYY rejected discharge:\n\n{raw_response}")

        else:
            await conn.execute(
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

            await send_webhook("worker_error", {
                "ticket_number": ticket,
                "error": err,
            })

            send_error_email(ticket, f"EOPYY returned discharge error:\n\n{raw_response}")

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"[{ticket}] Discharge processing error")

        await conn.execute(
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

        await send_webhook("worker_error", {
            "ticket_number": ticket,
            "exception": error_msg,
        })

        send_error_email(ticket, error_msg)


# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------
async def worker_loop():
    conn = await asyncpg.connect(DB_URL)
    logger.info("Worker connected to DB")

    try:
        while True:

            await conn.execute("""
                UPDATE worker_heartbeat
                SET last_beat = NOW()
                WHERE id = 1
            """)

            # Fetch pending admissions
            admissions = await conn.fetch("""
                SELECT * FROM admissions
                WHERE status='pending'
                ORDER BY created_at
                LIMIT 20
            """)

            # Fetch pending discharges
            discharges = await conn.fetch("""
                SELECT * FROM discharges
                WHERE status='pending'
                ORDER BY created_at
                LIMIT 20
            """)

            if not admissions and not discharges:
                await asyncio.sleep(5)
                continue

            for row in admissions:
                await process_admission_row(conn, row)

            for row in discharges:
                await process_discharge_row(conn, row)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(worker_loop())
