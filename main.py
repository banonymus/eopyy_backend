# main.py
import os
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_session, engine
from models import Base, Admission
from schemas import AdmissionCreate, AdmissionRead, AdmissionUpdate
from config import EXPECTED_KEY, API_HEADER  # <- import from config
import logging
logger = logging.getLogger("uvicorn.error")


app = FastAPI()

API_KEY = EXPECTED_KEY

API_KEY = os.getenv("API_KEY")  # loaded from Render env vars
API_HEADER = "x-api-key"        # required header name
EXPECTED_KEY = os.getenv("API_KEY")

#------------------------debug-------------------------------------
from fastapi import Request
import logging
logger = logging.getLogger("uvicorn.error")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("Incoming request %s %s", request.method, request.url.path)
    logger.info("Headers: %s", dict(request.headers))
    resp = await call_next(request)
    logger.info("Response %s for %s %s", resp.status_code, request.method, request.url.path)
    return resp

@app.on_event("startup")
async def startup_routes_dump():
    for route in app.routes:
        logger.info("Route: %s %s", getattr(route, "methods", None), route.path)




#----------------------------end bebug-----------------------------------------

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
        raise HTTPException(status_code=404, detail="Admission not found")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(adm, field, value)

    await db.commit()
    await db.refresh(adm)
    return adm

# use a descriptive path param name and string type
@app.patch("/admissions/by-ticket/{ticket_number}", response_model=AdmissionRead)
async def patch_admission_by_ticket(
    ticket_number: str,
    payload: AdmissionUpdate,
    db: AsyncSession = Depends(get_session),
):
    logger.info("patch_admission_by_ticket called with ticket=%s", ticket_number)
    q = await db.execute(select(Admission).where(Admission.ticket_number == ticket_number))
    adm = q.scalars().first()
    if not adm:
        raise HTTPException(status_code=404, detail="Admission not found")

    update_data = payload.dict(exclude_unset=True)
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
