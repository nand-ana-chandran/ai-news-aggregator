"""Regression tests for daily-pipeline stage and email failure reporting."""

import sys
import types
import unittest
from unittest.mock import Mock, patch


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


_STUBS = {
    "dotenv": _module("dotenv", load_dotenv=lambda: None),
    "app.runner": _module("app.runner", run_scrapers=None),
    "app.services.process_anthropic": _module(
        "app.services.process_anthropic", process_anthropic_markdown=None
    ),
    "app.services.process_youtube": _module(
        "app.services.process_youtube", process_youtube_transcripts=None
    ),
    "app.services.process_digest": _module(
        "app.services.process_digest", process_digests=None
    ),
    "app.services.process_email": _module(
        "app.services.process_email", send_digest_email=None
    ),
}

with patch.dict(sys.modules, _STUBS):
    from app import daily_runner


class DailyPipelineFailureReportingTests(unittest.TestCase):
    def setUp(self):
        self.scrape = Mock(return_value={
            "youtube": [],
            "openai": [],
            "anthropic": [],
            "source_status": {},
        })
        self.anthropic = Mock(return_value={"total": 0, "processed": 0, "failed": 0})
        self.youtube = Mock(return_value={
            "total": 0, "processed": 0, "unavailable": 0, "failed": 0
        })
        self.digests = Mock(return_value={"total": 0, "processed": 0, "failed": 0})
        self.email = Mock(return_value={"success": True, "status": "sent"})

        daily_runner.run_scrapers = self.scrape
        daily_runner.process_anthropic_markdown = self.anthropic
        daily_runner.process_youtube_transcripts = self.youtube
        daily_runner.process_digests = self.digests
        daily_runner.send_digest_email = self.email

    def test_thrown_processing_exception_remains_failed_not_partial_failure(self):
        self.anthropic.side_effect = RuntimeError("markdown service crashed")

        result = daily_runner.run_daily_pipeline()

        self.assertEqual(result["stage_status"]["anthropic_markdown"]["status"], "failed")
        stage_errors = [
            error for error in result["errors"]
            if error["stage"] == "anthropic_markdown"
        ]
        self.assertEqual(len(stage_errors), 1)
        self.assertEqual(stage_errors[0]["error_type"], "RuntimeError")
        self.assertEqual(result["status"], "partial_success")
        self.assertTrue(self.email.called)

    def test_email_exception_is_recorded_only_once(self):
        self.email.side_effect = RuntimeError("SMTP connection dropped")

        result = daily_runner.run_daily_pipeline()

        self.assertEqual(result["stage_status"]["email"]["status"], "failed")
        email_errors = [error for error in result["errors"] if error["stage"] == "email"]
        self.assertEqual(len(email_errors), 1)
        self.assertEqual(email_errors[0]["error_type"], "RuntimeError")
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["success"])

    def test_returned_email_failure_is_still_reported(self):
        self.email.return_value = {
            "success": False,
            "status": "failed",
            "error_type": "SMTPError",
            "error": "authentication rejected",
        }

        result = daily_runner.run_daily_pipeline()

        email_errors = [error for error in result["errors"] if error["stage"] == "email"]
        self.assertEqual(len(email_errors), 1)
        self.assertEqual(email_errors[0]["error_type"], "SMTPError")
        self.assertEqual(result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
