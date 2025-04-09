# email_handler.py

import imaplib
import smtplib
import ssl
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import logging

class EmailHandler:
    def __init__(self,
                 smtp_server,
                 smtp_port,
                 imap_server,
                 imap_port,
                 username,
                 password,
                 sender):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.sender = sender
        self.logger = logging.getLogger(__name__)

    def send_email(self, to_address, subject, body):
        """
        Send a plain text email using SMTP SSL.
        """
        msg = MIMEMultipart()
        msg["From"] = f"Vertrieb Erdbaron <{self.sender}>"
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(self.username, self.password)
                server.send_message(msg)
            self.logger.info(f"Email sent to {to_address}")
        except Exception as e:
            self.logger.error(f"Error sending email to {to_address}: {e}")

    def check_incoming_emails(self):
        """
        Check IMAP for UNSEEN emails, return list of (sender_email, body_text).
        """
        results = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.username, self.password)
            mail.select('"INBOX/Hide/vertrieb1@erdbaron.com"')

            search_criteria = '(UNSEEN SUBJECT "Feedback erbeten")'
            status, data = mail.search(None, search_criteria)
            if status != "OK":
                self.logger.info("No new emails or IMAP search error.")
                mail.close()
                mail.logout()
                return results

            for num in data[0].split():
                _, msg_data = mail.fetch(num, "(RFC822)")
                if msg_data and msg_data[0]:
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)

                    from_str = email_message.get("From", "")
                    sender_email = self.extract_email_address(from_str)
                    body_text = self.extract_plain_text(email_message)

                    # Mark as seen
                    mail.store(num, "+FLAGS", "\\Seen")

                    results.append((sender_email, body_text))

            mail.close()
            mail.logout()
        except Exception as e:
            self.logger.error(f"Error checking incoming emails: {e}")
        return results

    def extract_plain_text(self, msg):
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        return ""

    def extract_email_address(self, full_from_string):
        match = re.findall(r"<([^>]+)>", full_from_string)
        return match[0] if match else full_from_string
