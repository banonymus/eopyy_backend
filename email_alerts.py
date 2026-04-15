import smtplib
from email.mime.text import MIMEText
import os

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")



from email.mime.multipart import MIMEMultipart


from email_templates import build_error_email_html

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

def send_error_email(ticket_number, error_message):
    if not ALERT_EMAIL_TO:
        return

    html_body = build_error_email_html(ticket_number, error_message)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"EOPYY Error Alert — Ticket {ticket_number}"
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL_TO

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [ALERT_EMAIL_TO], msg.as_string())
