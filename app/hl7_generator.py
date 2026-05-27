import datetime
import aiofiles
import os

def fmt(dt):
    if not dt:
        return ""
    if isinstance(dt, datetime.datetime):
        return dt.strftime("%Y%m%d%H%M")
    try:
        return datetime.datetime.strptime(dt, "%Y%m%d%H%M%S").strftime("%Y%m%d%H%M")
    except:
        pass
    try:
        return datetime.datetime.strptime(dt, "%Y%m%d%H%M").strftime("%Y%m%d%H%M")
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

        # --- FILE HEADER ---
        await f.write("FHS|^~\\&|||||||HOSP1||I\n")
        await f.write("BHS|^~\\&|||||202602~202602\n")

        # --- Z03 HEADER BLOCK (IVC) ---
        await f.write(
            "MSH|^~\\&|||||||ZHC^Z03^ZHC_Z03|MSGID00001|P|2.6\n"
        )

        # IVC segment (invoice header)
        await f.write(
            f"IVC|ΤΠΥ-000003||423474|OR|NORM|FS|20260316|||"
            f"ΙΔΙΩΤΙΚΗ Μ.Η.Ν. ΚΕΝΤΡΟ ΟΡΑΣΗΣ ΗΠΕΙΡΟΥ Α.Ε.^^^^^^^^^75752|"
            f"ΕΟΠΥΥ||||||||||34436.09|34436.09|0.00||||997489660 6311\n"
        )

        await f.write(f"BTS|1||34436.09\n")

        # --- SECOND BATCH HEADER ---
        await f.write("BHS|^~\\&|||||202602~202602\n")

        # --- Z04 DETAIL BLOCKS ---
        for idx, r in enumerate(discharges, start=2):

            msg_id = f"MSGID{idx:05d}"

            # MSH
            await f.write(
                f"MSH|^~\\&|||||||ZHC^Z04^ZHC_Z04|{msg_id}|P|2.6\n"
            )

            # PSG
            await f.write(
                f"PSG|{safe(r['ticket_number'])}|"
                f"{fmt(r['discharge_datetime'])}|"
                f"{safe(r['alt_visit_id'])}|"
                f"{fmt(r['discharge_datetime'])}||Y||1\n"
            )

            # ZSG
            await f.write(
                f"ZSG|||||||0|||||||{safe(r['country_code'])}|||||"
                f"{safe(r['ticket_number'])}|{safe(r['alt_visit_id'])}|0\n"
            )

            # PID
            await f.write(
                f"PID||{safe(r['profile_id'])}|{safe(r['amka'])}^^^^ΑΜΑ~"
                f"{safe(r['installation_code'])}^^^^ΦΟΡΕΑΣ||"
                f"{safe(r['last_name'])}^{safe(r['first_name'])}^ΑΓΝΩΣΤΟ||"
                f"{safe(r['dob_hl7'])}|{safe(r['sex_val'])}|||"
                f"^{safe(r['location_code'])}^000^^{safe(r['location_code'])}"
                f"^{safe(r['location_code'])}^||||||||||||0||0\n"
            )

            # PV1
            await f.write(
                f"PV1|I|||||{safe(r['doctor_amka'])}^|||||||||||1||1\n"
            )

            # PV2
            await f.write("PV2||||||||||||||||||||||||||||||||||||||||||U\n")

            # DG1
            await f.write(
                f"DG1|1|ICD-10|{safe(r['icd10_code'])}|"
                f"{safe(r['icd10_desc'])}||D\n"
            )

            # PSL
            await f.write(
                f"PSL|||1||||6^Ο16Α|6||"
                f"{fmt(r['discharge_datetime'])}|{fmt(r['discharge_datetime'])}|"
                f"0.0|||396.10|277.27|||||NO|||||||||\n"
            )

            # ZSL
            await f.write(
                f"ZSL|||||1|1|100.00|396.10|30.00|118.83|0.00||0|0|0.00|0.00|0|\n"
            )

        # END OF FILE
        await f.write(f"BTS|{len(discharges)}||0.00\n")

    return out_path
