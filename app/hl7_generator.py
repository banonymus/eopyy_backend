import datetime
import aiofiles
import os


def fmt_date(dt):
    if not dt:
        return ""

    if isinstance(dt, datetime.datetime):
        return dt.strftime("%Y%m%d%H%M")

    try:
        return datetime.datetime.fromisoformat(dt).strftime("%Y%m%d%H%M")
    except:
        pass

    try:
        return datetime.datetime.strptime(dt, "%Y%m%d%H%M%S").strftime("%Y%m%d%H%M")
    except:
        pass

    try:
        return datetime.datetime.strptime(dt, "%Y%m%d").strftime("%Y%m%d%H%M")
    except:
        pass

    return str(dt).replace("-", "")[:12]


def safe(v):
    return "" if v is None else str(v)


async def generate_hl7_file(discharges, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:

        await f.write("FHS|^~\\&|||||||HOSP1||I\n")
        await f.write("BHS|^~\\&|||||202602~202602\n")

        for i, r in enumerate(discharges, start=1):

            # MSH
            await f.write(
                f"MSH|^~\\&|||||{fmt_date(r['discharge_datetime'])}||"
                f"ADT^A03^ADT_A03|{safe(r['ticket_number'])}|P|2.6|||||||||"
                f"{safe(r['profile_id'])}|^^^^^^^^^{safe(r['installation_code'])}\n"
            )

            # EVN
            await f.write(
                f"EVN|A03|{fmt_date(r['discharge_datetime'])}|||{safe(r['operator_id'])}\n"
            )

            # PID
            await f.write(
                f"PID||{safe(r['profile_id'])}|{safe(r['amka'])}^^^^AMKA||"
                f"{safe(r['last_name'])}^{safe(r['first_name'])}||"
                f"{safe(r['dob_hl7'])}|{safe(r['sex_val'])}||||||||||||||||||||||\n"
            )

            # PV1
            await f.write(
                f"PV1||I|{safe(r['location_code'])}||||{safe(r['doctor_amka'])}^|||||||||||0|"
                f"{safe(r['ticket_number'])}||||||||||||||||||||||||||"
                f"{fmt_date(r['admit_datetime'])}|||||{safe(r['ticket_number'])}\n"
            )

            # DG1
            await f.write(
                f"DG1|1|ICD-10|{safe(r['icd10_code'])}|{safe(r['icd10_desc'])}|"
                f"{safe(r['icd10_date'])}|D\n"
            )

        await f.write(f"BTS|{len(discharges)}||0.00\n")

    return out_path
