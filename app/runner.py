import logging

from app.config import YOUTUBE_CHANNELS
from app.scrapers.youtube import YouTubeScraper
from app.scrapers.openai import OpenAIScraper
from app.scrapers.anthropic import AnthropicScraper
from app.database.repository import Repository

logger = logging.getLogger(__name__)


def _new_source_status() -> dict:
    return {"status": "success", "fetched": 0, "persisted": 0, "errors": []}


def _record_error(status: dict, stage: str, error: Exception) -> None:
    status["errors"].append({
        "stage": stage,
        "error_type": type(error).__name__,
        "message": str(error),
    })
    logger.exception("operation=scraping status=failed stage=%s", stage)


def _rollback_repository(repo: Repository) -> None:
    """Clear a failed SQLAlchemy transaction before attempting another source."""
    session = getattr(repo, "session", None)
    rollback = getattr(session, "rollback", None)
    if callable(rollback):
        try:
            rollback()
        except Exception:
            logger.exception("operation=scraping.database_rollback status=failed")


def run_scrapers(hours: int = 24) -> dict:
    """Scrape and persist each source independently so one outage does not block others."""
    statuses = {
        "youtube": _new_source_status(),
        "openai": _new_source_status(),
        "anthropic": _new_source_status(),
    }
    youtube_videos = []
    youtube_records = []
    openai_articles = []
    anthropic_articles = []

    youtube_scraper = YouTubeScraper()
    openai_scraper = OpenAIScraper()
    anthropic_scraper = AnthropicScraper()
    repo = Repository()

    for channel_id in YOUTUBE_CHANNELS:
        try:
            videos = youtube_scraper.get_latest_videos(channel_id, hours=hours)
            youtube_videos.extend(videos)
            youtube_records.extend((channel_id, video) for video in videos)
            statuses["youtube"]["fetched"] += len(videos)
        except Exception as error:
            _record_error(statuses["youtube"], f"fetch_channel:{channel_id}", error)

    try:
        openai_articles = openai_scraper.get_articles(hours=hours)
        statuses["openai"]["fetched"] = len(openai_articles)
    except Exception as error:
        _record_error(statuses["openai"], "fetch_rss", error)

    try:
        anthropic_articles = anthropic_scraper.get_articles(hours=hours)
        statuses["anthropic"]["fetched"] = len(anthropic_articles)
    except Exception as error:
        _record_error(statuses["anthropic"], "fetch_rss", error)

    # Persistence is isolated per source. Roll back a failed transaction so a
    # later source can still be saved using the same SQLAlchemy session.
    if youtube_records:
        try:
            statuses["youtube"]["persisted"] = repo.bulk_create_youtube_videos([
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "channel_id": channel_id,
                    "published_at": video.published_at,
                    "description": video.description,
                    "transcript": video.transcript,
                }
                for channel_id, video in youtube_records
            ])
        except Exception as error:
            _record_error(statuses["youtube"], "persist", error)
            _rollback_repository(repo)

    if openai_articles:
        try:
            statuses["openai"]["persisted"] = repo.bulk_create_openai_articles([
                {
                    "guid": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at,
                    "description": article.description,
                    "category": article.category,
                }
                for article in openai_articles
            ])
        except Exception as error:
            _record_error(statuses["openai"], "persist", error)
            _rollback_repository(repo)

    if anthropic_articles:
        try:
            statuses["anthropic"]["persisted"] = repo.bulk_create_anthropic_articles([
                {
                    "guid": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at,
                    "description": article.description,
                    "category": article.category,
                }
                for article in anthropic_articles
            ])
        except Exception as error:
            _record_error(statuses["anthropic"], "persist", error)
            _rollback_repository(repo)

    for source, status in statuses.items():
        if status["errors"]:
            status["status"] = "partial_failure" if status["fetched"] else "failed"
        else:
            status["status"] = "success"
        logger.info(
            "operation=scraping.%s status=%s fetched=%d persisted=%d error_count=%d",
            source, status["status"], status["fetched"], status["persisted"], len(status["errors"]),
        )

    return {
        "youtube": youtube_videos,
        "openai": openai_articles,
        "anthropic": anthropic_articles,
        "source_status": statuses,
    }


if __name__ == "__main__":
    results = run_scrapers(hours=24)
    print({source: len(results[source]) for source in ("youtube", "openai", "anthropic")})
    print(results["source_status"])
