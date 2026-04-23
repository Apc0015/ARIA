"""Retry utilities with exponential backoff for HTTP collectors."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable, Optional, Type

logger = logging.getLogger("aria")


async def with_retry(
    coro_fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
    **kwargs: Any,
) -> Any:
    """
    Retry an async callable with exponential backoff + jitter.

    Retries on:
      - HTTP 429 (rate limit) — up to max_delay with Retry-After header respect
      - HTTP 5xx (server errors)
      - Network / timeout exceptions

    Args:
        coro_fn: Async callable to retry.
        *args: Positional args forwarded to coro_fn.
        max_attempts: Total attempts (including first).
        base_delay: Initial delay in seconds (doubles each retry).
        max_delay: Cap on retry delay.
        retryable_exceptions: Exception types to retry on.
        retryable_status_codes: HTTP status codes to treat as retryable.
        **kwargs: Keyword args forwarded to coro_fn.

    Returns:
        Result of successful call.

    Raises:
        Last exception if all attempts exhausted.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt == max_attempts:
                break

            # Check for Retry-After in response if it's an httpx response error
            retry_after: Optional[float] = None
            try:
                response = getattr(exc, "response", None)
                if response is not None:
                    status = getattr(response, "status_code", 0)
                    if status not in retryable_status_codes:
                        raise  # non-retryable HTTP error
                    retry_after_header = response.headers.get("Retry-After", "")
                    if retry_after_header:
                        retry_after = min(float(retry_after_header), max_delay)
            except (AttributeError, ValueError):
                pass

            delay = retry_after or min(base_delay * (2 ** (attempt - 1)), max_delay)
            # Add jitter (±20%)
            delay = delay * (0.8 + random.random() * 0.4)

            logger.debug(
                "Retry %d/%d after %.1fs (reason: %s)",
                attempt, max_attempts - 1, delay, type(exc).__name__,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]


def retryable(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
):
    """
    Decorator: wrap an async method with retry logic.

    Usage:
        @retryable(max_attempts=3, base_delay=1.0)
        async def _fetch(self, url: str) -> dict:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await with_retry(
                fn, *args,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                **kwargs,
            )
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator
