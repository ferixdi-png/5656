"""
Enhanced KIE API error handling with robust retry logic.

Features:
- Exponential backoff with jitter
- Timeout protection
- Rate limit handling (429)
- Graceful degradation
- Error classification and logging
"""

import asyncio
import logging
import random
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Rate limit exceeded (429)."""
    pass


class TimeoutError(Exception):
    """Request timeout."""
    pass


class APIError(Exception):
    """API returned 5xx error."""
    pass


class ClientError(Exception):
    """Invalid request (4xx, not including 429)."""
    pass


def classify_error(exc: Exception) -> str:
    """Classify exception type for logging."""
    if isinstance(exc, RateLimitError):
        return "RATE_LIMIT"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, APIError):
        return "API_ERROR"
    if isinstance(exc, ClientError):
        return "CLIENT_ERROR"
    if isinstance(exc, requests.ConnectionError):
        return "CONNECTION_ERROR"
    return "UNKNOWN"


async def retry_with_exponential_backoff(
    func: Callable,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    timeout_per_attempt: float = 10.0,
    **kwargs
) -> Any:
    """
    Execute function with exponential backoff retry.

    Retries on:
    - ConnectionError (network issues)
    - RateLimitError (429 - wait and retry)
    - TimeoutError (slow response)

    Does NOT retry on:
    - ClientError (invalid request)
    - APIError (server error) - may retry once

    Args:
        func: Async function to execute
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        timeout_per_attempt: Timeout for each attempt

    Returns:
        Function result or None if all attempts failed

    Raises:
        ClientError if request is invalid
    """
    attempt = 0
    last_error = None

    while attempt < max_attempts:
        attempt += 1
        try:
            # Run function with timeout
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_per_attempt
                )
                if attempt > 1:
                    logger.info(f"[RETRY] Succeeded on attempt {attempt}")
                return result
            except asyncio.TimeoutError:
                raise TimeoutError(f"Request timeout after {timeout_per_attempt}s")

        except ClientError as e:
            # Don't retry client errors
            logger.error(f"[RETRY] Client error: {e}")
            raise

        except RateLimitError as e:
            # Retry rate limits with longer delay
            if attempt < max_attempts:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                # Add jitter (±10%)
                delay += delay * random.uniform(-0.1, 0.1)
                logger.warning(
                    f"[RETRY] Rate limited, attempt {attempt}/{max_attempts}, "
                    f"retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"[RETRY] Max attempts reached for rate limit")
                raise
            last_error = e

        except TimeoutError as e:
            # Retry timeouts
            if attempt < max_attempts:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                delay += delay * random.uniform(-0.1, 0.1)
                logger.warning(
                    f"[RETRY] Timeout, attempt {attempt}/{max_attempts}, "
                    f"retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"[RETRY] Max timeout attempts reached")
                raise
            last_error = e

        except APIError as e:
            # Might retry server errors once
            if attempt < 2:  # Retry server errors only once
                logger.warning(
                    f"[RETRY] API error, attempt {attempt}/{max_attempts}, "
                    f"retrying: {e}"
                )
                await asyncio.sleep(min(base_delay, max_delay))
            else:
                logger.error(f"[RETRY] Max API error attempts reached")
                raise
            last_error = e

        except (requests.ConnectionError, requests.RequestException) as e:
            # Network errors - retry
            if attempt < max_attempts:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                delay += delay * random.uniform(-0.1, 0.1)
                logger.warning(
                    f"[RETRY] Connection error, attempt {attempt}/{max_attempts}, "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"[RETRY] Max connection attempts reached")
                raise
            last_error = e

    # All attempts failed
    if last_error:
        logger.error(
            f"[RETRY] All {max_attempts} attempts failed. "
            f"Last error: {classify_error(last_error)}: {last_error}"
        )
        raise last_error
    
    raise RuntimeError("All retry attempts failed without capturing error")


def handle_api_response(response: requests.Response) -> dict:
    """
    Parse API response and raise appropriate errors.

    Args:
        response: requests.Response object

    Returns:
        Parsed JSON response

    Raises:
        ClientError: 4xx (except 429)
        RateLimitError: 429
        APIError: 5xx
    """
    status = response.status_code

    if 200 <= status < 300:
        return response.json()

    # 4xx errors
    if 400 <= status < 500:
        if status == 429:
            # Rate limit - extract retry-after if available
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimitError(
                f"Rate limited (429). Retry after {retry_after}s"
            )
        # Other 4xx errors
        try:
            error_data = response.json()
            error_msg = error_data.get("error", response.text)
        except:
            error_msg = response.text
        raise ClientError(f"Client error {status}: {error_msg}")

    # 5xx errors
    if 500 <= status < 600:
        try:
            error_data = response.json()
            error_msg = error_data.get("error", response.text)
        except:
            error_msg = response.text
        raise APIError(f"API error {status}: {error_msg}")

    raise APIError(f"Unexpected response {status}: {response.text}")


async def call_kie_api_with_retry(
    url: str,
    headers: dict,
    payload: dict,
    model_id: str = "unknown",
    max_attempts: int = 3,
) -> Optional[dict]:
    """
    Call Kie API with full error handling and retry logic.

    Args:
        url: API endpoint
        headers: HTTP headers
        payload: Request payload
        model_id: Model name for logging
        max_attempts: Number of retry attempts

    Returns:
        API response or None if all retries failed
    """
    async def _call():
        try:
            response = await asyncio.to_thread(
                requests.post,
                url,
                headers=headers,
                json=payload,
                timeout=10  # Per-request timeout
            )
            return handle_api_response(response)
        except requests.Timeout as e:
            raise TimeoutError(f"Request timeout: {e}")
        except requests.ConnectionError as e:
            raise requests.ConnectionError(f"Connection failed: {e}")
        except requests.RequestException as e:
            raise ClientError(f"Request error: {e}")

    try:
        return await retry_with_exponential_backoff(
            _call,
            max_attempts=max_attempts,
            base_delay=1.0,
            max_delay=30.0,
            timeout_per_attempt=10.0
        )
    except ClientError as e:
        logger.error(f"[KIE] {model_id} - Client error: {e}")
        return None
    except RateLimitError as e:
        logger.warning(f"[KIE] {model_id} - Rate limited: {e}")
        return None
    except TimeoutError as e:
        logger.error(f"[KIE] {model_id} - Timeout: {e}")
        return None
    except APIError as e:
        logger.error(f"[KIE] {model_id} - API error: {e}")
        return None
    except Exception as e:
        logger.exception(f"[KIE] {model_id} - Unexpected error: {e}")
        return None
