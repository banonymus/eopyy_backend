from sqlalchemy import Column, Integer, String, Text
from database import Base

class Admission(Base):
    __tablename__ = "admissions"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(20), index=True)
    profile_id = Column(String(50))
    installation_code = Column(String(50))
    operator_id = Column(String(50))

    id_type_val = Column(String(5))
    id_number = Column(String(50))
    special_case_val = Column(String(5))
    insurance_expiry = Column(String(20))
    insurance_carrier = Column(String(100))

    last_name = Column(String(100))
    first_name = Column(String(100))
    country_code = Column(String(10))

    phone1_area = Column(String(10))
    phone1_number = Column(String(30))
    phone2_area = Column(String(10))
    phone2_number = Column(String(30))

    amka = Column(String(20))
    identity_flag_val = Column(String(5))

    nk1_last_name = Column(String(100))
    nk1_first_name = Column(String(100))
    nk1_amka = Column(String(20))

    patient_class = Column(String(5))
    location = Column(String(100))
    visit_number = Column(String(50))

    diagnoses = Column(Text)
    procedures = Column(Text)

    insurance_id = Column(String(50))
    insurance_company = Column(String(100))

    dob_hl7 = Column(String(20))
    sex_val = Column(String(5))
    doctor_amka = Column(String(20))
