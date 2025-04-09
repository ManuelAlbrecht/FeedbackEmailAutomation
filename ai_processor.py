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
    Uses the 'COMPOSE_ASSISTANT_ID' from .env to generate feedback emails.
    """
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.assistant_id = ASSISTANT_ID_COMPOSE

    def generate_email(self, user_message):
        """
        user_message: A string containing info about the deal
        (Anrede, Name, Date, Leistung, Status, etc.)

        Returns a single string with the final email content.
        """
        try:
            thread = self.client.beta.threads.create()

            # Add user message
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
    Uses the 'ANALYZE_ASSISTANT_ID' from .env to analyze replies
    and produce a short reason or standardized format.
    """
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.assistant_id = ASSISTANT_ID_ANALYZE

    def analyze_reply(self, reply_text):
        """
        reply_text: The raw text of the user's reply email.

        Returns the final analysis result from the assistant
        (which might be a short phrase or a structured block).
        """
        try:
            thread = self.client.beta.threads.create()

            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=reply_text
            )

            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )

            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )

            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data:
                if msg.role == "assistant":
                    return msg.content[0].text.value

            return "No analysis result"
        except Exception as e:
            return f"Error analyzing email: {str(e)}"
