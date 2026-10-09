"""Regression tests for retry-attempt counts and terminal status logging."""

import unittest
from unittest.mock import Mock

from app.utils.retry import retry_call


class RetryStatusReportingTests(unittest.TestCase):
    def test_success_after_retry_records_attempt_count_and_success_status(self):
        operation = Mock(side_effect=[TimeoutError("temporary outage"), "recovered"])

        with self.assertLogs("app.utils.retry", level="INFO") as captured:
            result = retry_call(
                "test.source",
                operation,
                max_attempts=3,
                base_delay=0,
                jitter=0,
                sleep=Mock(),
            )

        self.assertEqual(result, "recovered")
        self.assertEqual(operation.call_count, 2)
        self.assertTrue(any(
            "status=retrying attempt=1/3" in message
            for message in captured.output
        ))
        self.assertTrue(any(
            "status=success attempts=2" in message
            for message in captured.output
        ))

    def test_exhausted_transient_failure_records_final_attempt_count(self):
        operation = Mock(side_effect=TimeoutError("service remains unavailable"))

        with self.assertLogs("app.utils.retry", level="ERROR") as captured:
            with self.assertRaises(TimeoutError):
                retry_call(
                    "test.source",
                    operation,
                    max_attempts=3,
                    base_delay=0,
                    jitter=0,
                    sleep=Mock(),
                )

        self.assertEqual(operation.call_count, 3)
        self.assertTrue(any(
            "status=retries_exhausted attempts=3" in message
            for message in captured.output
        ))

    def test_permanent_failure_records_one_attempt_and_terminal_status(self):
        operation = Mock(side_effect=ValueError("invalid configuration"))

        with self.assertLogs("app.utils.retry", level="ERROR") as captured:
            with self.assertRaises(ValueError):
                retry_call("test.source", operation, sleep=Mock())

        self.assertEqual(operation.call_count, 1)
        self.assertTrue(any(
            "status=permanent_failure attempts=1" in message
            for message in captured.output
        ))

    def test_single_allowed_attempt_never_retries_transient_failure(self):
        operation = Mock(side_effect=TimeoutError("temporary outage"))
        sleep = Mock()

        with self.assertLogs("app.utils.retry", level="ERROR") as captured:
            with self.assertRaises(TimeoutError):
                retry_call(
                    "test.source",
                    operation,
                    max_attempts=1,
                    base_delay=0,
                    jitter=0,
                    sleep=sleep,
                )

        self.assertEqual(operation.call_count, 1)
        sleep.assert_not_called()
        self.assertTrue(any(
            "status=retries_exhausted attempts=1" in message
            for message in captured.output
        ))


if __name__ == "__main__":
    unittest.main()
