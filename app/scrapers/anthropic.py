import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
from docling.document_converter import DocumentConverter
from pydantic import BaseModel

from app.utils.retry import retry_call

logger = logging.getLogger(__name__)


class AnthropicArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None


class AnthropicScraper:
    def __init__(self):
        self.rss_urls = [
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        ]
        self.converter = DocumentConverter()

    def get_articles(self, hours: int = 24) -> List[AnthropicArticle]:
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles = []
        seen_guids = set()

        for rss_url in self.rss_urls:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                logger.warning("operation=anthropic.fetch_feed status=empty_feed source=%s", rss_url)
                continue

            for entry in feed.entries:
                published_parsed = getattr(entry, "published_parsed", None)
                if not published_parsed:
                    continue
                published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if published_time >= cutoff_time:
                    guid = entry.get("id", entry.get("link", ""))
                    if guid not in seen_guids:
                        seen_guids.add(guid)
                        articles.append(AnthropicArticle(
                            title=entry.get("title", ""),
                            description=entry.get("description", ""),
                            url=entry.get("link", ""),
                            guid=guid,
                            published_at=published_time,
                            category=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None,
                        ))
        return articles

    def url_to_markdown(self, url: str) -> Optional[str]:
        try:
            result = retry_call(
                "anthropic.extract_article",
                lambda: self.converter.convert(url),
            )
            markdown = result.document.export_to_markdown()
            if not markdown.strip():
                logger.warning("operation=anthropic.extract_article status=empty_content url=%s", url)
                return None
            return markdown
        except Exception:
            # Return None without persisting a failure marker. The database record
            # stays eligible for extraction on the next pipeline run.
            logger.exception("operation=anthropic.extract_article status=failed_retryable url=%s", url)
            return None


if __name__ == "__main__":
    scraper = AnthropicScraper()
    articles: List[AnthropicArticle] = scraper.get_articles(hours=100)
    markdown: Optional[str] = scraper.url_to_markdown(articles[1].url) if len(articles) > 1 else None
    print(markdown)
