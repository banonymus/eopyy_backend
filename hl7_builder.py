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


# ---------------------------------------------------------
# PV1 (51 fields)
# ---------------------------------------------------------
def build_PV1(location_code, doctor_code, ticket_number, admit_datetime, alt_visit_id=None):
    admit_datetime = admit_datetime[:12]

    # PV1 + 50 fields = 51 fields total (indexes 0..50)
    pv1 = ["PV1"] + [""] * 50

    pv1[2] = "I"                       # PV1.2 Patient Class
    pv1[3] = location_code             # PV1.3 Assigned Patient Location
    pv1[7] = doctor_code               # PV1.7 Attending Doctor
    pv1[19] = ticket_number            # PV1.19 Visit Number
    pv1[44] = admit_datetime           # PV1.44 Admit Date/Time

    # PV1.50 must exist — use ticket_number if no alt ID provided
    pv1[50] = alt_visit_id if alt_visit_id else ticket_number


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
# MSH A03
# ---------------------------------------------------------


def build_MSH_A03(ticket_number: str, profile_id: str, installation_code: str) -> str:
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    msh = [
        "MSH",                  # 1
        "^~\\&",                # 2
        "",                     # 3
        "",                     # 4
        "",                     # 5
        "",                     # 6
        now[:12],               # 7
        "",                     # 8
        "ADT^A03^ADT_A03",      # 9
        ticket_number,          # 10
        "P",                    # 11
        "2.6",                  # 12
        "", "", "", "", "", "", "", "",  # 13–20
        profile_id,             # 21
        "^^^^^^^^^" + installation_code  # 22
    ]
    return "|".join(msh)


# ---------------------------------------------------------
# EVN A03
# ---------------------------------------------------------
def build_EVN_A03(operator_id: str) -> str:
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    now=now[:12]
    return f"EVN|A03|{now}|||{operator_id}"


# ---------------------------------------------------------
# PID A03 (minimal)
# ---------------------------------------------------------
def build_PID_A03() -> str:
    # Σύμφωνα με το “σωστό εξιτήριο” του ΕΟΠΥΥ: PID||
    return "PID||"


# ---------------------------------------------------------
# PV1 A03 (minimal σύμφωνα με προδιαγραφές)
# ---------------------------------------------------------


import re

def _clean_field(value):
    if value is None:
        return ""
    return re.sub(r'[\r\n\x00-\x08\x0B\x0C\x0E-\x1F]', '', str(value))

def build_PV1_A03(location_code,
                  ticket_number,
                  admit_datetime,
                  discharge_datetime,
                  patient_type="0",
                  alt_visit_id=None,
                  template_pv1="PV1||I|666|||||||||||||||0|2013000012111||||||||||||||||||||||||||201310111111|||||2013000012113"):
    """
    Επιστρέφει PV1 string χωρίς trailing CR.
    Χρησιμοποιεί το template_pv1 για να διατηρήσει ακριβές pipe count και
    αντικαθιστά υπάρχοντα numeric/timestamp πεδία ώστε να αποφευχθεί διπλοεμφάνιση.
    """
    # καθαρισμοί και trim timestamps σε 12 chars
    location_code = _clean_field(location_code)
    ticket_number = _clean_field(ticket_number)
    admit = _clean_field(admit_datetime)[:12]
    discharge = _clean_field(discharge_datetime)[:12]
    alt_visit_id = _clean_field(alt_visit_id) if alt_visit_id is not None else ticket_number
    patient_type = _clean_field(patient_type)

    parts = _clean_field(template_pv1).split("|")
    if not parts or not parts[0].startswith("PV1"):
        raise ValueError("template_pv1 πρέπει να ξεκινάει με 'PV1'")

    orig_len = len(parts)

    # Εντοπίζουμε numeric/timestamp tokens στο template (8-14 ψηφία)
    numeric_idxs = [i for i, p in enumerate(parts) if re.fullmatch(r'\d{8,14}', p)]

    # Αν βρούμε τουλάχιστον 3 numeric πεδία κοντά στο τέλος (όπως στο working template),
    # αντικαθιστούμε τα κατάλληλα ώστε να έχουμε admit/discharge/alt μόνο μια φορά.
    if len(numeric_idxs) >= 3:
        # Συνήθως τα τελευταία 3 numeric στο template είναι: visitNumberLike, dischargeLike, altVisitLike
        # Θα τοποθετήσουμε: parts[n-3] <- (κρατάμε ή αντικαθιστούμε με ticket), parts[n-2] <- admit, parts[n-1] <- discharge/alt
        last = numeric_idxs[-3:]
        # βάζουμε ticket στην πρώτη από τις τρεις (αν θέλουμε να αντικαταστήσουμε)
        parts[last[0]] = ticket_number
        # admit και discharge στις επόμενες δύο θέσεις
        parts[last[1]] = admit
        parts[last[2]] = discharge
        # Αν υπάρχει επιπλέον numeric μετά από αυτά (π.χ. alt visit), τοποθετούμε alt_visit_id εκεί
        if len(numeric_idxs) >= 4:
            parts[numeric_idxs[-1]] = alt_visit_id
        else:
            # αλλιώς, προσπαθούμε να τοποθετήσουμε alt_visit_id στην τελευταία θέση του template
            parts[-1] = alt_visit_id if re.fullmatch(r'\d{1,250}', parts[-1]) or parts[-1] == "" else parts[-1]
    else:
        # fallback: επεκτείνουμε προσωρινά ώστε να τοποθετήσουμε σε HL7 indices (ασφαλές)
        if len(parts) < 51:
            parts += [""] * (51 - len(parts))
        parts[2]  = "I"
        parts[3]  = location_code
        parts[18] = patient_type
        parts[19] = ticket_number
        parts[44] = admit
        parts[45] = discharge
        parts[50] = alt_visit_id

    # Βεβαιώνουμε ότι οι βασικές θέσεις υπάρχουν/αντικαταστάθηκαν
    if len(parts) > 3:
        parts[3] = location_code
    if len(parts) > 19:
        parts[19] = ticket_number

    # Επιστρέφουμε μόνο τα πρώτα orig_len μέρη για να διατηρήσουμε ακριβώς το pipe count του template
    return "|".join(parts[:orig_len])







# ---------------------------------------------------------
# FULL HL7 MESSAGE A03
# ---------------------------------------------------------


def build_full_hl7_message_A03(data):
    return "\r".join([
        build_MSH_A03(data["ticket_number"], data["profile_id"], data["installation_code"]),
        build_EVN_A03(data["operator_id"]),
        build_PID_A03(),
        build_PV1_A03(
            data["location_code"],
            data["ticket_number"],
            data["admit_datetime"],
            data["discharge_datetime"],
            patient_type=data.get("patient_type", "0"),
            alt_visit_id=data["ticket_number"]
        )
    ]) + "\r"

