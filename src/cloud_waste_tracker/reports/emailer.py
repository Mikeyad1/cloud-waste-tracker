# src/cloud_waste_tracker/reports/emailer.py
import smtplib
import ssl
import pathlib
import mimetypes
from email.message import EmailMessage

from cloud_waste_tracker.config.secrets import EMAIL_USER, EMAIL_PASS

# --- SMTP config ---
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

def send(to_addr: str, subject: str, body: str, files=None) -> None:
    """
    Send an email with optional attachments.

    :param to_addr: recipient email address
    :param subject: email subject
    :param body: email body
    :param files: list of files to attach (Paths or string paths)
    """
    files = files or []
    msg = EmailMessage()
    msg["From"] = EMAIL_USER
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach files if they exist
    for fp in files:
        p = pathlib.Path(fp)
        if not p.exists():
            print(f"[i] Skipping missing attachment: {p}")
            continue
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype, filename=p.name)

    # Send via Gmail SMTP
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls(context=ctx)
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

    print(f"[✓] Email sent from {EMAIL_USER} to {to_addr}")
