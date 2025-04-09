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

# Zoho
ZOHO_CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

# Email
SMTP_SERVER  = os.getenv("SMTP_SERVER")
SMTP_PORT    = int(os.getenv("SMTP_PORT", 465))
IMAP_SERVER  = os.getenv("IMAP_SERVER")
IMAP_PORT    = int(os.getenv("IMAP_PORT", 993))
EMAIL_USER   = os.getenv("EMAIL_USERNAME")
EMAIL_PASS   = os.getenv("EMAIL_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")


def associate_email_with_deal(zoho, deal_id, from_email, to_email, subject, content, sent=True):
    url = f"https://www.zohoapis.eu/crm/v3/Deals/{deal_id}/actions/associate_email"
    headers = {
        "Authorization": f"Zoho-oauthtoken {zoho.access_token}",
        "Content-Type": "application/json"
    }

    msg_id = f"<{uuid.uuid4()}@erdbaron.com>"
    berlin = pytz.timezone("Europe/Berlin")
    now_iso = datetime.now(berlin).replace(microsecond=0).isoformat()

    payload = {
        "Emails": [
            {
                "from": {"email": from_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "content": content,
                "date_time": now_iso,
                "sent": sent,
                "original_message_id": msg_id
            }
        ]
    }

    r = requests.post(url, headers=headers, json=payload)
    logger.info(f"Associate email response: {r.status_code}, {r.text}")
    if r.status_code == 401:
        logger.warning("Access token expired, refreshing and retrying...")
        zoho.access_token = zoho._get_access_token()
        headers["Authorization"] = f"Zoho-oauthtoken {zoho.access_token}"
        r = requests.post(url, headers=headers, json=payload)
        logger.info(f"Second attempt response: {r.status_code}, {r.text}")

    r.raise_for_status()


def main_loop():
    logger.info("Initializing services...")

    zoho = ZohoCRMService(
        client_id=ZOHO_CLIENT_ID,
        client_secret=ZOHO_CLIENT_SECRET,
        refresh_token=ZOHO_REFRESH_TOKEN
    )

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

    logger.info("Starting feedback email loop...")

    while True:
        try:
            logger.info("Checking deals that need an email...")
            try:
                deals_to_send = zoho.search_records(module_name, "(Feedback_Email:equals:Senden)")
            except Exception as e_deals:
                logger.error(f"Error fetching deals: {e_deals}", exc_info=True)
                deals_to_send = []

            for deal in deals_to_send:
                deal_id = deal["id"]
                anrede   = deal.get("Anrede", "")
                vorname  = deal.get("Vorname", "")
                nachname = deal.get("Nachname", "")
                stage    = deal.get("Stage", "")
                service  = deal.get("Leistung_Lieferung", "")
                desc     = deal.get("Projektmanager_Feedback", "")
                recipient= deal.get("E_Mail", "")

                if not recipient:
                    logger.warning(f"Deal {deal_id}: no E_Mail, skipping.")
                    continue

                user_message = f"""
Anrede: {anrede}
Vorname: {vorname}
Nachname: {nachname}
Status: {stage}
Leistung: {service}
Extra Info: {desc}
"""
                email_body = compose_assistant.generate_email(user_message)
                subject_line = f"Feedback erbeten, {vorname} {nachname}"

                email_handler.send_email(recipient, subject_line, email_body)
                logger.info(f"Email sent to {recipient}")

                associate_email_with_deal(zoho, deal_id, SENDER_EMAIL, recipient, subject_line, email_body, sent=True)
                logger.info(f"Email linked to deal {deal_id} and sent to {recipient}")

                zoho.update_record(module_name, deal_id, {"Feedback_Email": "Gesendet"})
                logger.info(f"Deal {deal_id} updated to 'Gesendet'")

            logger.info("Checking inbox for new emails...")
            new_emails = email_handler.check_incoming_emails()
            logger.info(f"Fetched {len(new_emails)} new emails to analyze.")

            for (sender_email, body_text) in new_emails:
                try:
                    matching_deals = zoho.search_records(module_name, f"(E_Mail:equals:{sender_email})")
                except Exception as e_deals_inbox:
                    logger.error(f"Error searching deals for {sender_email}: {e_deals_inbox}", exc_info=True)
                    matching_deals = []

                if not matching_deals:
                    logger.info(f"No deals found for {sender_email}, skipping reason update.")
                    continue

                matched_deal = matching_deals[0]
                deal_id = matched_deal["id"]

                analysis_result = analyze_assistant.analyze_reply(body_text)
                logger.info(f"For {sender_email}, analysis => {analysis_result}")

                feedback_value = "Andere"
                match = re.search(r"Feedback:\s*([^\n]+)", analysis_result)
                if match:
                    feedback_value = match.group(1).strip()

                zoho.update_record(module_name, deal_id, {"Grund": feedback_value})
                logger.info(f"Deal {deal_id} 'Grund' => {feedback_value}")

                associate_email_with_deal(zoho, deal_id, sender_email, SENDER_EMAIL, "Re: Feedback", body_text, sent=False)

        except Exception as e_main:
            logger.error(f"Error in main loop: {e_main}", exc_info=True)

        logger.info("Sleeping for 60 seconds...")
        time.sleep(60)


if __name__ == "__main__":
    main_loop()
