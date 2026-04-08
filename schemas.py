# schemas.py
from urllib.request import Request

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from fastapi import BackgroundTasks, HTTPException, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import EXPECTED_KEY
from database import get_session, engine
from main import app
from models import Admission, Base
from schemas import AdmissionRead, AdmissionUpdate
from schemas import AdmissionCreate, AdmissionRead
import requests
import os

"""
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # Skip docs endpoints if you want (optional)
    if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
        return await call_next(request)

    key = request.headers.get(API_HEADER)
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return await call_next(request)
"""
@app.middleware("http")
async def verify_api_key(request: Request, call_next):

    # --- BYPASS PUBLIC ROUTES HERE ---
    if request.url.path in ["/health", "/docs", "/openapi.json"]:
        return await call_next(request)
    # ---------------------------------

    api_key = request.headers.get("X-API-Key")
    if api_key != EXPECTED_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return await call_next(request)




@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post("/admissions", response_model=AdmissionRead)
async def create_admission(data: AdmissionCreate, db: AsyncSession = Depends(get_session)):
    adm = Admission(**data.dict())
    db.add(adm)
    await db.commit()
    await db.refresh(adm)
    return adm



@app.get("/admissions", response_model=list[AdmissionRead])
async def list_admissions(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Admission).order_by(Admission.id.desc()))
    return result.scalars().all()


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/debug-version")
def debug_version():
    import models
    return {"fields": list(models.Admission.__table__.columns.keys())}



class AdmissionBase(BaseModel):
    ticket_number: Optional[str] = None
    profile_id: Optional[str] = None
    installation_code: Optional[str] = None
    operator_id: Optional[str] = None

    last_name: Optional[str] = None
    first_name: Optional[str] = None
    country_code: Optional[str] = None

    phone1_area: Optional[str] = None
    phone1_number: Optional[str] = None

    amka: Optional[str] = None
    pid31: Optional[str] = None

    dob_hl7: Optional[str] = None
    sex_val: Optional[str] = None

    pid_taut: Optional[str] = None
    pid_ekaa: Optional[str] = None
    pid_eidik: Optional[str] = None
    pid_expiry: Optional[str] = None
    pid_foreas: Optional[str] = None

    doctor_amka: Optional[str] = None
    doctor_last: Optional[str] = None
    doctor_first: Optional[str] = None

    visit_number: Optional[str] = None
    admit_datetime: Optional[str] = None
    location_code: Optional[str] = None

    icd10_code: Optional[str] = None
    icd10_desc: Optional[str] = None
    icd10_date: Optional[str] = None

    nk1_ama: Optional[str] = None

    hl7: Optional[str] = None
    raw_response: Optional[str] = None
    status: Optional[str] = None

    @validator("ticket_number")
    def ticket_length(cls, v):
        if v is None:
            return v
        if not (13 <= len(v) <= 20):
            raise ValueError("ticket_number should be 13 digits (or up to DB length)")
        return v

    @validator("profile_id")
    def profile_id_len(cls, v):
        if v is None:
            return v
        if len(v) != 20:
            # allow but warn via validation error
            raise ValueError("profile_id must be exactly 20 characters")
        return v

class AdmissionCreate(AdmissionBase):
    """
    Use a permissive create model so the UI can send the full payload.
    If you want stricter creation rules, make required fields non-optional here.
    """
    pass

class AdmissionRead(AdmissionBase):
    id: int
    created_at: Optional[datetime] = None

    # discharge fields
    discharge_datetime: Optional[str] = None
    discharge_result: Optional[str] = None
    raw_response_a03: Optional[str] = None

    class Config:
        orm_mode = True

class AdmissionUpdate(BaseModel):
    """
    PATCH payload for updating discharge fields (used by Streamlit PATCH).
    """
    discharge_datetime: Optional[str] = None
    discharge_result: Optional[str] = None
    raw_response_a03: Optional[str] = None


# PATCH /admissions/{ticket_number} — update discharge fields
@app.patch("/admissions/{ticket_number}", response_model=AdmissionRead)
async def update_admission(
    ticket_number: str,
    payload: AdmissionUpdate,
    db: AsyncSession = Depends(get_session)
):
    q = await db.execute(select(Admission).where(Admission.ticket_number == ticket_number))
    adm = q.scalars().first()
    if not adm:
        raise HTTPException(status_code=404, detail="Admission not found")

    if payload.discharge_datetime is not None:
        adm.discharge_datetime = payload.discharge_datetime
    if payload.discharge_result is not None:
        adm.discharge_result = payload.discharge_result
    if payload.raw_response_a03 is not None:
        adm.raw_response_a03 = payload.raw_response_a03

    db.add(adm)
    await db.commit()
    await db.refresh(adm)
    return adm
