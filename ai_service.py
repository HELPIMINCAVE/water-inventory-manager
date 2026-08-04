import os
from typing import Optional
from groq import Groq
from models import ReorderAlert


class AIService:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def generate_refill_reminder(
        self, alert: ReorderAlert, station_name: str = "Water Station"
    ) -> str:
        if self.client is None:
            return (
                f"Hi {alert.customer_name}! It's been {alert.days_since_last_refill} days since "
                f"your last water refill at {station_name}. Reply to order your next container!"
            )

        prompt = f"""
                You are a friendly assistant for a local mineral water refilling station named "{station_name}".
                Write a short, polite SMS reminder (under 160 characters) for a customer who is overdue for a water refill.

                Customer Details:
                - Name: {alert.customer_name}
                - Days since last refill: {alert.days_since_last_refill} days

                Guidelines:
                - Keep it friendly, short, and professional.
                - Include a clear call-to-action to reorder.
                - Do not include hashtags or subject lines.
                """

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You write concise, high-converting SMS marketing messages for small businesses.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=100,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return (
                f"Hi {alert.customer_name}! Friendly reminder from {station_name}: "
                f"Your water container might be running low. Contact us today for a quick refill!"
            )
    