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
    payer_doy,
    country_code,
    invoice_date
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

        paid = (covered_amount)
        # DYNAMIC IVC
        invoice_date = invoice_date.strftime("%Y%m%d")
        await f.write(
            f"IVC|{invoice_number}||{contract_number}|OR|NORM|FS|{invoice_date}|||"
            f"{installation_descr}^^^^^^^^^{safe(job_installation_code)}|"
            f"ΕΟΠΥΥ||||||||||"
            #f"{total_amount:.2f}|{covered_amount:.2f}|{patient_amount:.2f}"
            #f"{patient_amount:.2f}|{patient_amount:.2f}|{0:.2f}"
            
            f"{paid:.2f}|{paid:.2f}|{0:.2f}"
            f"||||{payer_taxid} {payer_doy}\n"
        )

        #await f.write(f"BTS|1||{total_amount:.2f}\n")
        await f.write(f"BTS|1||{patient_amount:.2f}\n")
        #await f.write("BHS|^~\\&|||||202602~202602\n")
        await f.write(f"BHS|^~\\&|||||{bhs_period}\n")
        # ============================================================
        # Z04 DETAIL BLOCKS
        # ============================================================
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
                #f"{safe(r['alt_visit_id'])}|"
                f"{safe(r['discharge_ticket_number'])}|"
                f"{fmt(r['discharge_datetime'])}||Y||1\n"
            )

            # ZSG
            await f.write(
                f"ZSG|||||||0|||||||{safe(r['country_code'])}|||||"
                f"{safe(r['ticket_number'])}|{safe(r['alt_visit_id'])}|0\n"
            )

            # PID
            sex_code = "1" if r["sex_val"] == "M" else "2"

            pid_fields = [
                "PID",  # PID-0
                "",  # PID-1
                safe(r["installation_code"]),  # PID-2
                f"{safe(r['ama'])}^^^^ΑΜΑ~10000^^^^ΦΟΡΕΑΣ",  # PID-3
                "",  # PID-4
                f"{safe(r['last_name'])}^{safe(r['first_name'])}^{safe(r['fathers_name'])}",  # PID-5
                "",  # PID-6
                safe(r["dob_hl7"]),  # PID-7
                sex_code,  # PID-8
                "",  # PID-9
                "",  # PID-10
                f"^{safe(r['address'])}^000^^{safe(r['city'])}^{safe(r['region'])}^{safe(r['location_code'])}",
                # PID-11
                "",  # PID-12
                safe(r["phone1_number"]),  # PID-13
                "",  # PID-14
                "",  # PID-15
                "",  # PID-16
                "",  # PID-17
                "",  # PID-18
                safe(r["ama"]),  # PID-19
                "",  # PID-20
                "",  # PID-21
                "",  # PID-22
                "",  # PID-23
                "",  # PID-24
                "",  # PID-25
                "",  # PID-26
                "",  # PID-27
                "",  # PID-28
                "0",  # PID-29
                "0",  # PID-30
            ]

            await f.write("|".join(pid_fields) + "\n")

            # PV1
            await f.write(
                f"PV1|I|||||"
                f"{safe(r['doctor_amka'])}^{safe(r['doctor_last'])}^{safe(r['doctor_first'])}"
                f"|||||||||||1||1\n"
            )

            # PV2
            await f.write("PV2||||||||||||||||||||||||||||||||||||||||||U\n")

            # ============================================================
            # MULTI-DIAGNOSIS: DG1 + ZKE + PSL + ZSL
            # ============================================================
            diags = r.get("diagnoses") or []
            block_total = 0.0
            if not diags:
                # fallback to single icd10_* fields if diagnoses is empty
                await f.write(
                    f"DG1|1|ICD-10|{safe(r['icd10_code'])}|"
                    f"{safe(r['icd10_desc'])}||D\n"
                )
                # PSL/ZSL fallback (keep your old hardcoded values if you want)
                await f.write(
                    f"PSL|||1||||1^{safe(r.get('ken_code', ''))}|1||"
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

                    block_total += total

                    # DG1 per diagnosis
                    await f.write(
                        f"DG1|{i}|ICD-10|{icd10_code}|{icd10_desc}||D\n"
                    )

                    # ZKE per diagnosis (KEN + financials)
                    #await f.write(
                       # f"ZKE|{ken_code}|{total:.2f}|{covered:.2f}|{patient:.2f}|{perc:.2f}\n"
                    #)

                    # PSL per diagnosis (KEN + amounts)
                    if ken_code == "00128":
                        psl_prefix = f"PSL|||{i}||||1^{ken_code}|1||"
                    else:
                        psl_prefix = f"PSL|||{i}||||6^{ken_code}|6||"

                    await f.write(
                        psl_prefix +
                        f"{fmt(r['discharge_datetime'])}|{fmt(r['discharge_datetime'])}|"
                        f"0.0|||{total:.2f}|{covered:.2f}|||||NO|||||||||\n"
                    )

                    # ZSL per diagnosis (participation + patient amount)
                    await f.write(
                        f"ZSL|||||{i}|{i}|100.00|{total:.2f}|{perc:.2f}|{patient:.2f}|0.00||0|0|0.00|0.00|0|\n"
                    )





    return out_path
