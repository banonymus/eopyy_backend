# routes/discharges.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder

from database import get_session
from models import Admission, Discharge
from schemas import DischargeCreate
from app.worker_batch import process_discharge_row

router = APIRouter()

@router.get("/discharges/ping")
async def ping():
    print(">>> PING WORKS <<<")
    return {"ok": True}



@router.post("/discharges")
async def create_or_process_discharge(
    data: DischargeCreate,
    db: AsyncSession = Depends(get_session)
):
    print(">>> DISCHARGE ENDPOINT ENTERED <<<")
    if not data.ticket_number:
        raise HTTPException(
            status_code=422,
            detail="ticket_number is required"
        )

    # 1️⃣ Βρες το admission με ίδιο ticket_number
    admission_result = await db.execute(
        select(Admission).where(Admission.ticket_number == data.ticket_number)
    )
    admission = admission_result.scalar_one_or_none()

    if not admission:
        raise HTTPException(
            status_code=404,
            detail=f"No admission found for ticket_number {data.ticket_number}"
        )
    # ⭐ READ discharge_ticket_number FROM ADMISSION
    discharge_ticket_number = admission.discharge_ticket_number

    # 2️⃣ Auto-fill discharge fields from admission
    auto_fields = {
        "profile_id": admission.profile_id,
        "installation_code": admission.installation_code,
        "location_code": admission.location_code,
        "operator_id": admission.operator_id,
        "visit_number": admission.visit_number,
        "admit_datetime": admission.admit_datetime,
        "doctor_amka": admission.doctor_amka,
        "amka": admission.amka,
        "first_name": admission.first_name,
        "last_name": admission.last_name,
        "sex_val": admission.sex_val,
        "country_code": admission.country_code,
        "icd10_code": admission.icd10_code,
        "icd10_desc": admission.icd10_desc,
        "icd10_date": admission.icd10_date,

        # ⭐ HL7 ONLY — MUST BE SENT TO WORKER
        "admission_alt_visit_id": admission.alt_visit_id,
        # ⭐ NEW FIELD — USED IN A03 HL7 BUILDER
        "discharge_ticket_number": discharge_ticket_number
    }

    # Combine user input + auto-fill
    discharge_data = data.dict()
    discharge_data.update(auto_fields)

    # ----------------------------------------------------
    # ⭐ A) ORM DATA — MUST NOT CONTAIN admission_alt_visit_id
    # ----------------------------------------------------
    discharge_data_for_db = discharge_data.copy()

    discharge_data_for_db.pop("visit_number", None)
    discharge_data_for_db.pop("admission_ticket_number", None)
    discharge_data_for_db.pop("alt_visit_id", None)

    # ⭐ REMOVE ONLY FROM ORM
    discharge_data_for_db.pop("admission_alt_visit_id", None)

    #print(">>> DISCHARGE DATA FOR DB:", discharge_data_for_db)

    # 3️⃣ Save discharge to DB
    result = await db.execute(
        select(Discharge).where(Discharge.ticket_number == data.ticket_number)
    )
    existing = result.scalar_one_or_none()

    if existing:
        for field, value in discharge_data_for_db.items():
            setattr(existing, field, value)
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        saved_record = existing
    else:
        dis = Discharge(**discharge_data_for_db)
        db.add(dis)
        await db.commit()
        await db.refresh(dis)
        saved_record = dis
    #print(">>> ABOUT TO CREATE ORM OBJECT")
    #print(">>> CALLING WORKER WITH:", discharge_data)

    # ----------------------------------------------------
    # ⭐ B) WORKER DATA — MUST CONTAIN admission_alt_visit_id
    # ----------------------------------------------------
    hl7_result = await process_discharge_row(None, discharge_data)

    # 5️⃣ Return result to Postman
    return {
        "message": "Discharge saved to database",
        "ticket_number": saved_record.ticket_number,
        "record": jsonable_encoder(saved_record),

        "hl7_status": hl7_result["status"],
        "hl7_message": hl7_result["hl7"],
        "hl7_raw_response": hl7_result["raw_response"],
        "hl7_error": hl7_result["error"]
    }
