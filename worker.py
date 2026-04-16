# worker.py
import asyncio
import asyncpg
import os
import json
import logging
import re

from hl7_builder_worker import build_hl7_message
from old_eopyy_client import submit_hl7
from discarge_eopyy_client import submit_discarge_hl7
from email_alerts import send_error_email


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eopyy-worker")

DB_URL = os.getenv("DATABASE_URL")


# ---------------------------------------------------------
# HL7 PARSER (MSA + ERR)
# ---------------------------------------------------------
def parse_hl7_response(raw):
    """
    Extract MSA code, message ID, and ERR details from HL7.
    """
    # MSA|AA|12345  or  MSA|AR|12345  or  MSA|AE|12345
    msa_match = re.search(r"MSA\|([A-Z]{2})\|([0-9]+)", raw)
    msa_code = msa_match.group(1) if msa_match else None
    message_id = msa_match.group(2) if msa_match else None

    # ERR||PID^19|102|E|331
    err_match = re.search(r"ERR\|\|([A-Z0-9\^]+)\|([0-9]+)\|([A-Z])\|([0-9]+)", raw)
    err = {
        "location": err_match.group(1) if err_match else None,
        "code": err_match.group(2) if err_match else None,
        "severity": err_match.group(3) if err_match else None,
        "eopyy_code": err_match.group(4) if err_match else None,
    }

    return msa_code, message_id, err


async def process_row(conn, row):
    row_id = row["id"]
    ticket = row["ticket_number"]

    logger.info(f"[{ticket}] Start processing (id={row_id})")

    # mark as processing
    await conn.execute(
        """
        UPDATE admissions
        SET status='processing', updated_at=NOW()
        WHERE id=$1
        """,
        row_id,
    )

    try:
        data = dict(row)

        # 1. Build HL7 (A01 ή A03)
        hl7 = build_hl7_message(data)
        logger.info(f"[{ticket}] HL7 built, length={len(hl7)}")

        await conn.execute(
            """
            UPDATE admissions
            SET hl7=$2, updated_at=NOW()
            WHERE id=$1
            """,
            row_id,
            hl7,
        )

        # 2. Submit to EOPYY
        if data.get("discharge_datetime"):
            logger.info(f"[{ticket}] Submitting DISCHARGE (A03) to EOPYY")
            raw_response = submit_discarge_hl7(hl7)
            response_field = "raw_response_a03"
        else:
            logger.info(f"[{ticket}] Submitting ADMISSION (A01) to EOPYY")
            raw_response = submit_hl7(hl7)
            response_field = "raw_response"

        # ---------------------------------------------------------
        # 3. Parse HL7 response (NEW LOGIC)
        # ---------------------------------------------------------
        msa_code, message_id, err = parse_hl7_response(raw_response)
        logger.info(f"[{ticket}] HL7 MSA={msa_code}, ERR={err}")

        # ---------------------------------------------------------
        # 4. Save result based on MSA code (NEW LOGIC)
        # ---------------------------------------------------------
        if msa_code == "AA":
            # SUCCESS
            await conn.execute(
                f"""
                UPDATE admissions
                SET status='completed',
                    {response_field}=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                raw_response,
            )
            logger.info(f"[{ticket}] Completed successfully")

        elif msa_code == "AR":
            # REJECTED
            await conn.execute(
                f"""
                UPDATE admissions
                SET status='rejected',
                    error_code=$3,
                    error_details=$4,
                    {response_field}=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                raw_response,
                err["eopyy_code"],
                json.dumps(err, ensure_ascii=False),
            )
            logger.warning(f"[{ticket}] Rejected by EOPYY")
            send_error_email(ticket, f"EOPYY rejected the admission:\n\n{raw_response}")

        else:
            # ERROR (AE or unknown)
            await conn.execute(
                f"""
                UPDATE admissions
                SET status='error',
                    error_code=$3,
                    error_details=$4,
                    {response_field}=$2,
                    updated_at=NOW()
                WHERE id=$1
                """,
                row_id,
                raw_response,
                err["eopyy_code"],
                json.dumps(err, ensure_ascii=False),
            )
            logger.error(f"[{ticket}] Error from EOPYY")
            send_error_email(ticket, f"EOPYY returned an error:\n\n{raw_response}")

    except Exception as e:
        error_msg = str(e)

        logger.exception(f"[{ticket}] Error during processing")

        send_error_email(ticket, error_msg)

        await conn.execute(
            """
            UPDATE admissions
            SET status='error',
                raw_response=$2,
                updated_at=NOW()
            WHERE id=$1
            """,
            row_id,
            json.dumps({"error": error_msg}, ensure_ascii=False),
        )


async def worker_loop():
    conn = await asyncpg.connect(DB_URL)
    logger.info("Worker connected to DB")

    try:
        while True:
            rows = await conn.fetch(
                """
                SELECT * FROM admissions
                WHERE status='pending'
                ORDER BY created_at
                LIMIT 20
                """
            )

            # HEARTBEAT
            await conn.execute("""
                UPDATE worker_heartbeat
                SET last_beat = NOW()
                WHERE id = 1
            """)

            if not rows:
                await asyncio.sleep(5)
                continue

            logger.info(f"Found {len(rows)} pending rows")

            for row in rows:
                await process_row(conn, row)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(worker_loop())
