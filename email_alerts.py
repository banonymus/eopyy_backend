import smtplib
from email.mime.text import MIMEText
import os

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

def send_error_email(ticket_number, error_message):
    if not ALERT_EMAIL_TO:
        return

    msg = MIMEText(f"Error for ticket {ticket_number}:\n\n{error_message}")
    msg["Subject"] = f"EOPYY Error Alert: {ticket_number}"
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [ALERT_EMAIL_TO], msg.as_string())
