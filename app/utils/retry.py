"""Small, dependency-free retry helpers for transient external-service failures."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
_RETRYABLE_ERROR_NAMES = (
    "timeout",
    "timedout",
    "connectionerror",
    "connectionreset",
    "temporarilyunavailable",
    "serviceunavailable",
    "internalservererror",
    "resourceexhausted",
    "ratelimit",
    "toomanyrequests",
    "servererror",
)


def is_retryable_error(error: BaseException) -> bool:
    """Return True only when an error looks transient; unknown errors fail fast."""
    status_code = (
        getattr(error, "status_code", None)
        or getattr(error, "status", None)
        or getattr(getattr(error, "response", None), "status_code", None)
    )
    try:
        status_code = int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        status_code = None

    if status_code is not None:
        return status_code in _RETRYABLE_STATUS_CODES

    name = type(error).__name__.replace("_", "").lower()
    module = type(error).__module__.lower()
    if any(token in name for token in _RETRYABLE_ERROR_NAMES):
        return True

    # These standard/network client exceptions are transient in external calls.
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    if any(client in module for client in ("requests", "urllib3", "httpx", "httpcore")):
        return any(token in name for token in ("timeout", "connection", "network", "protocol"))
    return False


def retry_call(
    operation: str,
    func: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    jitter: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> T:
    """Call func with bounded exponential backoff and jitter.

    max_attempts includes the initial call. Permanent/unknown errors are never retried.
    Each operation logs its final status and attempt count.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay < 0 or max_delay < 0 or jitter < 0:
        raise ValueError("delay and jitter values must be non-negative")

    for attempt in range(1, max_attempts + 1):
        try:
            result = func()
        except Exception as error:
            retryable = is_retryable_error(error)
            if not retryable:
                logger.error(
                    "operation=%s status=permanent_failure attempts=%d error_type=%s",
                    operation, attempt, type(error).__name__,
                )
                raise
            if attempt >= max_attempts:
                logger.error(
                    "operation=%s status=retries_exhausted attempts=%d error_type=%s",
                    operation, attempt, type(error).__name__,
                )
                raise

            exponential_delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay = exponential_delay * (1 + jitter * ((2 * random_value()) - 1))
            delay = max(0.0, min(delay, max_delay))
            logger.warning(
                "operation=%s status=retrying attempt=%d/%d error_type=%s retry_in_seconds=%.2f",
                operation, attempt, max_attempts, type(error).__name__, delay,
            )
            sleep(delay)
        else:
            logger.info(
                "operation=%s status=success attempts=%d",
                operation, attempt,
            )
            return result

    raise RuntimeError("Unreachable retry state")
