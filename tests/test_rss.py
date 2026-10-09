import unittest
from unittest.mock import Mock, patch

from app.scrapers.rss import fetch_rss_feed


class RSSFetchingTests(unittest.TestCase):
    def make_response(self, content, status_code=200):
        response = Mock()
        response.content = content
        response.status_code = status_code
        response.raise_for_status.return_value = None
        return response

    @patch("app.scrapers.rss.requests.get")
    def test_fetches_and_parses_valid_feed(self, get):
        get.return_value = self.make_response(
            b"<rss version='2.0'><channel><title>News</title>"
            b"<item><title>AI update</title><link>https://example.com/a</link>"
            b"<pubDate>Fri, 09 Oct 2026 10:00:00 GMT</pubDate></item>"
            b"</channel></rss>"
        )

        feed = fetch_rss_feed("https://example.com/rss", operation="test.rss")

        self.assertEqual(len(feed.entries), 1)
        self.assertEqual(feed.entries[0].title, "AI update")
        get.assert_called_once_with("https://example.com/rss", timeout=(5, 20))

    @patch("app.scrapers.rss.requests.get")
    def test_returns_valid_empty_feed(self, get):
        get.return_value = self.make_response(
            b"<rss version='2.0'><channel><title>News</title></channel></rss>"
        )

        feed = fetch_rss_feed("https://example.com/rss", operation="test.rss")

        self.assertEqual(len(feed.entries), 0)

    @patch("app.scrapers.rss.requests.get")
    def test_rejects_invalid_feed(self, get):
        get.return_value = self.make_response(b"this is not an RSS or Atom document")

        with self.assertRaises(ValueError):
            fetch_rss_feed("https://example.com/rss", operation="test.rss")

    @patch("app.scrapers.rss.retry_call")
    def test_uses_shared_retry_helper(self, retry):
        response = self.make_response(
            b"<rss version='2.0'><channel><title>News</title></channel></rss>"
        )
        retry.side_effect = lambda operation, callback: callback()
        with patch("app.scrapers.rss.requests.get", return_value=response):
            fetch_rss_feed("https://example.com/rss", operation="test.rss")

        self.assertEqual(retry.call_args.args[0], "test.rss")
        self.assertTrue(callable(retry.call_args.args[1]))


if __name__ == "__main__":
    unittest.main()
