from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------
# 1. ASYNC DATABASE ENGINE (Neon)
# ---------------------------------------------------------
DATABASE_URL = "postgresql+asyncpg://<USERNAME>:<PASSWORD>@<HOST>/<DBNAME>"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# ---------------------------------------------------------
# 2. FETCH DISCHARGES (όπως μου έστειλες)
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
