import unittest
from unittest.mock import Mock

from app.utils.retry import is_retryable_error, retry_call


class RetryHelperTests(unittest.TestCase):
    def test_retries_transient_error_then_succeeds(self):
        operation = Mock(side_effect=[TimeoutError("temporary"), "ok"])
        delays = []

        result = retry_call(
            "test.operation", operation, max_attempts=3,
            base_delay=0.5, jitter=0, sleep=delays.append,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(operation.call_count, 2)
        self.assertEqual(delays, [0.5])

    def test_exponential_backoff_is_bounded_by_attempts(self):
        operation = Mock(side_effect=TimeoutError("still down"))
        delays = []

        with self.assertRaises(TimeoutError):
            retry_call(
                "test.operation", operation, max_attempts=3,
                base_delay=1, max_delay=5, jitter=0, sleep=delays.append,
            )

        self.assertEqual(operation.call_count, 3)
        self.assertEqual(delays, [1, 2])

    def test_permanent_error_fails_without_retry(self):
        operation = Mock(side_effect=ValueError("invalid input"))

        with self.assertRaises(ValueError):
            retry_call("test.operation", operation, sleep=Mock())

        self.assertEqual(operation.call_count, 1)

    def test_http_status_classification(self):
        class RateLimited(Exception):
            status_code = 429

        class Unauthorized(Exception):
            status_code = 401

        self.assertTrue(is_retryable_error(RateLimited()))
        self.assertFalse(is_retryable_error(Unauthorized()))

    def test_unknown_errors_fail_fast(self):
        self.assertFalse(is_retryable_error(ValueError("bad input")))


if __name__ == "__main__":
    unittest.main()
