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

async def generate_hl7_file(
    discharges,
    out_path,
    job_id,
    job_installation_code,
    total_amount,
    covered_amount,
    patient_amount,
    invoice_number,
    contract_number,
    installation_descr,
    payer_taxid,
    payer_doy
):

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:

        # ============================================================
        # FILE HEADER
        # ============================================================
        await f.write("FHS|^~\\&|||||||HOSP1||I\n")

        # ============================================================
        # BHS + Z03 INVOICE HEADER BLOCK
        # ============================================================
        #job_id = job["job_id"]
        # Example: hl7_discharges_75752_2026-01-01_2026-05-05

        parts = job_id.split("_")

        start_date = parts[-2]  # "2026-01-01"
        end_date = parts[-1]  # "2026-05-05"

        start_year, start_month, _ = start_date.split("-")
        end_year, end_month, _ = end_date.split("-")

        bhs_period = f"{start_year}{start_month}~{end_year}{end_month}"

        await f.write(f"BHS|^~\\&|||||{bhs_period}\n")


        await f.write("MSH|^~\\&|||||||ZHC^Z03^ZHC_Z03|MSGID00001|P|2.6\n")

        # DYNAMIC IVC
        await f.write(
            f"IVC|{invoice_number}||{contract_number}|OR|NORM|FS|20260316|||"
            f"{installation_descr}^^^^^^^^^{safe(job_installation_code)}|"
            f"ΕΟΠΥΥ||||||||||"
            f"{total_amount:.2f}|{covered_amount:.2f}|{patient_amount:.2f}"
            f"||||{payer_taxid} {payer_doy}\n"
        )

        await f.write("BTS|1\n")

        # ============================================================
        # Z04 DETAIL BLOCKS
        # ============================================================
        for idx, r in enumerate(discharges, start=2):

            await f.write("BHS|^~\\&|||||202602~202602\n")

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

            # ============================================================
            # MULTI-DIAGNOSIS: DG1 + ZKE + PSL + ZSL
            # ============================================================
            diags = r.get("diagnoses") or []

            if not diags:
                # fallback to single icd10_* fields if diagnoses is empty
                await f.write(
                    f"DG1|1|ICD-10|{safe(r['icd10_code'])}|"
                    f"{safe(r['icd10_desc'])}||D\n"
                )
                # PSL/ZSL fallback (keep your old hardcoded values if you want)
                await f.write(
                    f"PSL|||1||||6^{safe(r.get('ken_code', ''))}|6||"
                    f"{fmt(r['discharge_datetime'])}|{fmt(r['discharge_datetime'])}|"
                    f"0.0|||{safe(r.get('total_amount', 0))}|{safe(r.get('covered_amount', 0))}|||||NO|||||||||\n"
                )
                await f.write(
                    f"ZSL|||||1|1|100.00|{safe(r.get('total_amount', 0))}|"
                    f"{safe(r.get('patient_participation_perc', 0))}|"
                    f"{safe(r.get('patient_amount', 0))}|0.00||0|0|0.00|0.00|0|\n"
                )
            else:
                for i, d in enumerate(diags, start=1):
                    icd10_code = safe(d.get("icd10_code"))
                    icd10_desc = safe(d.get("icd10_desc"))
                    icd10_date = safe(d.get("icd10_date"))
                    ken_code = safe(d.get("ken_code"))
                    total = float(d.get("total_amount", 0) or 0)
                    covered = float(d.get("covered_amount", 0) or 0)
                    patient = float(d.get("patient_amount", 0) or 0)
                    perc = float(d.get("patient_participation_perc", 0) or 0)

                    # DG1 per diagnosis
                    await f.write(
                        f"DG1|{i}|ICD-10|{icd10_code}|{icd10_desc}||D\n"
                    )

                    # ZKE per diagnosis (KEN + financials)
                    await f.write(
                        f"ZKE|{ken_code}|{total:.2f}|{covered:.2f}|{patient:.2f}|{perc:.2f}\n"
                    )

                    # PSL per diagnosis (KEN + amounts)
                    await f.write(
                        f"PSL|||{i}||||6^{ken_code}|6||"
                        f"{fmt(r['discharge_datetime'])}|{fmt(r['discharge_datetime'])}|"
                        f"0.0|||{total:.2f}|{covered:.2f}|||||NO|||||||||\n"
                    )

                    # ZSL per diagnosis (participation + patient amount)
                    await f.write(
                        f"ZSL|||||{i}|{i}|100.00|{total:.2f}|{perc:.2f}|{patient:.2f}|0.00||0|0|0.00|0.00|0|\n"
                    )

            # BTS for this Z04 block
            await f.write("BTS|1\n")

    return out_path
