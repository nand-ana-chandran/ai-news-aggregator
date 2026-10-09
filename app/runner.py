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
    status["status"] = "partial_failure" if status["fetched"] else "failed"
    logger.exception("operation=scraping.%s status=failed stage=%s", stage, stage)


def run_scrapers(hours: int = 24) -> dict:
    """Scrape and persist each source independently so one outage does not block others."""
    statuses = {
        "youtube": _new_source_status(),
        "openai": _new_source_status(),
        "anthropic": _new_source_status(),
    }
    youtube_videos = []
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

    # Persistence is isolated per source. A database error for one source should
    # not prevent records from other sources from being saved.
    if youtube_videos:
        try:
            video_dicts = [
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "channel_id": next(
                        (channel_id for channel_id in YOUTUBE_CHANNELS
                         if f"channel_id={channel_id}" in video.url),
                        "",
                    ),
                    "published_at": video.published_at,
                    "description": video.description,
                    "transcript": video.transcript,
                }
                for video in youtube_videos
            ]
            statuses["youtube"]["persisted"] = repo.bulk_create_youtube_videos(video_dicts)
        except Exception as error:
            _record_error(statuses["youtube"], "persist", error)

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

    for source, status in statuses.items():
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
