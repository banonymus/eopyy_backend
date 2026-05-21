import datetime
import aiofiles
import os


# ---------------------------------------------------------
#  CLEAN, FINAL, CORRECT HL7 DATE FORMATTER
# ---------------------------------------------------------
def fmt_date(dt):
    if not dt:
        return ""

    # Already datetime object
    if isinstance(dt, datetime.datetime):
        return dt.strftime("%Y%m%d%H%M")

    # Try ISO format first (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    try:
        return datetime.datetime.fromisoformat(dt).strftime("%Y%m%d%H%M")
    except:
        pass

    # Try EOPYY/Neon format: YYYYMMDDHHMMSS
    try:
        return datetime.datetime.strptime(dt, "%Y%m%d%H%M%S").strftime("%Y%m%d%H%M")
    except:
        pass

    # Try short date: YYYYMMDD
    try:
        return datetime.datetime.strptime(dt, "%Y%m%d").strftime("%Y%m%d%H%M")
    except:
        pass

    # Fallback: return first 12 chars (YYYYMMDDHHMM)
    return str(dt).replace("-", "")[:12]


def safe(v):
    return "" if v is None else str(v)


# ---------------------------------------------------------
#  HL7 FILE GENERATOR
# ---------------------------------------------------------
async def generate_hl7_file(discharges, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total_amount = 0.0

    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:

        # File headers
        await f.write("FHS|^~\\&|||||||HOSP1||I\n")
        await f.write("BHS|^~\\&|||||202602~202602\n")

        for i, r in enumerate(discharges, start=1):
            msg_id = f"MSGID{i:05d}"

            # ---------------------------------------------------------
            # MSH
            # ---------------------------------------------------------
            await f.write(
                f"MSH|^~\\&|||||{fmt_date(r['discharge_time'])}||"
                f"ADT^A03^ADT_A03|{safe(r['ticket_number'])}|P|2.6|||||||||"
                f"{safe(r['patient_id'])}|^^^^^^^^^{safe(r['installation_code'])}\n"
            )

            # ---------------------------------------------------------
            # EVN
            # ---------------------------------------------------------
            await f.write(
                f"EVN|A03|{fmt_date(r['discharge_time'])}|||{safe(r['operator_id'])}\n"
            )

            # ---------------------------------------------------------
            # PID
            # ---------------------------------------------------------
            await f.write(
                f"PID||{safe(r['patient_id'])}|{safe(r['amka'])}^^^^AMKA||"
                f"{safe(r['lastname'])}^{safe(r['firstname'])}||{safe(r['dob'])}|{safe(r['gender'])}|||"
                f"^{safe(r.get('address',''))}^^{safe(r.get('city',''))}^^{safe(r.get('postal',''))}||"
                f"{safe(r.get('phone',''))}|||||{safe(r.get('afm',''))}|||||||||0||0\n"
            )

            # ---------------------------------------------------------
            # PV1
            # ---------------------------------------------------------
            await f.write(
                f"PV1||I|{safe(r['location_code'])}||||{safe(r['doctor_amka'])}^|||||||||||0|"
                f"{safe(r['ticket_number'])}||||||||||||||||||||||||||"
                f"{fmt_date(r['admission_time'])}|||||{safe(r['ticket_number'])}\n"
            )

            # ---------------------------------------------------------
            # PV2
            # ---------------------------------------------------------
            await f.write("PV2||||||||||||||||||||||||||||||||||||||||||U\n")

            # ---------------------------------------------------------
            # DG1
            # ---------------------------------------------------------
            await f.write(
                f"DG1|1|ICD-10|{safe(r['diagnosis_code'])}|{safe(r['diagnosis_desc'])}||D\n"
            )

            # ---------------------------------------------------------
            # PSL
            # ---------------------------------------------------------
            await f.write(
                f"PSL|||1||||{safe(r['procedure_code'])}|1||"
                f"{fmt_date(r['admission_time'])}|{fmt_date(r['discharge_time'])}|"
                f"0.0|||{float(r['price']):.2f}|{float(r['price']):.2f}|||||NO|||||||||\n"
            )

            # ---------------------------------------------------------
            # ZSL
            # ---------------------------------------------------------
            await f.write(
                f"ZSL|||||1|1|100.00|{float(r['price']):.2f}|0.00|{float(r['price']):.2f}|0.00||"
                f"0|0|0.00|0.00|0|\n"
            )

            total_amount += float(r["price"])

        # ---------------------------------------------------------
        # TRAILER
        # ---------------------------------------------------------
        await f.write(f"BTS|{len(discharges)}||{total_amount:.2f}\n")

    return out_path
