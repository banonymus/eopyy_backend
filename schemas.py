# schemas.py
from pydantic import BaseModel, validator
from typing import List,Optional
from datetime import datetime
from sqlalchemy import Column, JSON

class AdmissionBase(BaseModel):
    ticket_number: Optional[str] = None
    profile_id: Optional[str] = None
    installation_code: Optional[str] = None
    operator_id: Optional[str] = None

    last_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name2: Optional[str] = None
    first_name2: Optional[str] = None
    country_code: Optional[str] = None

    phone1_area: Optional[str] = None
    phone1_number: Optional[str] = None

    amka: Optional[str] = None
    pid31: Optional[str] = None

    dob_hl7: Optional[str] = None
    sex_val: Optional[str] = None

    pid_taut: Optional[str] = None
    pid_ekaa: Optional[str] = None
    pid_eidik: Optional[str] = None
    pid_expiry: Optional[str] = None
    pid_foreas: Optional[str] = None

    doctor_amka: Optional[str] = None
    doctor_last: Optional[str] = None
    doctor_first: Optional[str] = None

    visit_number: Optional[str] = None
    admit_datetime: Optional[str] = None
    location_code: Optional[str] = None

    #icd10_code: Optional[str] = None
    #icd10_desc: Optional[str] = None
    #icd10_date: Optional[str] = None

    nk1_ama: Optional[str] = None

    hl7: Optional[str] = None
    raw_response: Optional[str] = None
    status: Optional[str] = None
    alt_visit_id: str | None = None
    pid3_type: Optional[str] = "0"
    ekaa_pdf_base64: Optional[str] = None

    @validator("ticket_number")
    def ticket_length(cls, v):
        if v is None:
            return v
        if not (13 <= len(v) <= 20):
            raise ValueError("ticket_number should be 13 digits (or up to DB length)")
        return v

    @validator("profile_id")
    def profile_id_len(cls, v):
        if v is None:
            return v
        if len(v) != 20:
            raise ValueError("profile_id must be exactly 20 characters")
        return v

class Diagnosis(BaseModel):
    icd10_code: str
    icd10_desc: str
    icd10_date: str
    ken_code: Optional[str] = None
    total_amount: Optional[float] = None
    covered_amount: Optional[float] = None
    patient_amount: Optional[float] = None
    patient_participation_perc: Optional[float] = None

class AdmissionCreate(BaseModel):
    ticket_number: str
    discharge_ticket_number: Optional[str] = None
    profile_id: str
    installation_code: str
    operator_id: str

    last_name: str
    first_name: str
    last_name2: Optional[str] = ""
    first_name2: Optional[str] = ""

    country_code: str
    phone1_area: Optional[str] = None
    phone1_number: Optional[str] = None

    amka: str
    pid31: str
    pid3_type: str

    dob_hl7: str
    sex_val: str

    pid_taut: str
    pid_ekaa: Optional[str] = ""
    pid_eidik: str
    pid_expiry: str
    pid_foreas: str

    doctor_amka: str
    doctor_last: str
    doctor_first: str

    visit_number: str
    admit_datetime: str
    location_code: str

    diagnoses: List[Diagnosis]   # ⭐ NEW — multiple DG1 support

    nk1_ama: Optional[str] = ""
    ekaa_pdf_base64: Optional[str] = None

class AdmissionRead(AdmissionBase):
    id: int
    created_at: Optional[datetime] = None

    discharge_datetime: Optional[str] = None
    discharge_result: Optional[str] = None
    raw_response_a03: Optional[str] = None
    discharge_ticket_number: str
    class Config:
        orm_mode = True

class AdmissionUpdate(BaseModel):
    discharge_datetime: Optional[str] = None
    discharge_result: Optional[str] = None
    raw_response_a03: Optional[str] = None


from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DischargeBase(BaseModel):
    ticket_number: Optional[str] = None
    profile_id: Optional[str] = None
    installation_code: Optional[str] = None
    operator_id: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    country_code: Optional[str] = None
    amka: Optional[str] = None
    dob_hl7: Optional[str] = None
    sex_val: Optional[str] = None
    location_code: Optional[str] = None
    doctor_amka: Optional[str] = None
    admit_datetime: Optional[str] = None
    discharge_datetime: Optional[str] = None

    # NEW HL7 fields
    discharge_ticket_number: Optional[str] = None
    visit_number: Optional[str] = None
    admission_alt_visit_id: Optional[str] = None

    # Optional PID fields
    phone1_area: Optional[str] = None
    phone1_number: Optional[str] = None
    pid31: Optional[str] = None
    pid_taut: Optional[str] = None      # 0 = Greek, 1 = EU
    pid_ekaa: Optional[str] = None      # EKAA number
    pid_eidik: Optional[str] = None
    pid_expiry: Optional[str] = None
    pid_foreas: Optional[str] = None

    alt_visit_id: Optional[str] = None
    icd10_code: Optional[str] = None
    icd10_desc: Optional[str] = None
    icd10_date: Optional[str] = None
    hl7_a03: Optional[str] = None
    raw_response: Optional[str] = None
    raw_response_a03: Optional[str] = None
    status: Optional[str] = None
    total_amount: Optional[float] = None
    covered_amount: Optional[float] = None
    patient_amount: Optional[float] = None
    admission_ticket_number: Optional[str] = None
    ken_code: Optional[str] = None  # ⭐ NEW
    patient_participation_perc: Optional[float] = None  # ⭐ NEW
    diagnoses: Optional[List[dict]] = None
    nk1_last: Optional[str] = ""  # holder last (EU indirect)
    nk1_first: Optional[str] = ""  # holder first (EU indirect)

    ekaa_pdf_base64: Optional[str] = None  # scanned EKAA card


class DischargeCreate(DischargeBase):
    ticket_number: str

class DischargeUpdate(DischargeBase):
    pass

class DischargeRead(DischargeBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
