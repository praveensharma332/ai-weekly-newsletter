import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger("newsletter.utils.email")

def send_newsletter_email(subject: str, html_content: str, attachment_path: Optional[str] = None) -> bool:
    """Sends the newsletter via SMTP to configured email addresses."""
    
    # 1. Validate SMTP Configuration
    if not all([settings.SMTP_USER, settings.SMTP_PASSWORD, settings.SMTP_TO_EMAIL]):
        logger.info("SMTP email credentials are not fully configured in .env. Skipping email dispatch.")
        return False

    sender_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    receiver_email = settings.SMTP_TO_EMAIL
    
    # 2. Build Multi-part email message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = receiver_email
    
    # Attach HTML body
    part_html = MIMEText(html_content, "html")
    message.attach(part_html)
    
    # 3. Handle File Attachment
    if attachment_path and os.path.exists(attachment_path):
        try:
            filename = os.path.basename(attachment_path)
            with open(attachment_path, "rb") as attachment:
                part_file = MIMEBase("application", "octet-stream")
                part_file.set_payload(attachment.read())
                
            encoders.encode_base64(part_file)
            part_file.add_header(
                "Content-Disposition",
                f"attachment; filename= {filename}",
            )
            message.attach(part_file)
            logger.info(f"Attached file: {attachment_path} to email.")
        except Exception as e:
            logger.error(f"Failed to attach file to email: {e}")

    # 4. Connect to SMTP Server and Transmit
    try:
        logger.info(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}...")
        
        # Connect using SSL or Standard port with STARTTLS
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            server.starttls()
            
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(sender_email, receiver_email.split(","), message.as_string())
        server.quit()
        
        logger.info(f"Newsletter email successfully dispatched to {receiver_email}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {e}")
        return False
