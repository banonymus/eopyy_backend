# main.py
import json
import os
import logging
import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request, status,Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.responses import FileResponse

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
from models import HL7Job
from database import async_session


# ---------------------------------------------------------
# 1) Create FastAPI app FIRST
# ---------------------------------------------------------
app = FastAPI()

import asyncio
from app.worker_batch import worker_loop

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(worker_loop())



logger = logging.getLogger("uvicorn.error")

# ---------------------------------------------------------
# 2) Import routers AFTER app creation
# ---------------------------------------------------------
from routes.retry import router as retry_router
from routes.webhooks import router as webhook_router
from routes.job_status import router as job_status_router
from app.generate_hl7 import router as generate_hl7_router

# ---------------------------------------------------------
# 3) Include routers
# ---------------------------------------------------------
app.include_router(retry_router)
app.include_router(webhook_router)
app.include_router(job_status_router)
app.include_router(generate_hl7_router)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
EXPECTED_KEY: Optional[str] = os.getenv("API_KEY") or CONFIG_EXPECTED_KEY
API_HEADER: str = (os.getenv("API_HEADER") or CONFIG_API_HEADER or "X-API-Key")


# ---------------------------------------------------------
# Middleware: API Key Verification
# ---------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok"}


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    path = request.url.path

    # Public endpoints (Render health checks, docs, monitoring)
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/debug/api-key",
        "/monitoring",
        "/monitoring/",
        "/monitoring/dashboard",
        "/monitoring/dashboard/errors",
        "/monitoring/dashboard/success",
        "/monitoring/queue",
        "/monitoring/worker-health",
        "/monitoring/last-errors",
        "/monitoring/last-success",
        "/worker/get-job",
        "/worker/update-job",
        "/debug/job",
    }

    # Allow exact matches OR prefix matches
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    # Allow HL7 worker endpoints
    if path.startswith("/generate-hl7") or path.startswith("/job-status") or path.startswith("/download"):
        return await call_next(request)

    # Allow webhooks
    if path.startswith("/webhooks/"):
        return await call_next(request)

    # API key check
    api_key = (
        request.headers.get("X-API-Key")
        or request.headers.get("x-api-key")
        or request.query_params.get("api_key")
    )

    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return await call_next(request)


# ---------------------------------------------------------
# Optional route dump
# ---------------------------------------------------------
if os.getenv("ENABLE_ROUTE_DUMP") == "1":

    @app.on_event("startup")
    async def startup_routes_dump():
        logger.info("Resolved main.py: %s", __file__)
        for route in app.routes:
            logger.info("Route: %s %s", getattr(route, "methods", None), getattr(route, "path", None)
)


# ---------------------------------------------------------
# DB startup
# ---------------------------------------------------------


# ---------------------------------------------------------
# Admissions
# ---------------------------------------------------------
from app.worker_batch import process_admission_row

@app.post("/admissions")
async def create_or_upsert_admission(
    data: AdmissionCreate,
    db: AsyncSession = Depends(get_session)
):
    if not data.ticket_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ticket_number is required"
        )

    # ----------------------------------------------------
    # 1) SAVE admission to database (as you want)
    # ----------------------------------------------------

    # ⭐ ADD alt_visit_id BEFORE SAVING TO NEON
    admission_dict = data.dict()

    ticket = int(data.ticket_number)
    admission_dict["alt_visit_id"] = str(ticket + 1)

    # ⭐ ADD discharge_ticket_number (required)
    admission_dict["discharge_ticket_number"] = data.discharge_ticket_number

    result = await db.execute(
        select(Admission).where(Admission.ticket_number == data.ticket_number)
    )
    existing = result.scalar_one_or_none()

    if existing:
        update_data = data.dict(exclude_unset=True)

        # ⭐ ensure discharge_ticket_number updates too
        if "discharge_ticket_number" in update_data:
            existing.discharge_ticket_number = update_data["discharge_ticket_number"]

        for field, value in update_data.items():
            setattr(existing, field, value)

        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        saved_record = existing

    else:
        adm = Admission(**admission_dict)
        db.add(adm)
        await db.commit()
        await db.refresh(adm)
        saved_record = adm

    # ----------------------------------------------------
    # 2) CALL HL7 + SOAP (NO DB UPDATE)
    # ----------------------------------------------------
    fake_row = admission_dict
    hl7_result = await process_admission_row(None, fake_row)

    # ----------------------------------------------------
    # 3) RETURN BOTH:
    # ----------------------------------------------------
    return {
        "message": "Admission saved to database",
        "ticket_number": saved_record.ticket_number,
        "record": jsonable_encoder(saved_record),

        "hl7_status": hl7_result["status"],
        "hl7_message": hl7_result["hl7"],
        "hl7_raw_response": hl7_result["raw_response"],
        "hl7_error": hl7_result["error"]
    }




@app.get("/admissions/{ticket_number}", response_model=AdmissionRead)
async def get_admission(ticket_number: str, db: AsyncSession = Depends(get_session)):
    stmt = select(Admission).where(Admission.ticket_number == ticket_number)
    admission = await db.scalar(stmt)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    return admission


@app.patch("/admissions/id/{admission_id}", response_model=AdmissionRead)
async def update_admission(admission_id: int, data: AdmissionUpdate, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Admission).where(Admission.id == admission_id))
    adm = result.scalar_one_or_none()
    if not adm:
        raise HTTPException(status_code=404, detail="Admission not found")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(adm, field, value)

    db.add(adm)
    await db.commit()
    await db.refresh(adm)
    return adm


# ---------------------------------------------------------
# Health & Debug
# ---------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug-version")
def debug_version():
    import models
    return {"fields": list(models.Admission.__table__.columns.keys())}


@app.post("/_debug-headers")
async def debug_headers(request: Request):
    headers = dict(request.headers)
    logger.info("Incoming headers for debug: %s", headers)
    return {"received_headers": list(headers.keys())}

# --------------------------------------------------------------------------------------------------------
# Discharges endpoints
# --------------------------------------------------------------------------------------------------------
from app.worker_batch import process_discharge_row

@app.post("/discharges")
async def create_or_process_discharge(
    data: DischargeCreate,
    db: AsyncSession = Depends(get_session)
):
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
    # ⭐ A) ORM DATA — CLEANUP FIELDS NOT IN DISCHARGE MODEL
    # ----------------------------------------------------
    discharge_data_for_db = discharge_data.copy()

    for bad_field in [
        "phone1_area",
        "phone1_number",
        "pid31",
        "pid_taut",
        "pid_ekaa",
        "pid_eidik",
        "pid_expiry",
        "pid_foreas",
        "address",
        "city",
        "zip",
        "country",
        "admission_ticket_number",
        "visit_number",
        "alt_visit_id",
        "admission_alt_visit_id",
    ]:
        discharge_data_for_db.pop(bad_field, None)

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


@app.post("/admissions/{ticket_number}/retry")
async def retry_admission(ticket_number: str, db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        text("""
            UPDATE admissions
            SET status='pending', updated_at=NOW()
            WHERE ticket_number = :ticket
              AND status = 'rejected'
            RETURNING id
        """),
        {"ticket": ticket_number}
    )
    row = q.fetchone()

    if not row:
        raise HTTPException(400, "Admission not found or not rejected")

    return {"message": "Admission set to pending again", "ticket": ticket_number}



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

from sqlalchemy import text

@app.get("/monitoring/queue")
async def monitoring_queue(db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        text("SELECT COUNT(*) FROM admissions WHERE status='pending'")
    )
    count = q.scalar()
    return {"pending": count}

@app.get("/monitoring/worker-health")
async def worker_health(db: AsyncSession = Depends(get_session)):
    q = await db.execute(text("SELECT last_beat FROM worker_heartbeat WHERE id=1"))
    row = q.fetchone()
    if not row:
        return {"status": "unknown", "last_beat": None}

    return {
        "status": "ok",
        "last_beat": row.last_beat
    }


@app.get("/monitoring/last-success")
async def monitoring_last_success(limit: int = 20, db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        text("""
            SELECT id, ticket_number, status, updated_at
            FROM admissions
            WHERE status='completed'
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
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


from fastapi.responses import HTMLResponse

@app.get("/monitoring/dashboard", response_class=HTMLResponse)
async def monitoring_dashboard(db: AsyncSession = Depends(get_session)):
    # get counts
    q1 = await db.execute(text("SELECT COUNT(*) FROM admissions WHERE status='pending'"))
    pending = q1.scalar()

    q2 = await db.execute(text("SELECT COUNT(*) FROM admissions WHERE status='processing'"))
    processing = q2.scalar()

    q3 = await db.execute(text("SELECT COUNT(*) FROM admissions WHERE status='completed'"))
    completed = q3.scalar()

    q4 = await db.execute(text("SELECT COUNT(*) FROM admissions WHERE status='error'"))
    errors = q4.scalar()

    q5 = await db.execute(text("SELECT COUNT(*) FROM admissions WHERE status='rejected'"))
    rejected = q5.scalar()

    html = f"""
    <html>
    <head>
        <title>EOPYY Monitoring</title>
        <style>
            body {{
                font-family: Arial;
                padding: 20px;
                background: #f5f5f5;
            }}
            .card {{
                background: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 20px;
            }}
            .stat {{
                background: #fff;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                font-size: 22px;
                font-weight: bold;
            }}
            .label {{
                font-size: 14px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <h1>EOPYY Monitoring Dashboard</h1>

        <div class="grid">
            <div class="stat">{pending}<div class="label">Pending</div></div>
            <div class="stat">{processing}<div class="label">Processing</div></div>
            <div class="stat">{completed}<div class="label">Completed</div></div>
            <div class="stat">{errors}<div class="label">Errors</div></div>
            <div class="stat">{rejected}<div class="label">Rejected</div></div>
        </div>

        <div class="card">
            <h2>Links</h2>
            <ul>
                <li><a href="/monitoring/queue">Queue</a></li>
                <li><a href="/monitoring/last-errors">Last Errors</a></li>
                <li><a href="/monitoring/last-success">Last Success</a></li>
                <li><a href="/monitoring/worker-health">Worker Health</a></li>
            </ul>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/monitoring/queue")
async def monitoring_queue(db: AsyncSession = Depends(get_session)):
    q = await db.execute(text("SELECT COUNT(*) FROM admissions WHERE status='pending'"))
    return {"pending": q.scalar()}

@app.get("/monitoring/worker-health")
async def monitoring_worker_health(db: AsyncSession = Depends(get_session)):
    q = await db.execute(text("SELECT last_beat FROM worker_heartbeat WHERE id=1"))
    row = q.fetchone()
    if not row:
        return {"status": "unknown", "last_beat": None}
    return {"status": "ok", "last_beat": row.last_beat}

@app.get("/monitoring/last-errors")
async def monitoring_last_errors(limit: int = 20, db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        text("""
            SELECT id, ticket_number, status, raw_response, updated_at
            FROM admissions
            WHERE status='error'
            ORDER BY updated_at DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    return [dict(r) for r in q.fetchall()]

@app.get("/monitoring/last-success")
async def monitoring_last_success(limit: int = 20, db: AsyncSession = Depends(get_session)):
    q = await db.execute(
        text("""
            SELECT id, ticket_number, status, updated_at
            FROM admissions
            WHERE status='completed'
            ORDER BY updated_at DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    return [dict(r) for r in q.fetchall()]

@app.get("/monitoring/dashboard", response_class=HTMLResponse)
async def monitoring_dashboard(db: AsyncSession = Depends(get_session)):
    q = await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM admissions WHERE status='pending') AS pending,
            (SELECT COUNT(*) FROM admissions WHERE status='processing') AS processing,
            (SELECT COUNT(*) FROM admissions WHERE status='completed') AS completed,
            (SELECT COUNT(*) FROM admissions WHERE status='error') AS errors
    """))
    stats = q.fetchone()

    html = f"""
    <html>
    <head>
        <title>EOPYY Dashboard</title>
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f5f5f5; }}
            .grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 20px; }}
            .stat {{ background: #fff; padding: 20px; border-radius: 8px; text-align: center; font-size: 22px; font-weight: bold; }}
            .label {{ font-size: 14px; color: #666; }}
            .card {{ background: white; padding: 20px; margin-top: 30px; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <h1>EOPYY Monitoring Dashboard</h1>

        <div class="grid">
            <div class="stat">{stats.pending}<div class="label">Pending</div></div>
            <div class="stat">{stats.processing}<div class="label">Processing</div></div>
            <div class="stat">{stats.completed}<div class="label">Completed</div></div>
            <div class="stat">{stats.errors}<div class="label">Errors</div></div>
        </div>

        <div class="card">
            <h2>Links</h2>
            <ul>
                <li><a href="/monitoring/dashboard/errors">Error Table</a></li>
                <li><a href="/monitoring/dashboard/success">Success Table</a></li>
                <li><a href="/monitoring/queue">Queue</a></li>
                <li><a href="/monitoring/worker-health">Worker Health</a></li>
            </ul>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)

@app.get("/monitoring/dashboard/errors", response_class=HTMLResponse)
async def monitoring_dashboard_errors(db: AsyncSession = Depends(get_session)):
    q = await db.execute(text("""
        SELECT ticket_number, raw_response, updated_at
        FROM admissions
        WHERE status='error'
        ORDER BY updated_at DESC
        LIMIT 50
    """))
    rows = q.fetchall()

    html = "<h1>Last Errors</h1><table border='1' cellpadding='5'><tr><th>Ticket</th><th>Error</th><th>Time</th></tr>"
    for r in rows:
        html += f"<tr><td>{r.ticket_number}</td><td>{r.raw_response}</td><td>{r.updated_at}</td></tr>"
    html += "</table>"

    return HTMLResponse(html)


@app.get("/monitoring/dashboard/success", response_class=HTMLResponse)
async def monitoring_dashboard_success(db: AsyncSession = Depends(get_session)):
    q = await db.execute(text("""
        SELECT ticket_number, updated_at
        FROM admissions
        WHERE status='completed'
        ORDER BY updated_at DESC
        LIMIT 50
    """))
    rows = q.fetchall()

    html = "<h1>Last Success</h1><table border='1' cellpadding='5'><tr><th>Ticket</th><th>Time</th></tr>"
    for r in rows:
        html += f"<tr><td>{r.ticket_number}</td><td>{r.updated_at}</td></tr>"
    html += "</table>"

    return HTMLResponse(html)

@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_index():
    html = """
    <html>
    <head>
        <title>Monitoring Index</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f5f5f5; }
            .card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                max-width: 600px;
                margin: auto;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 { text-align: center; }
            ul { font-size: 18px; }
            li { margin-bottom: 10px; }
            a { text-decoration: none; color: #0066cc; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>EOPYY Monitoring</h1>
            <ul>
                <li><a href="/monitoring/dashboard">Dashboard</a></li>
                <li><a href="/monitoring/queue">Queue</a></li>
                <li><a href="/monitoring/worker-health">Worker Health</a></li>
                <li><a href="/monitoring/last-errors">Last Errors (JSON)</a></li>
                <li><a href="/monitoring/last-success">Last Success (JSON)</a></li>
                <li><a href="/monitoring/dashboard/errors">Error Table</a></li>
                <li><a href="/monitoring/dashboard/success">Success Table</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/generate-hl7")
async def generate_hl7(from_date: str, to_date: str, installation_code: str):
    job_id = f"hl7_discharges_{installation_code}_{from_date}_{to_date}"

    async with async_session() as db:
        job = HL7Job(
            job_id=job_id,
            from_date=datetime.date.fromisoformat(from_date),
            to_date=datetime.date.fromisoformat(to_date),
            installation_code=installation_code,
            status="queued_batch"
        )

        db.add(job)
        await db.commit()

    return {
        "status": "queued_batch",
        "job_id": job_id,
        "check_status": f"/job-status/{job_id}"
    }



@app.get("/job-status/{job_id}")
async def job_status(job_id: str):
    job_id = job_id.strip()

    async with async_session() as db:
        result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.job_id,
        "status": job.status,
        "updated_at": job.updated_at,
        "download": f"/download/{job_id}" if job.file_data else None
    }


@app.get("/debug/job/{job_id}")
async def debug_job(job_id: str):
    job_id = job_id.strip()

    async with async_session() as db:
        result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
        job = result.scalar_one_or_none()

    if not job:
        return {"error": "not found"}

    return {
        "job_id": job.job_id,
        "status": job.status,
        "result_file": job.result_file,
        "updated_at": job.updated_at
    }
@app.get("/download/{job_id}")
async def download(job_id: str):
    job_id = job_id.strip()

    async with async_session() as db:
        result = await db.execute(select(HL7Job).where(HL7Job.job_id == job_id))
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # IMPORTANT: check file_data, NOT result_file
    if not job.file_data:
        raise HTTPException(status_code=404, detail="Job completed but no file stored")

    return Response(
        content=job.file_data,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={job_id}.hl7"
        }
    )

