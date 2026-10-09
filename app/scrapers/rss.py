"""HTTP-aware RSS fetching with bounded retries and explicit parse diagnostics."""

import logging

import feedparser
import requests

from app.utils.retry import retry_call

logger = logging.getLogger(__name__)


def fetch_rss_feed(url: str, *, operation: str):
    """Fetch an RSS feed with timeout/status checks, then parse its response.

    HTTP/network failures are retried by retry_call. An HTTP 4xx other than
    408/425/429 is treated as permanent. A valid but empty feed is returned as
    an empty feed; callers decide whether that is expected for their source.
    """
    def fetch_response():
        response = requests.get(url, timeout=(5, 20))
        response.raise_for_status()
        return response

    response = retry_call(operation, fetch_response)
    feed = feedparser.parse(response.content)

    if getattr(feed, "bozo", False):
        parse_error = getattr(feed, "bozo_exception", None)
        if feed.entries:
            logger.warning(
                "operation=%s status=partial_feed_parse entry_count=%d error_type=%s",
                operation, len(feed.entries), type(parse_error).__name__ if parse_error else "Unknown",
            )
        else:
            logger.error(
                "operation=%s status=invalid_feed error_type=%s",
                operation, type(parse_error).__name__ if parse_error else "Unknown",
            )
            raise ValueError(f"RSS feed could not be parsed: {url}")

    logger.info(
        "operation=%s status=%s entry_count=%d http_status=%d",
        operation, "success" if feed.entries else "empty_feed",
        len(feed.entries), response.status_code,
    )
    return feed
