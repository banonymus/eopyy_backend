import datetime

# ---------------------------------------------------------
# HELPERS - ADMISSIONS
# ---------------------------------------------------------

def escape_msh2():
    return "^~\\&"

def build_msh21(profile_id: str, installation_code: str):
    return f"{profile_id}~^^^^^^^^^{installation_code}"


# ---------------------------------------------------------
# MSH (21 fields)
# ---------------------------------------------------------
def build_MSH(ticket_number, profile_id, installation_code):
    now = datetime.now().strftime("%Y%m%d%H%M")

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
    now = datetime.now().strftime("%Y%m%d%H%M")
    return f"EVN|A01|{now}|||{operator_id}"

#PID-------------------------------------------------------------
#     PID
#----------------------------------------------------------------

def build_PID(data):
    # PID + 31 SEQ fields = 32 fields total
    pid = ["PID"] + [""] * 31

    # ---------------------------------------------------------
    # PID.3 – Patient Identifier List (EOPYY-compliant)
    # ---------------------------------------------------------
    pid[3] = "~".join([
        f"{data['pid_taut']}^^^^ΤΑΥΤΟΠΟΙΗΣΗ",
        f"{data['pid_ekaa']}^^^^ΕΚΑΑ",
        f"{data['pid_eidik']}^^^^ΕΙΔΙΚΑΙΚΑΝΟΤΗΤΑ",
        f"^^^^ΛΗΞΗ^^^{data['pid_expiry']}",
        f"{data['pid_foreas']}^^^^ΦΟΡΕΑΣ"
    ])

    # ---------------------------------------------------------
    # PID.5 – Patient Name (EOPYY-compliant)
    # last_name ^ first_name ^ last_name2 ^ first_name2
    # ---------------------------------------------------------
    pid[5] = (
        f"{data['last_name']}^"
        f"{data['first_name']}^"
        f"{data.get('last_name2', '')}^"
        f"{data.get('first_name2', '')}"
    )

    # PID.7 – Birthdate
    pid[7] = data["dob"]

    # PID.8 – Sex
    pid[8] = data["sex"]

    # PID.12 – Country Code
    pid[12] = data["country_code"]

    # PID.13 – Phone (XTN)
    if data.get("phone1_area") and data.get("phone1_number"):
        pid[13] = f"^^^^^{data['phone1_area']}^{data['phone1_number']}"

    # PID.19 – AMKA
    pid[19] = data["amka"]

    # PID.31 – Identity Unknown Indicator (N/Y/E)
    pid[31] = data["pid31"]

    # ---------------------------------------------------------
    # PID.3 type (Τύπος Ταυτοποίησης) — NEW FIELD
    # ---------------------------------------------------------
    # We store it in PID.3.5 (identifier type)
    # EOPYY expects it inside the PID.3 composite
    pid3_type = data.get("pid3_type", "0")  # default AMKA

    # Append type to the first identifier (ΤΑΥΤΟΠΟΙΗΣΗ)
    pid[3] = pid[3] + f"^{pid3_type}"

    return "|".join(pid)






# ---------------------------------------------------------
# NK1 (AMA + AMKA CORRECT FORMAT)
# ---------------------------------------------------------
def build_NK1(amka, nk1_ama, last, first, pid31="N", pv2_36="N", pid3_type="0"):
    nk1 = ["NK1", "1", f"{last}^{first}"]

    while len(nk1) < 33:
        nk1.append("")

    send_ama = nk1_ama and len(nk1_ama.strip()) > 0
    send_amka = (
        amka and len(amka.strip()) == 11 and
        pid3_type == "0" and
        pv2_36 == "N" and
        pid31 == "N"
    )

    if send_ama and send_amka:
        nk1_33 = f"{nk1_ama}^^^^ΑΜΑ~{amka}^^^^ΑΜΚΑ"
    elif send_ama:
        nk1_33 = f"{nk1_ama}^^^^ΑΜΑ"
    elif send_amka:
        nk1_33 = f"{amka}^^^^ΑΜΚΑ"   # ⭐ FIX: send AMKA alone
    else:
        nk1_33 = ""

    nk1.append(nk1_33)
    return "|".join(nk1)




def build_PV1(location_code, doctor_code, ticket_number, admit_datetime, alt_visit_id=None):
    admit_datetime = admit_datetime[:12]   # YYYYMMDDHHMM

    # PV1 must have EXACTLY 50 fields (indexes 0..49)
    pv1 = [""] * 50

    pv1[0] = "PV1"              # Segment name
    pv1[1] = ""                 # PV1.1 Set ID
    pv1[2] = "I"                # PV1.2 Patient Class

    pv1[3] = location_code      # PV1.4 Assigned Patient Location
    pv1[7] = doctor_code        # PV1.7 Attending Doctor

    pv1[19] = ticket_number     # PV1.19 Visit Number

    pv1[44] = admit_datetime    # PV1.44 Admit Date/Time

    # PV1.50 (index 49)
    #pv1[49] = alt_visit_id if alt_visit_id else ticket_number
    #pv1[49] = f"{ticket_number}01"  #ticket_number + 1

    pv1[49] = str(alt_visit_id)  # ⭐ MUST BE DIFFERENT
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





def build_full_hl7_message(data):
    return "\r".join([
        build_MSH(
            data["ticket_number"],
            data["profile_id"],
            data["installation_code"]
        ),

        build_EVN(data["operator_id"]),

        build_PID(data),

        build_NK1(
            amka=data["amka"],
            nk1_ama=data["nk1_ama"],
            last=data["last_name"],
            first=data["first_name"],
            pid31=data["pid31"],                     # dynamic
            pv2_36="N",                              # A01 always N
            pid3_type=data.get("pid3_type", "0")     # dynamic
        ),

        build_PV1(
            data["location_code"],
            data["doctor_amka"],
            data["ticket_number"],
            data["admit_datetime"]
        ),

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

def build_MSH_A03(discharge_ticket_number,ticket_number, profile_id, installation_code):
    now = datetime.now().strftime("%Y%m%d%H%M")
    return (
        #f"MSH|^~\\&|||||{now}||ADT^A03^ADT_A03|{ticket_number}|P|2.6|||||||||"
        f"MSH|^~\\&|||||{now}||ADT^A03^ADT_A03|{discharge_ticket_number}|P|2.6|||||||||"
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
def build_PV1_A03(location_code, visit_number, admit_datetime, discharge_datetime,
                  discharge_ticket_number,patient_type="0", alt_visit_id=None):

    pv1 = [""] * 53  # 0..52

    pv1[0] = "PV1"
    pv1[1] = ""
    pv1[2] = "I"

    pv1[3] = location_code

    pv1[18] = patient_type      # PV1.19
    pv1[19] = visit_number      # PV1.20

    pv1[45] = discharge_datetime          # PV1.46

    #pv1[51] = alt_visit_id or visit_number  # PV1.52
    pv1[51] = discharge_ticket_number




    return "|".join(pv1)


# ---------------------------------------------------------
# FULL HL7 MESSAGE A03
# ---------------------------------------------------------


def build_full_hl7_message_A03(data):
    return "\r".join([
        build_MSH_A03(
            data["discharge_ticket_number"],
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
            alt_visit_id=data["visit_number"],  # ⭐ MUST BE visit_number

        )
    ]) + "\r"

