"""Mocked tests for external integrations; no API keys or live network calls."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.agent.digest_agent import DigestAgent, DigestOutput
from app.agent.curator_agent import CuratorAgent, RankedArticle, RankedDigestList
from app.scrapers.youtube import YouTubeScraper
import app.services.email as email_service


def test_gemini_digest_uses_mocked_client(monkeypatch):
    expected = DigestOutput(title="Safer AI Systems", summary="A short test summary.")
    generate = Mock(return_value=SimpleNamespace(parsed=expected))
    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr("app.agent.digest_agent.genai.Client", Mock(return_value=fake_client))

    agent = DigestAgent()
    result = agent.generate_digest("Test", "Example content", "article")

    assert result == expected
    generate.assert_called_once()
    assert generate.call_args.kwargs["model"] == agent.model


def test_gemini_digest_returns_none_when_client_fails(monkeypatch):
    generate = Mock(side_effect=ValueError("invalid request"))
    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr("app.agent.digest_agent.genai.Client", Mock(return_value=fake_client))

    result = DigestAgent().generate_digest("Test", "Example content", "article")

    assert result is None
    generate.assert_called_once()


def test_curator_ranks_with_mocked_gemini(monkeypatch):
    expected = RankedDigestList(articles=[
        RankedArticle(
            digest_id="openai:1",
            relevance_score=8.5,
            rank=1,
            reasoning="Relevant to the profile.",
        )
    ])
    generate = Mock(return_value=SimpleNamespace(parsed=expected))
    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr("app.agent.curator_agent.genai.Client", Mock(return_value=fake_client))
    profile = {
        "name": "Test User",
        "background": "Software engineering",
        "expertise_level": "beginner",
        "interests": ["AI safety"],
        "preferences": {"format": "concise"},
    }
    digests = [{
        "id": "openai:1",
        "title": "AI safety",
        "summary": "An example summary.",
        "article_type": "openai",
    }]

    result = CuratorAgent(profile).rank_digests(digests)

    assert result == expected.articles
    generate.assert_called_once()


def test_youtube_transcript_uses_mocked_api(monkeypatch):
    snippets = [SimpleNamespace(text="Hello"), SimpleNamespace(text="world")]
    fake_transcript = SimpleNamespace(snippets=snippets)
    fake_api = SimpleNamespace(fetch=Mock(return_value=fake_transcript))
    monkeypatch.setattr("app.scrapers.youtube.YouTubeTranscriptApi", Mock(return_value=fake_api))

    scraper = YouTubeScraper()
    result = scraper.get_transcript("fake-video-id")

    assert result is not None
    assert result.text == "Hello world"
    fake_api.fetch.assert_called_once_with("fake-video-id")


def test_youtube_transient_failure_is_raised_for_later_retry(monkeypatch):
    fake_api = SimpleNamespace(fetch=Mock(side_effect=TimeoutError("temporary outage")))
    monkeypatch.setattr("app.scrapers.youtube.YouTubeTranscriptApi", Mock(return_value=fake_api))
    # Avoid waiting through real backoff; preserve retry behavior.
    monkeypatch.setattr("app.utils.retry.time.sleep", lambda _delay: None)

    scraper = YouTubeScraper()
    with pytest.raises(TimeoutError):
        scraper.get_transcript("fake-video-id")

    assert fake_api.fetch.call_count == 3


def test_smtp_send_uses_mocked_server(monkeypatch):
    smtp = Mock()
    smtp_context = Mock()
    smtp_context.__enter__ = Mock(return_value=smtp)
    smtp_context.__exit__ = Mock(return_value=False)
    smtp_factory = Mock(return_value=smtp_context)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", smtp_factory)
    monkeypatch.setattr(email_service, "MY_EMAIL", "sender@example.com")
    monkeypatch.setattr(email_service, "APP_PASSWORD", "fake-test-password")

    email_service.send_email(
        subject="Test digest",
        body_text="Plain-text test body",
        body_html="<p>HTML test body</p>",
        recipients=["reader@example.com"],
    )

    smtp_factory.assert_called_once_with("smtp.gmail.com", 465)
    smtp.login.assert_called_once_with("sender@example.com", "fake-test-password")
    smtp.sendmail.assert_called_once()
    assert smtp.sendmail.call_args.args[1] == ["reader@example.com"]


def test_smtp_missing_credentials_fails_without_network(monkeypatch):
    smtp_factory = Mock()
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", smtp_factory)
    monkeypatch.setattr(email_service, "MY_EMAIL", "sender@example.com")
    monkeypatch.setattr(email_service, "APP_PASSWORD", None)

    with pytest.raises(ValueError, match="APP_PASSWORD"):
        email_service.send_email("Subject", "Body")

    smtp_factory.assert_not_called()
