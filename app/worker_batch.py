import asyncio
import json
import os
import asyncpg
from app.hl7_generator import generate_hl7_file

QUEUE_DIR = "/tmp/hl7_queue"
os.makedirs(QUEUE_DIR, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL")


async def process_job(job):
    start_date = job["start_date"]   # already HL7 timestamp
    end_date = job["end_date"]       # already HL7 timestamp

    query = """
    SELECT
        ticket_number,
        amka,
        lastname,
        firstname,
        dob,
        gender,
        address,
        city,
        postal,
        phone,
        afm,
        patient_id,
        installation_code,
        location_code,
        doctor_amka,
        diagnosis_code,
        diagnosis_desc,
        procedure_code,
        price,
        admit_datetime AS admission_time,
        discharge_datetime AS discharge_time,
        operator_id
    FROM discharges
    WHERE discharge_datetime BETWEEN $1 AND $2
    ORDER BY discharge_datetime ASC
    """

    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(query, start_date, end_date)
    await conn.close()

    discharges = [dict(r) for r in rows]

    out_path = f"/tmp/{job['job_id']}.hl7"
    await generate_hl7_file(discharges, out_path)

    return out_path


async def worker_loop():
    print("🚀 Batch worker started. Watching queue:", QUEUE_DIR)

    while True:
        try:
            files = [f for f in os.listdir(QUEUE_DIR) if f.endswith(".json")]

            if not files:
                await asyncio.sleep(2)
                continue

            for file in files:
                job_path = os.path.join(QUEUE_DIR, file)

                try:
                    with open(job_path, "r") as f:
                        job = json.load(f)

                    print(f"📥 Processing job: {job['job_id']}")

                    out_path = await process_job(job)

                    print(f"📤 HL7 file created: {out_path}")

                    os.remove(job_path)

                except Exception as e:
                    print("❌ Error processing job:", e)

        except Exception as e:
            print("🔥 Worker loop error:", e)

        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(worker_loop())
