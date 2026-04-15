# hl7_builder_worker.py

from hl7_builder import (
    build_MSH,
    build_EVN,
    build_PID,
    build_NK1,
    build_PV1,
    build_PV2,
    build_DG1,
    build_MSH_A03,
    build_EVN_A03,
    build_PID_A03,
    build_PV1_A03,
)

def normalize(data: dict, key: str, default: str = "") -> str:
    """Safe extraction from Neon row dict."""
    val = data.get(key)
    return "" if val is None else str(val)

def build_hl7_admission(data: dict) -> str:
    """Build HL7 ADT^A01 from raw Neon dict."""
    return "\r".join([
        build_MSH(
            normalize(data, "ticket_number"),
            normalize(data, "profile_id"),
            normalize(data, "installation_code"),
        ),
        build_EVN(normalize(data, "operator_id")),
        build_PID({
            "pid_taut": normalize(data, "pid_taut"),
            "pid_ekaa": normalize(data, "pid_ekaa"),
            "pid_eidik": normalize(data, "pid_eidik"),
            "pid_expiry": normalize(data, "pid_expiry"),
            "pid_foreas": normalize(data, "pid_foreas"),
            "last_name": normalize(data, "last_name"),
            "first_name": normalize(data, "first_name"),
            "dob": normalize(data, "dob_hl7"),
            "sex": normalize(data, "sex_val"),
            "country_code": normalize(data, "country_code"),
            "phone1_area": normalize(data, "phone1_area"),
            "phone1_number": normalize(data, "phone1_number"),
            "amka": normalize(data, "amka"),
            "pid31": normalize(data, "pid31"),
        }),
        build_NK1(
            normalize(data, "amka"),
            normalize(data, "nk1_ama"),
            normalize(data, "last_name"),
            normalize(data, "first_name"),
        ),
        build_PV1(
            normalize(data, "location_code"),
            normalize(data, "doctor_amka"),
            normalize(data, "ticket_number"),
            normalize(data, "admit_datetime"),
        ),
        build_PV2(normalize(data, "admit_datetime")),
        build_DG1(normalize(data, "icd10_code")),
    ]) + "\r"

def build_hl7_discharge(data: dict) -> str:
    """Build HL7 ADT^A03 from raw Neon dict."""
    return "\r".join([
        build_MSH_A03(
            normalize(data, "ticket_number"),
            normalize(data, "profile_id"),
            normalize(data, "installation_code"),
        ),
        build_EVN_A03(normalize(data, "operator_id")),
        build_PID_A03(),
        build_PV1_A03(
            normalize(data, "location_code"),
            normalize(data, "ticket_number"),
            normalize(data, "admit_datetime"),
            normalize(data, "discharge_datetime"),
            patient_type="0",
            alt_visit_id=normalize(data, "ticket_number"),
        ),
    ]) + "\r"

def build_hl7_message(data: dict) -> str:
    """Auto-select A01 or A03 based on presence of discharge_datetime."""
    if data.get("discharge_datetime"):
        return build_hl7_discharge(data)
    return build_hl7_admission(data)
