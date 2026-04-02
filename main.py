import os
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_session, engine
from models import Base, Admission
from schemas import AdmissionCreate, AdmissionRead

app = FastAPI()

API_KEY = os.getenv("API_KEY")  # loaded from Render env vars
API_HEADER = "x-api-key"        # required header name

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
    key = request.headers.get("x-api-key") or request.query_params.get("api_key")
    if key != API_KEY:
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


