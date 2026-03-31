from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Admission(Base):
    __tablename__ = "admissions"

    id = Column(Integer, primary_key=True, index=True)

    ticket_number = Column(String(20))
    profile_id = Column(String(50))
    installation_code = Column(String(50))
    operator_id = Column(String(50))

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

    doctor_amka = Column(String(20))
    doctor_last = Column(String(100))
    doctor_first = Column(String(100))

    visit_number = Column(String(20))
    admit_datetime = Column(String(20))
    location_code = Column(String(20))

    icd10_code = Column(String(20))
    icd10_desc = Column(String(255))
    icd10_date = Column(String(20))

    nk1_ama = Column(String(20))

    hl7 = Column(Text)
    raw_response = Column(Text)
    status = Column(String(20))

    created_at = Column(TIMESTAMP, server_default=func.now())
