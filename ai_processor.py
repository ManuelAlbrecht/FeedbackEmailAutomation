# ai_processor.py

import os
import openai
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID_COMPOSE = os.getenv("ASSISTANT_ID_COMPOSE")
ASSISTANT_ID_ANALYZE = os.getenv("ASSISTANT_ID_ANALYZE")


class ComposeAssistant:
    """
    Uses the 'ASSISTANT_ID_COMPOSE' from .env to generate feedback emails.
    """
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.assistant_id = ASSISTANT_ID_COMPOSE

    def generate_email(self, user_message):
        """
        user_message: A string containing info about the deal (Anrede, Name, Date, Leistung, Status, etc.)
        Returns a single string with the final email content (body only).
        """
        try:
            thread = self.client.beta.threads.create()

            # Add user message (the structured details of the deal)
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_message
            )

            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )

            # Poll until "completed"
            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )

            # Retrieve final message
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data:
                if msg.role == "assistant":
                    return msg.content[0].text.value

            return "No email content generated"
        except Exception as e:
            return f"Error generating email: {str(e)}"


class AnalyzeAssistant:
    """
    Uses the 'ASSISTANT_ID_ANALYZE' from .env to analyze replies
    and produce:
      - A 'Feedback' category
      - A short 'Zusammenfassung' (2-3 lines)
      - Full 'Original' text
    in one structured block.

    The required instructions for strictly formatted output
    (including the new 'Zusammenfassung:' line) must be set
    in the OpenAI Assistant’s own system/prompt configuration.
    """

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.assistant_id = ASSISTANT_ID_ANALYZE

    def analyze_reply(self, reply_text):
        """
        reply_text: The raw text of the user's reply email.

        Expected final output (assuming the system instructions are in place):
            Anrede: [Herr/Frau]
            Name: [...]
            Email: [...]
            Telefon: [...]
            Status: [Gewonnen/Verloren]
            Feedback: [Preis, Angebot, ...]
            Zusammenfassung: [2-3 lines summarizing the response]
            Original: [Original email content]

        Returns the entire structured text from the assistant.
        """
        try:
            thread = self.client.beta.threads.create()

            # Add the user's message (the actual reply text)
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=reply_text
            )

            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )

            # Poll until "completed"
            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )

            # Retrieve the final message
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data:
                if msg.role == "assistant":
                    return msg.content[0].text.value

            return "No analysis result"
        except Exception as e:
            return f"Error analyzing email: {str(e)}"
