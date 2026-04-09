from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Admission(Base):
    __tablename__ = "admissions"

    id = Column(Integer, primary_key=True, index=True)

    # Identifiers / MSH
    ticket_number = Column(String(64), unique=True, index=True, nullable=False)
    profile_id = Column(String(50))
    installation_code = Column(String(50))
    operator_id = Column(String(50))

    # Patient
    last_name = Column(String(100))
    first_name = Column(String(100))
    country_code = Column(String(10))

    phone1_area = Column(String(10))
    phone1_number = Column(String(20))

    amka = Column(String(20))
    pid31 = Column(String(5))

    dob_hl7 = Column(String(20))
    sex_val = Column(String(5))

    pid_taut = Column(String(50))
    pid_ekaa = Column(String(50))
    pid_eidik = Column(String(50))
    pid_expiry = Column(String(20))
    pid_foreas = Column(String(50))

    # Visit / PV1
    doctor_amka = Column(String(20))
    doctor_last = Column(String(100))
    doctor_first = Column(String(100))

    visit_number = Column(String(20))
    admit_datetime = Column(String(20))
    location_code = Column(String(20))

    # Diagnosis / DG1
    icd10_code = Column(String(20))
    icd10_desc = Column(String(255))
    icd10_date = Column(String(20))

    nk1_ama = Column(String(20))

    # HL7 / responses
    hl7 = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    status = Column(String(20), nullable=True)

    # --- New fields for discharge / A03 ---
    discharge_datetime = Column(String(32), nullable=True)
    discharge_result = Column(String(16), nullable=True)
    raw_response_a03 = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())


from sqlalchemy import Column, BigInteger, String, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Discharge(Base):
    __tablename__ = "discharges"

    id = Column(BigInteger, primary_key=True)
    ticket_number = Column(String)
    profile_id = Column(String)
    installation_code = Column(String)
    operator_id = Column(String)
    last_name = Column(String)
    first_name = Column(String)
    country_code = Column(String)
    amka = Column(String)
    dob_hl7 = Column(String)
    sex_val = Column(String)
    location_code = Column(String)
    doctor_amka = Column(String)
    admit_datetime = Column(String)
    discharge_datetime = Column(Text)
    alt_visit_id = Column(String)
    icd10_code = Column(String)
    icd10_desc = Column(String)
    icd10_date = Column(String)
    hl7_a03 = Column(Text)
    raw_response = Column(Text)
    status = Column(String)
    created_at = Column(DateTime, server_default=func.now())
