import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from docling.document_converter import DocumentConverter
from pydantic import BaseModel

from app.scrapers.rss import fetch_rss_feed

logger = logging.getLogger(__name__)


class OpenAIArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None


class OpenAIScraper:
    def __init__(self):
        self.rss_url = "https://openai.com/news/rss.xml"
        self.converter = DocumentConverter()

    def get_articles(self, hours: int = 24) -> List[OpenAIArticle]:
        feed = fetch_rss_feed(self.rss_url, operation="openai.fetch_rss")
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles = []

        for entry in feed.entries:
            published_parsed = getattr(entry, "published_parsed", None)
            if not published_parsed:
                logger.warning(
                    "operation=openai.parse_article status=missing_published_date url=%s",
                    entry.get("link", ""),
                )
                continue

            published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                articles.append(OpenAIArticle(
                    title=entry.get("title", ""),
                    description=entry.get("description", ""),
                    url=entry.get("link", ""),
                    guid=entry.get("id", entry.get("link", "")),
                    published_at=published_time,
                    category=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None,
                ))

        logger.info(
            "operation=openai.get_articles status=success articles_found=%d hours=%d",
            len(articles), hours,
        )
        return articles


if __name__ == "__main__":
    scraper = OpenAIScraper()
    articles: List[OpenAIArticle] = scraper.get_articles(hours=50)
