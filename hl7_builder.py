import datetime

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def escape_msh2():
    return "^~\\&"

def build_msh21(profile_id: str, installation_code: str):
    return f"{profile_id}~^^^^^^^^^{installation_code}"


# ---------------------------------------------------------
# MSH (21 fields)
# ---------------------------------------------------------
def build_MSH(ticket_number, profile_id, installation_code):
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    msh = [
        "MSH",                  # 1  Segment ID
        "^~\\&",                # 2  Encoding characters
        "",                     # 3  Sending Application
        "",                     # 4  Sending Facility
        "",                     # 5  Receiving Application
        "",                     # 6  Receiving Facility
        now,                    # 7  Date/Time of Message
        "",                     # 8  Security
        "ADT^A01^ADT_A01",      # 9  Message Type
        ticket_number,          # 10 Message Control ID
        "P",                    # 11 Processing ID
        "2.6",                  # 12 Version ID

        # MSH.13–MSH.20 → 8 empty fields
        "", "", "", "", "", "", "", "",

        profile_id,             # 21 → MSH.21 (Message Profile Identifier)
        "^^^^^^^^^" + installation_code  # 22 → MSH.22 (Sending Responsible Organization)
    ]

    return "|".join(msh)




# ---------------------------------------------------------
# EVN
# ---------------------------------------------------------
def build_EVN(operator_id):
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"EVN|A01|{now}|||{operator_id}"


# ---------------------------------------------------------
# PID (32 fields)
# ---------------------------------------------------------
def build_PID(data):
    # PID + 31 SEQ fields = 32 fields total
    pid = ["PID"] + [""] * 31

    # PID.3 – Patient Identifier List
    pid[3] = "~".join([
        f"{data['pid_taut']}^^^^ΤΑΥΤΟΠΟΙΗΣΗ",
        f"{data['pid_ekaa']}^^^^ΕΚΑΑ",
        f"{data['pid_eidik']}^^^^ΕΙΔΙΚΑΙΚΑΝΟΤΗΤΑ",
        f"^^^^ΛΗΞΗ^^^{data['pid_expiry']}",
        f"{data['pid_foreas']}^^^^ΦΟΡΕΑΣ"
    ])

    # PID.5 – Όνομα
    pid[5] = f"{data['last_name']}^{data['first_name']}"

    # PID.7 – Ημ/νία γέννησης
    pid[7] = data["dob"]

    # PID.8 – Φύλο
    pid[8] = data["sex"]

    # PID.12 – Country Code (π.χ. GR)
    pid[12] = data["country_code"]

    # PID.13 – Τηλέφωνο
    if data["phone1_area"] and data["phone1_number"]:
        pid[13] = f"^^^^^{data['phone1_area']}^{data['phone1_number']}"

    # PID.19 – ΑΜΚΑ (ΚΡΙΣΙΜΟ ΓΙΑ ΤΟ 331)
    pid[19] = data["amka"]

    # PID.31 – Identity Unknown Indicator (N/Y/E)
    pid[31] = data["pid31"]

    return "|".join(pid)






# ---------------------------------------------------------
# NK1 (AMA + AMKA CORRECT FORMAT)
# ---------------------------------------------------------
def build_NK1(amka, nk1_ama, last, first):
    nk1 = ["NK1", "1", f"{last}^{first}"]

    # pad to NK1-33
    while len(nk1) < 33:
        nk1.append("")

    # correct AMA + AMKA format
    nk1.append(f"{nk1_ama}^^^^ΑΜΑ~{amka}^^^^ΑΜΚΑ")

    return "|".join(nk1)


def build_PV1(location_code, visit_number, admit_datetime, discharge_datetime,
                  patient_type="0", alt_visit_id=None):
    pv1 = [""] * 53   # PV1.52 = index 52

    pv1[0] = "PV1"
    pv1[1] = ""                # Set ID
    pv1[2] = "I"               # Patient Class

    pv1[3] = location_code     # PV1.4

    # PV1.5–PV1.18 κενά → 15 pipes μετά το location_code

    # PV1.19 — patient_type
    pv1[18] = patient_type

    # PV1.20 — visit_number
    pv1[19] = visit_number

    # PV1.45 — discharge datetime
    pv1[44] = discharge_datetime

    # PV1.53 — alt visit id
    pv1[52] = alt_visit_id or visit_number

    return "|".join(pv1)
















# ---------------------------------------------------------
# PV2 (36 fields)
# ---------------------------------------------------------
def build_PV2(admit_datetime):
    # PV2 must have 37 fields total (PV2.37 = N)
    pv2 = ["PV2"] + [""] * 36   # 37 fields total

    pv2[8] = admit_datetime[:8]  # PV2.9 = admit date (YYYYMMDD)
    pv2[36] = "N"                # PV2.37 = N (required by EOPYY)

    return "|".join(pv2)



# ---------------------------------------------------------
# DG1 (9 fields)
# ---------------------------------------------------------
def build_DG1(code):
    return f"DG1|1||{code}^^ICD-10|||A"





# ---------------------------------------------------------
# FULL HL7 MESSAGE
# ---------------------------------------------------------
def build_full_hl7_message(data):
    return "\r".join([
        build_MSH(data["ticket_number"], data["profile_id"], data["installation_code"]),
        build_EVN(data["operator_id"]),
        build_PID(data),
        build_NK1(data["amka"], data["nk1_ama"], data["last_name"], data["first_name"]),
        build_PV1(data["location_code"], data["doctor_amka"], data["ticket_number"], data["admit_datetime"]),
        build_PV2(data["admit_datetime"]),
        build_DG1(data["icd10_code"])
    ]) + "\r"

# ---------------------------
# A03 / Discharge builders
# ---------------------------


import datetime

# ---------------------------------------------------------
# MSH A03 disharhes
# ---------------------------------------------------------


from datetime import datetime

def build_MSH_A03(ticket_number, profile_id, installation_code):
    now = datetime.now().strftime("%Y%m%d%H%M")
    return (
        f"MSH|^~\\&|||||{now}||ADT^A03^ADT_A03|{ticket_number}|P|2.6|||||||||"
        f"{profile_id}|^^^^^^^^^{installation_code}"
    )



# ---------------------------------------------------------
# EVN A03
# ---------------------------------------------------------
def build_EVN_A03(operator_id):
    now = datetime.now().strftime("%Y%m%d%H%M")
    operator_id = operator_id or ""   # prevent None
    return f"EVN|A03|{now}|||{operator_id}"





# ---------------------------------------------------------
# PID A03 (minimal)
# ---------------------------------------------------------
def build_PID_A03():
    return "PID||"





# ---------------------------------------------------------
# PV1 A03 (minimal σύμφωνα με προδιαγραφές)
# ---------------------------------------------------------
def build_PV1_A03(location_code, visit_number, admit_datetime, discharge_datetime, patient_type="0", alt_visit_id=None):
    pv1 = [""] * 53   # PV1.52 = index 52

    pv1[0] = "PV1"
    pv1[1] = ""                # Set ID
    pv1[2] = "I"               # Patient Class

    pv1[3] = location_code     # PV1.4

    # PV1.5–PV1.15 remain empty → this produces the required 11 pipes
    # PV1.16:
    pv1[15] = patient_type

    # PV1.17 (correct position for visit_number)
    pv1[16] = visit_number

    # PV1.45 (discharge datetime)
    pv1[44] = discharge_datetime

    # PV1.53 (alt visit id)
    pv1[52] = alt_visit_id or visit_number

    return "|".join(pv1)


# ---------------------------------------------------------
# FULL HL7 MESSAGE A03
# ---------------------------------------------------------


def build_full_hl7_message_A03(data):
    return "\r".join([
        build_MSH_A03(
            data["ticket_number"],
            data["profile_id"],
            data["installation_code"]
        ),
        build_EVN_A03(data["operator_id"]),
        build_PID_A03(),
        build_PV1_A03(
            data["location_code"],
            data["visit_number"],          # ⭐ MUST BE visit_number
            data["admit_datetime"],
            data["discharge_datetime"],
            patient_type=data.get("patient_type", "0"),
            alt_visit_id=data["visit_number"]  # ⭐ MUST BE visit_number
        )
    ]) + "\r"
