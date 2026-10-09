import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig

from app.utils.retry import retry_call

logger = logging.getLogger(__name__)


class Transcript(BaseModel):
    text: str


class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


class YouTubeScraper:
    def __init__(self):
        proxy_config = None
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")

        if proxy_username and proxy_password:
            proxy_config = WebshareProxyConfig(
                proxy_username=proxy_username,
                proxy_password=proxy_password,
            )

        self.transcript_api = YouTubeTranscriptApi(proxy_config=proxy_config)

    def _get_rss_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def _extract_video_id(self, video_url: str) -> str:
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript = retry_call(
                "youtube.fetch_transcript",
                lambda: self.transcript_api.fetch(video_id),
            )
            text = " ".join(snippet.text for snippet in transcript.snippets)
            if not text.strip():
                logger.warning(
                    "operation=youtube.fetch_transcript status=empty_transcript video_id=%s",
                    video_id,
                )
                return None
            return Transcript(text=text)
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.info(
                "operation=youtube.fetch_transcript status=permanently_unavailable video_id=%s",
                video_id,
            )
            return None
        except Exception:
            # Transient failures propagate to the processor, which leaves the DB field
            # NULL so a later pipeline run can retry. Do not cache a failure marker.
            logger.exception(
                "operation=youtube.fetch_transcript status=failed video_id=%s",
                video_id,
            )
            raise

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> list[ChannelVideo]:
        feed = feedparser.parse(self._get_rss_url(channel_id))
        if not feed.entries:
            logger.warning("operation=youtube.fetch_feed status=empty_feed channel_id=%s", channel_id)
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos = []
        for entry in feed.entries:
            if "/shorts/" in entry.link:
                continue
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                video_id = self._extract_video_id(entry.link)
                videos.append(ChannelVideo(
                    title=entry.title,
                    url=entry.link,
                    video_id=video_id,
                    published_at=published_time,
                    description=entry.get("summary", ""),
                ))
        return videos

    def scrape_channel(self, channel_id: str, hours: int = 150) -> list[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)
        result = []
        for video in videos:
            try:
                transcript = self.get_transcript(video.video_id)
            except Exception:
                logger.warning(
                    "operation=youtube.scrape_channel status=transcript_pending video_id=%s",
                    video.video_id,
                )
                transcript = None
            result.append(video.model_copy(update={"transcript": transcript.text if transcript else None}))
        return result


if __name__ == "__main__":
    scraper = YouTubeScraper()
    transcript: Transcript = scraper.get_transcript("jqd6_bbjhS8")
    print(transcript.text)
    channel_videos: List[ChannelVideo] = scraper.scrape_channel("UCn8ujwUInbJkBhffxqAPBVQ", hours=200)
