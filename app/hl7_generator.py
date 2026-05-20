import datetime
import aiofiles
import os

def fmt_date(dt):
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.datetime.fromisoformat(dt)
        except:
            return dt.replace("-", "")[:8]
    return dt.strftime("%Y%m%d%H%M")

def safe(v):
    return "" if v is None else str(v)

async def generate_hl7_file(discharges, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total_amount = 0.0

    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
        await f.write("FHS|^~\\&|||||||HOSP1||I\n")
        await f.write("BHS|^~\\&|||||202602~202602\n")

        for i, r in enumerate(discharges, start=1):
            msg_id = f"MSGID{i:05d}"

            await f.write(
                f"MSH|^~\\&|||||{fmt_date(r['discharge_time'])}||"
                f"ADT^A03^ADT_A03|{r['ticket_number']}|P|2.6|||||||||"
                f"{r['patient_id']}|^^^^^^^^^{r['installation_code']}\n"
            )

            await f.write(
                f"EVN|A03|{fmt_date(r['discharge_time'])}|||{r['operator_id']}\n"
            )

            await f.write(
                f"PID||{r['patient_id']}|{r['amka']}^^^^AMKA||"
                f"{r['lastname']}^{r['firstname']}||{r['dob']}|{r['gender']}|||"
                f"^{r.get('address','')}^^{r.get('city','')}^^{r.get('postal','')}||"
                f"{r.get('phone','')}|||||{r.get('afm','')}|||||||||0||0\n"
            )

            await f.write(
                f"PV1||I|{r['location_code']}||||{r['doctor_amka']}^|||||||||||0|"
                f"{r['ticket_number']}||||||||||||||||||||||||||"
                f"{fmt_date(r['admission_time'])}|||||{r['ticket_number']}\n"
            )

            await f.write("PV2||||||||||||||||||||||||||||||||||||||||||U\n")

            await f.write(
                f"DG1|1|ICD-10|{r['diagnosis_code']}|{r['diagnosis_desc']}||D\n"
            )

            await f.write(
                f"PSL|||1||||{r['procedure_code']}|1||"
                f"{fmt_date(r['admission_time'])}|{fmt_date(r['discharge_time'])}|"
                f"0.0|||{r['price']:.2f}|{r['price']:.2f}|||||NO|||||||||\n"
            )

            await f.write(
                f"ZSL|||||1|1|100.00|{r['price']:.2f}|0.00|{r['price']:.2f}|0.00||"
                f"0|0|0.00|0.00|0|\n"
            )

            total_amount += float(r["price"])

        await f.write(f"BTS|{len(discharges)}||{total_amount:.2f}\n")

    return out_path

def fmt_date(dt):
    if not dt:
        return ""

    # Already datetime object
    if isinstance(dt, datetime.datetime):
        return dt.strftime("%Y%m%d%H%M")

    # Try ISO format first
    try:
        return datetime.datetime.fromisoformat(dt).strftime("%Y%m%d%H%M")
    except:
        pass

    # Try EOPYY format: YYYYMMDDHHMMSS
    try:
        return datetime.datetime.strptime(dt, "%Y%m%d%H%M%S").strftime("%Y%m%d%H%M")
    except:
        pass

    # Try YYYYMMDD
    try:
        return datetime.datetime.strptime(dt, "%Y%m%d").strftime("%Y%m%d%H%M")
    except:
        pass

    # Fallback: return raw
    return dt[:12]
