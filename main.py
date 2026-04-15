# main.py
import os
import logging
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import get_session, engine
from models import Base, Admission, Discharge
from schemas import (
    AdmissionCreate,
    AdmissionRead,
    AdmissionUpdate,
    DischargeCreate,
    DischargeRead,
    DischargeUpdate,
)
from config import EXPECTED_KEY as CONFIG_EXPECTED_KEY, API_HEADER as CONFIG_API_HEADER

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# -------------------------
# Configuration (single source of truth)
# -------------------------
EXPECTED_KEY: Optional[str] = os.getenv("API_KEY") or CONFIG_EXPECTED_KEY
API_HEADER: str = (os.getenv("API_HEADER") or CONFIG_API_HEADER or "X-API-Key")

# -------------------------
# Single middleware to verify API key (case-insensitive)
# -------------------------
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # allow public endpoints
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    # check header case-insensitively and fall back to common names
    api_key = (
        request.headers.get(API_HEADER)
        or request.headers.get(API_HEADER.lower())
        or request.headers.get(API_HEADER.upper())
        or request.headers.get("X-API-Key")
        or request.headers.get("x-api-key")
    )

    if EXPECTED_KEY and api_key != EXPECTED_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return await call_next(request)


# -------------------------
# Optional route dump for debugging
# Enable by setting environment variable ENABLE_ROUTE_DUMP=1 in Render
# -------------------------
if os.getenv("ENABLE_ROUTE_DUMP") == "1":

    @app.on_event("startup")
    async def startup_routes_dump():
        logger.info("Resolved main.py: %s", __file__)
        for route in app.routes:
            logger.info("Route: %s %s", getattr(route, "methods", None), route.path)


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
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(adm))


# -------------------------
# List admissions
# -------------------------
@app.get("/admissions", response_model=List[AdmissionRead])
async def list_admissions(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Admission).order_by(Admission.id.desc()))
    return result.scalars().all()


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


# -------------------------
# Health and debug
# -------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug-version")
def debug_version():
    # local import to avoid circular issues at module import time
    import models  # noqa: F401
    return {"fields": list(models.Admission.__table__.columns.keys())}


# Optional header debug endpoint (temporary; remove in production)
@app.post("/_debug-headers")
async def debug_headers(request: Request):
    headers = dict(request.headers)
    logger.info("Incoming headers for debug: %s", headers)
    return {"received_headers": list(headers.keys())}


# -------------------------
# Discharges endpoints
# -------------------------
@app.post("/discharges", response_model=DischargeRead)
async def create_discharge(data: DischargeCreate, db: AsyncSession = Depends(get_session)):
    dis = Discharge(**data.dict())
    db.add(dis)
    await db.commit()
    await db.refresh(dis)
    return dis


@app.get("/discharges", response_model=List[DischargeRead])
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

from sqlalchemy import func

@app.get("/monitoring/summary")
async def monitoring_summary(db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM admissions
        GROUP BY status
        """
    )
    rows = q.fetchall()
    return {
        "statuses": [{ "status": r[0], "count": r[1] } for r in rows]
    }

from sqlalchemy import text

@app.get("/monitoring/last-errors")
async def monitoring_last_errors(limit: int = 20, db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        text("""
            SELECT id, ticket_number, status, raw_response, updated_at
            FROM admissions
            WHERE status = 'error'
            ORDER BY updated_at DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    rows = q.fetchall()

    return [
        {
            "id": r.id,
            "ticket_number": r.ticket_number,
            "status": r.status,
            "raw_response": r.raw_response,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]
