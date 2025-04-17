# main.py
import os
import time
import re
import uuid
import requests
from datetime import datetime
from dotenv import load_dotenv
import pytz

from logging_service import setup_logging
from zoho_crm import ZohoCRMService
from email_handler import EmailHandler
from ai_processor import ComposeAssistant, AnalyzeAssistant

load_dotenv()
logger = setup_logging()

# ──────────── ENV ────────────
ZOHO_CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

SMTP_SERVER  = os.getenv("SMTP_SERVER")
SMTP_PORT    = int(os.getenv("SMTP_PORT", 465))
IMAP_SERVER  = os.getenv("IMAP_SERVER")
IMAP_PORT    = int(os.getenv("IMAP_PORT", 993))
EMAIL_USER   = os.getenv("EMAIL_USERNAME")
EMAIL_PASS   = os.getenv("EMAIL_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

# ──────────── HELPERS ────────────
def associate_email_with_deal(zoho, deal_id, from_email, to_email, subject, content, sent=True):
    url = f"https://www.zohoapis.eu/crm/v3/Deals/{deal_id}/actions/associate_email"
    headers = {
        "Authorization": f"Zoho-oauthtoken {zoho.access_token}",
        "Content-Type": "application/json"
    }

    berlin = pytz.timezone("Europe/Berlin")
    now_iso = datetime.now(berlin).replace(microsecond=0).isoformat()
    msg_id  = f"<{uuid.uuid4()}@erdbaron.com>"

    payload = {
        "Emails": [
            {
                "from": {"email": from_email},
                "to":   [{"email": to_email}],
                "subject": subject,
                "content": content,
                "date_time": now_iso,
                "sent": sent,
                "original_message_id": msg_id
            }
        ]
    }

    r = requests.post(url, headers=headers, json=payload)
    if r.status_code == 401:  # refresh token if needed
        zoho.access_token = zoho._get_access_token()
        headers["Authorization"] = f"Zoho-oauthtoken {zoho.access_token}"
        r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    logger.info(f"Associate email response: {r.status_code}")

# ──────────── MAIN LOOP ────────────
def main_loop():
    logger.info("Initializing services")

    zoho = ZohoCRMService(ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN)
    email_handler = EmailHandler(
        smtp_server=SMTP_SERVER,
        smtp_port=SMTP_PORT,
        imap_server=IMAP_SERVER,
        imap_port=IMAP_PORT,
        username=EMAIL_USER,
        password=EMAIL_PASS,
        sender=SENDER_EMAIL
    )
    compose_assistant = ComposeAssistant()
    analyze_assistant = AnalyzeAssistant()
    module_name = "Deals"

    logger.info("Automation running ...")

    while True:
        try:
            # ── SEND FEEDBACK EMAILS ──
            deals_to_send = zoho.search_records(module_name, "(Feedback_Email:equals:Senden)")
            for deal in deals_to_send:
                deal_id   = deal["id"]
                anrede    = deal.get("Anrede", "")
                vorname   = deal.get("Vorname", "")
                nachname  = deal.get("Nachname", "")
                stage     = deal.get("Stage", "")
                service   = deal.get("Leistung_Lieferung", "")
                desc      = deal.get("Projektmanager_Feedback", "")
                created_raw = deal.get("Created_Time", "")
                try:
                    created_date = datetime.fromisoformat(created_raw).strftime("%d.%m.%Y")
                except Exception:
                    created_date = ""
                recipient = deal.get("E_Mail", "")
                if not recipient:
                    logger.warning(f"Deal {deal_id}: no email, skipped")
                    continue

                # prompt for Compose Assistant
                user_message = f"""
Anrede: {anrede}
Vorname: {vorname}
Nachname: {nachname}
Status: {stage}
Leistung: {service}
Datum der Anfrage: {created_date}
Extra Info: {desc}
"""

                raw_response = compose_assistant.generate_email(user_message).lstrip()

                # split subject + body
                first_line, *rest = raw_response.splitlines()
                m_sub = re.match(r"^(?:Betreff|Subject):\s*(.*)", first_line, re.IGNORECASE)
                if m_sub:
                    subject_line = m_sub.group(1).strip() or f"Feedback erbeten, {vorname} {nachname}"
                    email_body   = "\n".join(rest).lstrip()
                else:
                    subject_line = f"Feedback erbeten, {vorname} {nachname}"
                    email_body   = raw_response

                # send email
                email_handler.send_email(recipient, subject_line, email_body)
                logger.info(f"Sent to {recipient} | Subject: {subject_line}")

                associate_email_with_deal(
                    zoho, deal_id, SENDER_EMAIL, recipient, subject_line, email_body, sent=True
                )
                zoho.update_record(module_name, deal_id, {"Feedback_Email": "Gesendet"})

            # ── CHECK INCOMING REPLIES ──
            new_emails = email_handler.check_incoming_emails()
            for sender_email, body_text in new_emails:
                deals = zoho.search_records(module_name, f"(E_Mail:equals:{sender_email})")
                if not deals:
                    logger.info(f"No deal for {sender_email}")
                    continue
                deal_id = deals[0]["id"]

                analysis = analyze_assistant.analyze_reply(body_text)
                m_feed = re.search(r"Feedback:\s*([^\n]+)", analysis)
                feedback_val = m_feed.group(1).strip() if m_feed else "Andere"
                m_sum = re.search(
                    r"Zusammenfassung:\s*(.*?)(?=\n[A-Z][a-zA-ZäöüÄÖÜß]+:|$)",
                    analysis,
                    re.DOTALL
                )
                summary_val = m_sum.group(1).strip() if m_sum else ""

                zoho.update_record(
                    module_name,
                    deal_id,
                    {
                        "Grund": feedback_val,
                        "Zusammenfassung_des_Feedbacks": summary_val
                    }
                )
                logger.info(f"Deal {deal_id} updated (Grund={feedback_val})")

                associate_email_with_deal(
                    zoho, deal_id, sender_email, SENDER_EMAIL, "Re: Feedback", body_text, sent=False
                )

        except Exception as e:
            logger.error(f"Loop error: {e}", exc_info=True)

        time.sleep(60)

# ─────────────────────────────
if __name__ == "__main__":
    main_loop()
