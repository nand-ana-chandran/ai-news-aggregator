import logging
from typing import Optional

from app.scrapers.youtube import YouTubeScraper
from app.database.repository import Repository

logger = logging.getLogger(__name__)
TRANSCRIPT_UNAVAILABLE_MARKER = "__UNAVAILABLE__"


def process_youtube_transcripts(limit: Optional[int] = None) -> dict:
    scraper = YouTubeScraper()
    repo = Repository()

    videos = repo.get_youtube_videos_without_transcript(limit=limit)
    processed = 0
    unavailable = 0
    failed = 0

    for video in videos:
        try:
            transcript_result = scraper.get_transcript(video.video_id)
            if transcript_result:
                repo.update_youtube_video_transcript(video.video_id, transcript_result.text)
                processed += 1
                status = "success"
            else:
                # Only explicit YouTube "no transcript" responses are cached.
                # Unexpected/transient errors must leave transcript NULL for a future retry.
                repo.update_youtube_video_transcript(video.video_id, TRANSCRIPT_UNAVAILABLE_MARKER)
                unavailable += 1
                status = "permanently_unavailable"
            logger.info(
                "operation=youtube.process_transcript video_id=%s status=%s",
                video.video_id, status,
            )
        except Exception:
            failed += 1
            logger.exception(
                "operation=youtube.process_transcript video_id=%s status=failed_retryable",
                video.video_id,
            )

    result = {
        "total": len(videos),
        "processed": processed,
        "unavailable": unavailable,
        "failed": failed,
    }
    logger.info("operation=youtube.process_transcripts status=complete results=%s", result)
    return result


if __name__ == "__main__":
    print(process_youtube_transcripts())
