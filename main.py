from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_session, engine
from models import Base, Admission
from schemas import AdmissionCreate, AdmissionRead

app = FastAPI()


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

@app.get("/debug-version")
def debug_version():
    import models
    return {"fields": list(models.Admission.__table__.columns.keys())}


@app.get("/admissions", response_model=list[AdmissionRead])
async def list_admissions(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Admission).order_by(Admission.id.desc()))
    return result.scalars().all()


@app.get("/health")
async def health():
    return {"status": "ok"}
