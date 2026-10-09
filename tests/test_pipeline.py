"""Regression tests for source isolation and database recovery in the scraping runner.

The scraper and repository imports are stubbed so these tests run without network
access, API credentials, a database, or heavyweight scraper dependencies.
"""
import importlib
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch


def _install_import_stubs():
    config = types.ModuleType("app.config")
    config.YOUTUBE_CHANNELS = ["channel-good", "channel-bad"]

    youtube = types.ModuleType("app.scrapers.youtube")
    youtube.YouTubeScraper = type("YouTubeScraper", (), {})

    openai = types.ModuleType("app.scrapers.openai")
    openai.OpenAIScraper = type("OpenAIScraper", (), {})

    anthropic = types.ModuleType("app.scrapers.anthropic")
    anthropic.AnthropicScraper = type("AnthropicScraper", (), {})

    repository = types.ModuleType("app.database.repository")
    repository.Repository = type("Repository", (), {})

    return {
        "app.config": config,
        "app.scrapers.youtube": youtube,
        "app.scrapers.openai": openai,
        "app.scrapers.anthropic": anthropic,
        "app.database.repository": repository,
    }


_STUBS = _install_import_stubs()
with patch.dict(sys.modules, _STUBS):
    from app import runner


class PipelineReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.youtube = Mock()
        self.openai = Mock()
        self.anthropic = Mock()
        self.repository = Mock()
        self.repository.session = Mock()

        runner.YOUTUBE_CHANNELS = ["channel-good", "channel-bad"]
        runner.YouTubeScraper = Mock(return_value=self.youtube)
        runner.OpenAIScraper = Mock(return_value=self.openai)
        runner.AnthropicScraper = Mock(return_value=self.anthropic)
        runner.Repository = Mock(return_value=self.repository)

        self.video = types.SimpleNamespace(
            video_id="video-1",
            title="A video",
            url="https://example.com/video-1",
            published_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
            description="description",
            transcript="transcript",
        )
        self.openai_article = types.SimpleNamespace(
            guid="openai-1",
            title="OpenAI news",
            url="https://example.com/openai",
            published_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
            description="description",
            category="research",
        )
        self.anthropic_article = types.SimpleNamespace(
            guid="anthropic-1",
            title="Anthropic news",
            url="https://example.com/anthropic",
            published_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
            description="description",
            category="research",
        )
        self.youtube.get_latest_videos.side_effect = (
            lambda channel_id, hours: [self.video]
            if channel_id == "channel-good"
            else (_ for _ in ()).throw(TimeoutError("channel temporarily unavailable"))
        )
        self.openai.get_articles.return_value = [self.openai_article]
        self.anthropic.get_articles.return_value = [self.anthropic_article]
        self.repository.bulk_create_youtube_videos.return_value = 1
        self.repository.bulk_create_openai_articles.return_value = 1
        self.repository.bulk_create_anthropic_articles.return_value = 1

    def test_failed_source_does_not_block_other_sources(self):
        result = runner.run_scrapers(hours=24)

        self.assertEqual(len(result["youtube"]), 1)
        self.assertEqual(len(result["openai"]), 1)
        self.assertEqual(len(result["anthropic"]), 1)
        self.assertEqual(result["source_status"]["youtube"]["status"], "partial_failure")
        self.assertEqual(result["source_status"]["youtube"]["fetched"], 1)
        self.assertEqual(result["source_status"]["openai"]["status"], "success")
        self.assertEqual(result["source_status"]["anthropic"]["status"], "success")
        self.repository.bulk_create_openai_articles.assert_called_once()
        self.repository.bulk_create_anthropic_articles.assert_called_once()

    def test_database_failure_rolls_back_and_other_sources_still_persist(self):
        self.repository.bulk_create_youtube_videos.side_effect = RuntimeError("database write failed")

        result = runner.run_scrapers(hours=24)

        self.repository.session.rollback.assert_called_once()
        self.repository.bulk_create_openai_articles.assert_called_once()
        self.repository.bulk_create_anthropic_articles.assert_called_once()
        self.assertEqual(result["source_status"]["youtube"]["status"], "partial_failure")
        self.assertEqual(result["source_status"]["youtube"]["errors"][0]["stage"], "persist")
        self.assertEqual(result["source_status"]["openai"]["persisted"], 1)
        self.assertEqual(result["source_status"]["anthropic"]["persisted"], 1)

    def test_all_fetch_failures_are_reported_without_attempting_empty_persistence(self):
        self.youtube.get_latest_videos.side_effect = TimeoutError("YouTube unavailable")
        self.openai.get_articles.side_effect = ConnectionError("OpenAI feed unavailable")
        self.anthropic.get_articles.side_effect = ValueError("invalid feed")

        result = runner.run_scrapers(hours=24)

        self.assertEqual(result["source_status"]["youtube"]["status"], "failed")
        self.assertEqual(result["source_status"]["openai"]["status"], "failed")
        self.assertEqual(result["source_status"]["anthropic"]["status"], "failed")
        self.assertEqual(result["source_status"]["youtube"]["fetched"], 0)
        self.repository.bulk_create_youtube_videos.assert_not_called()
        self.repository.bulk_create_openai_articles.assert_not_called()
        self.repository.bulk_create_anthropic_articles.assert_not_called()


if __name__ == "__main__":
    unittest.main()
