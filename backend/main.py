from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import engine, Base, get_session
from models import Admission
from schemas import AdmissionCreate, AdmissionRead

app = FastAPI()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/admissions", response_model=AdmissionRead)
async def create_admission(
    data: AdmissionCreate,
    db: AsyncSession = Depends(get_session),
):
    adm = Admission(**data.dict())
    db.add(adm)
    await db.commit()
    await db.refresh(adm)
    return adm

@app.get("/admissions", response_model=list[AdmissionRead])
async def list_admissions(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Admission))
    return result.scalars().all()
