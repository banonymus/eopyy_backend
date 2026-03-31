from pydantic import BaseModel

class AdmissionBase(BaseModel):
    ticket_number: str
    profile_id: str
    installation_code: str
    operator_id: str

    last_name: str
    first_name: str
    country_code: str

    phone1_area: str
    phone1_number: str

    amka: str
    pid31: str

    dob_hl7: str
    sex_val: str

    pid_taut: str
    pid_ekaa: str
    pid_eidik: str
    pid_expiry: str
    pid_foreas: str

    doctor_amka: str
    doctor_last: str
    doctor_first: str

    visit_number: str
    admit_datetime: str
    location_code: str

    icd10_code: str
    icd10_desc: str
    icd10_date: str

    nk1_ama: str

    hl7: str
    raw_response: str
    status: str


class AdmissionCreate(AdmissionBase):
    pass


class AdmissionRead(AdmissionBase):
    id: int
    created_at: str

    class Config:
        orm_mode = True
