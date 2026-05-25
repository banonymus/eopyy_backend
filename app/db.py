import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------
# 1. LOAD DATABASE URL FROM ENV
# ---------------------------------------------------------
raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    raise RuntimeError("❌ DATABASE_URL is missing from environment variables")

# ---------------------------------------------------------
# 2. REMOVE sslmode=require (Neon adds it automatically)
# ---------------------------------------------------------
if "sslmode=" in raw_url:
    raw_url = raw_url.split("?")[0]

# ---------------------------------------------------------
# 3. CREATE SSL CONTEXT FOR ASYNCPG
# ---------------------------------------------------------
ssl_ctx = ssl.create_default_context()

# If Neon requires insecure SSL (rare), uncomment:
# ssl_ctx.check_hostname = False
# ssl_ctx.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------
# 4. CREATE ASYNC ENGINE WITH SSL
# ---------------------------------------------------------
engine = create_async_engine(
    raw_url,
    echo=False,
    future=True,
    connect_args={"ssl": ssl_ctx}
)

AsyncSessionLocal = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# ---------------------------------------------------------
# 5. FETCH DISCHARGES
# ---------------------------------------------------------
async def fetch_discharges(session, start_date, end_date):
    query = """
    SELECT
        id,
        ticket_number,
        last_name,
        first_name,
        amka,
        dob_hl7,
        sex_val,
        location_code,
        doctor_amka,
        admit_datetime,
        discharge_datetime,
        icd10_code,
        icd10_desc,
        icd10_date,
        installation_code,
        operator_id
    FROM discharges
    WHERE discharge_datetime >= :start_date
      AND discharge_datetime <= :end_date
    ORDER BY discharge_datetime ASC
    """

    result = await session.execute(
        query,
        {"start_date": start_date, "end_date": end_date}
    )

    rows = result.fetchall()
    discharges = []

    for r in rows:
        discharges.append({
            "patient_id": r.id,
            "ticket_number": r.ticket_number,
            "lastname": r.last_name,
            "firstname": r.first_name,
            "amka": r.amka,
            "dob": r.dob_hl7,
            "gender": "1" if r.sex_val == "M" else "2",
            "location_code": r.location_code,
            "doctor_amka": r.doctor_amka,
            "admission_time": r.admit_datetime,
            "discharge_time": r.discharge_datetime,
            "diagnosis_code": r.icd10_code,
            "diagnosis_desc": r.icd10_desc,
            "diagnosis_date": r.icd10_date,
            "procedure_code": "6^Ο16Α",
            "price": 0.00,
            "installation_code": r.installation_code,
            "operator_id": r.operator_id,
        })

    return discharges
