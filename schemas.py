# schemas.py
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

class AdmissionBase(BaseModel):
    ticket_number: Optional[str] = None
    profile_id: Optional[str] = None
    installation_code: Optional[str] = None
    operator_id: Optional[str] = None

    last_name: Optional[str] = None
    first_name: Optional[str] = None
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

    icd10_code: Optional[str] = None
    icd10_desc: Optional[str] = None
    icd10_date: Optional[str] = None

    nk1_ama: Optional[str] = None

    hl7: Optional[str] = None
    raw_response: Optional[str] = None
    status: Optional[str] = None

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

class AdmissionCreate(AdmissionBase):
    pass

class AdmissionRead(AdmissionBase):
    id: int
    created_at: Optional[datetime] = None

    discharge_datetime: Optional[str] = None
    discharge_result: Optional[str] = None
    raw_response_a03: Optional[str] = None

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
    alt_visit_id: Optional[str] = None
    icd10_code: Optional[str] = None
    icd10_desc: Optional[str] = None
    icd10_date: Optional[str] = None
    hl7_a03: Optional[str] = None
    raw_response: Optional[str] = None
    status: Optional[str] = None

class DischargeCreate(DischargeBase):
    ticket_number: str

class DischargeUpdate(DischargeBase):
    pass

class DischargeRead(DischargeBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
