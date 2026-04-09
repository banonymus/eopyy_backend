
# main.py
import os
import logging
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import get_session, engine
from models import Base, Admission
from schemas import AdmissionCreate, AdmissionRead, AdmissionUpdate
from config import EXPECTED_KEY as CONFIG_EXPECTED_KEY, API_HEADER as CONFIG_API_HEADER

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# -------------------------
# Configuration (single source of truth)
# -------------------------
EXPECTED_KEY: Optional[str] = os.getenv("API_KEY") or CONFIG_EXPECTED_KEY
API_HEADER: str = os.getenv("API_HEADER") or CONFIG_API_HEADER or "x-api-key"

# -------------------------
# Optional route dump for debugging
# Enable by setting environment variable ENABLE_ROUTE_DUMP=1 in Render
# -------------------------
if os.getenv("ENABLE_ROUTE_DUMP") == "1":

    @app.on_event("startup")
    async def startup_routes_dump():
        for route in app.routes:
            logger.info("Route: %s %s", getattr(route, "methods", None), route.path)

# -------------------------
# Logging middleware
# -------------------------
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    # use configured header name (case-insensitive)
    api_key = request.headers.get(API_HEADER) or request.headers.get(API_HEADER.upper()) or request.headers.get("X-API-Key")
    if EXPECTED_KEY and api_key != EXPECTED_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return await call_next(request)


# -------------------------
# API key middleware
# -------------------------
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # Public endpoints that don't require API key
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    api_key = request.headers.get(API_HEADER) or request.headers.get(API_HEADER.upper()) or request.headers.get("X-API-Key")
    if EXPECTED_KEY and api_key != EXPECTED_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return await call_next(request)

# -------------------------
# DB startup: create tables
# -------------------------
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# -------------------------
# Admissions endpoints
# POST /admissions implements upsert: create if missing, update if exists
# -------------------------
@app.post("/admissions", response_model=AdmissionRead)
async def create_or_upsert_admission(data: AdmissionCreate, db: AsyncSession = Depends(get_session)):
    """
    Upsert behavior:
    - If an admission with the same ticket_number exists, update it with provided fields and return 200.
    - Otherwise create a new admission and return 201.
    """
    if not data.ticket_number:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ticket_number is required")

    # Try to find existing by ticket_number
    result = await db.execute(select(Admission).where(Admission.ticket_number == data.ticket_number))
    existing = result.scalar_one_or_none()

    if existing:
        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing  # 200 OK

    # Create new
    adm = Admission(**data.dict())
    db.add(adm)
    try:
        await db.commit()
    except IntegrityError:
        # Race condition: another process created it concurrently
        await db.rollback()
        result = await db.execute(select(Admission).where(Admission.ticket_number == data.ticket_number))
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create admission")
    await db.refresh(adm)
    # Return 201 for newly created resource
    return adm

# -------------------------
# List admissions
# -------------------------
@app.get("/admissions", response_model=list[AdmissionRead])
async def list_admissions(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Admission).order_by(Admission.id.desc()))
    return result.scalars().all()

# -------------------------
# Health and debug
# -------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/debug-version")
def debug_version():
    import models  # local import to avoid circular issues at module import time
    return {"fields": list(models.Admission.__table__.columns.keys())}

# -------------------------
# Update admission by internal id (keeps explicit update endpoint)
# -------------------------
@app.patch("/admissions/id/{admission_id}", response_model=AdmissionRead)
async def update_admission(
    admission_id: int,
    data: AdmissionUpdate,
    db: AsyncSession = Depends(get_session),
):
    logger.info("update_admission called with id=%s", admission_id)
    result = await db.execute(select(Admission).where(Admission.id == admission_id))
    adm = result.scalar_one_or_none()
    if not adm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(adm, field, value)

    db.add(adm)
    await db.commit()
    await db.refresh(adm)
    return adm



from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session
from models import Discharge
from schemas import DischargeCreate, DischargeRead, DischargeUpdate

app = FastAPI()  # if already defined, just add the routes below

@app.post("/discharges", response_model=DischargeRead)
async def create_discharge(data: DischargeCreate, db: AsyncSession = Depends(get_session)):
    dis = Discharge(**data.dict())
    db.add(dis)
    await db.commit()
    await db.refresh(dis)
    return dis

@app.get("/discharges", response_model=list[DischargeRead])
async def list_discharges(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Discharge).order_by(Discharge.id.desc()))
    return result.scalars().all()

@app.get("/discharges/by-ticket/{ticket_number}", response_model=DischargeRead)
async def get_discharge_by_ticket(ticket_number: str, db: AsyncSession = Depends(get_session)):
    q = await db.execute(select(Discharge).where(Discharge.ticket_number == ticket_number))
    dis = q.scalars().first()
    if not dis:
        raise HTTPException(status_code=404, detail="Discharge not found")
    return dis

@app.patch("/discharges/by-ticket/{ticket_number}", response_model=DischargeRead)
async def patch_discharge_by_ticket(
    ticket_number: str,
    payload: DischargeUpdate,
    db: AsyncSession = Depends(get_session),
):
    q = await db.execute(select(Discharge).where(Discharge.ticket_number == ticket_number))
    dis = q.scalars().first()
    if not dis:
        raise HTTPException(status_code=404, detail="Discharge not found")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dis, field, value)

    db.add(dis)
    await db.commit()
    await db.refresh(dis)
    return dis

@app.get("/discharges/{discharge_id}", response_model=DischargeRead)
async def get_discharge_by_id(discharge_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Discharge).where(Discharge.id == discharge_id))
    dis = result.scalar_one_or_none()
    if not dis:
        raise HTTPException(status_code=404, detail="Discharge not found")
    return dis
