import logging
from typing import Optional

from app.scrapers.anthropic import AnthropicScraper
from app.database.repository import Repository

logger = logging.getLogger(__name__)


def process_anthropic_markdown(limit: Optional[int] = None) -> dict:
    scraper = AnthropicScraper()
    repo = Repository()
    articles = repo.get_anthropic_articles_without_markdown(limit=limit)
    processed = 0
    failed = 0

    for article in articles:
        try:
            markdown = scraper.url_to_markdown(article.url)
            if markdown:
                repo.update_anthropic_article_markdown(article.guid, markdown)
                processed += 1
                logger.info(
                    "operation=anthropic.process_markdown guid=%s status=success",
                    article.guid,
                )
            else:
                failed += 1
                logger.warning(
                    "operation=anthropic.process_markdown guid=%s status=failed_retryable",
                    article.guid,
                )
        except Exception:
            failed += 1
            logger.exception(
                "operation=anthropic.process_markdown guid=%s status=failed",
                article.guid,
            )

    result = {"total": len(articles), "processed": processed, "failed": failed}
    logger.info("operation=anthropic.process_markdown status=complete results=%s", result)
    return result


if __name__ == "__main__":
    print(process_anthropic_markdown())
