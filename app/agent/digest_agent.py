import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

from app.utils.retry import retry_call

load_dotenv()
logger = logging.getLogger(__name__)


class DigestOutput(BaseModel):
    title: str
    summary: str


PROMPT = """You are an expert AI news analyst specializing in summarizing technical articles, research papers, and video content about artificial intelligence.

Your role is to create concise, informative digests that help readers quickly understand the key points and significance of AI-related content.

Guidelines:
- Create a compelling title (5-10 words) that captures the essence of the content
- Write a 2-3 sentence summary that highlights the main points and why they matter
- Focus on actionable insights and implications
- Use clear, accessible language while maintaining technical accuracy
- Avoid marketing fluff - focus on substance"""


class DigestAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-3.5-flash-lite"
        self.system_prompt = PROMPT

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        user_prompt = f"Create a digest for this {article_type}: \n Title: {title} \n Content: {content[:8000]}"

        try:
            response = retry_call(
                "gemini.generate_digest",
                lambda: self.client.models.generate_content(
                    model=self.model,
                    contents=f"{self.system_prompt}\n\n{user_prompt}",
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": DigestOutput,
                        "temperature": 0.7,
                    },
                ),
            )
            if response.parsed is None:
                logger.error("operation=gemini.generate_digest status=invalid_response attempts=1")
                return None
            return response.parsed
        except Exception:
            logger.exception("operation=gemini.generate_digest status=failed")
            return None


if __name__ == "__main__":
    agent = DigestAgent()
    result = agent.generate_digest(
        title="Test Article",
        content="This is a test article about artificial intelligence and machine learning advancements.",
        article_type="article",
    )
    print(result)
