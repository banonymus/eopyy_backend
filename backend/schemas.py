from pydantic import BaseModel

class AdmissionBase(BaseModel):
    ticket_number: str
    profile_id: str
    installation_code: str
    operator_id: str

    id_type_val: str
    id_number: str
    special_case_val: str
    insurance_expiry: str
    insurance_carrier: str

    last_name: str
    first_name: str
    country_code: str

    phone1_area: str
    phone1_number: str
    phone2_area: str | None = None
    phone2_number: str | None = None

    amka: str
    identity_flag_val: str

    nk1_last_name: str | None = None
    nk1_first_name: str | None = None
    nk1_amka: str | None = None

    patient_class: str
    location: str
    visit_number: str

    diagnoses: str
    procedures: str

    insurance_id: str | None = None
    insurance_company: str | None = None

    dob_hl7: str
    sex_val: str
    doctor_amka: str

class AdmissionCreate(AdmissionBase):
    pass

class AdmissionRead(AdmissionBase):
    id: int

    class Config:
        orm_mode = True
