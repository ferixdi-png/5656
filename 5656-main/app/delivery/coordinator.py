"""
Unified Delivery Coordinator
Platform-wide atomic delivery lock for ALL Kie.ai generation types.

Responsibilities:
1. Acquire atomic lock (try_acquire_delivery_lock)
2. Deliver media based on category (image/video/audio/upscale)
3. Mark delivered after successful send
4. Release lock on failure (allow retry)
5. Ensure exactly-once delivery under all race conditions:
   - callback + polling
   - Kie retry callbacks
   - deploy overlap (ACTIVE/PASSIVE)
   - transient Telegram failures
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile
from aiogram.exceptions import TelegramAPIError
import aiohttp

logger = logging.getLogger(__name__)

# State normalization: treat these as SUCCESS
SUCCESS_STATES = {"success", "done", "completed"}
FAILURE_STATES = {"failed", "error", "fail", "canceled"}


def normalize_state(raw_state: str) -> str:
    """
    Normalize Kie.ai state variations to canonical form.
    
    Args:
        raw_state: Raw state from Kie API (success/done/completed/failed/etc.)
        
    Returns:
        'success', 'failed', 'running', or raw_state if unknown
    """
    lower = raw_state.lower()
    
    if lower in SUCCESS_STATES:
        return "success"
    elif lower in FAILURE_STATES:
        return "failed"
    elif lower in {"running", "pending", "waiting", "queued"}:
        return "running"
    else:
        return raw_state  # Unknown state, preserve original


async def deliver_result_atomic(
    storage,
    bot: Bot,
    task_id: str,
    chat_id: int,
    result_urls: List[str],
    category: str,
    corr_id: str = "",
    timeout_minutes: int = 5,
    job_service=None  # Optional JobServiceV2 for balance charge after delivery
) -> Dict[str, Any]:
    """
    Atomic delivery coordinator with exactly-once guarantee.
    
    This is the SINGLE delivery pipeline for ALL Kie.ai generation types.
    
    Args:
        storage: Storage instance with try_acquire_delivery_lock/mark_delivered
        bot: Aiogram Bot instance
        task_id: Kie.ai external_task_id
        chat_id: Telegram chat_id to send result to
        result_urls: List of result URLs from Kie.ai
        category: 'image', 'video', 'audio', 'upscale', etc.
        corr_id: Correlation ID for logging
        timeout_minutes: Stale lock timeout
        
    Returns:
        {
            'delivered': bool,          # True if this call delivered
            'already_delivered': bool,  # True if someone else already delivered
            'lock_acquired': bool,      # True if lock was won
            'error': Optional[str]      # Error message if delivery failed
        }
    """
    # CRITICAL: Validate inputs
    if not task_id or not isinstance(task_id, str):
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = f"Invalid task_id: {task_id} (must be non-empty string)"
        logger.error(f"{cid} [DELIVER_ERROR] {error_msg}")
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': False,
            'error': error_msg
        }
    
    if not isinstance(chat_id, int) or chat_id <= 0:
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = f"Invalid chat_id: {chat_id} (must be positive integer)"
        logger.error(f"{cid} [DELIVER_ERROR] {error_msg}")
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': False,
            'error': error_msg
        }
    
    if not category or not isinstance(category, str):
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = f"Invalid category: {category} (must be non-empty string)"
        logger.error(f"{cid} [DELIVER_ERROR] {error_msg} task_id={task_id}")
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': False,
            'error': error_msg
        }
    
    tag = f"[{corr_id}]" if corr_id else ""
    
    # STEP 1: Try to acquire atomic lock
    logger.info(f"{tag} [DELIVER_COORDINATOR] Attempting lock for task_id={task_id}")
    lock_job = await storage.try_acquire_delivery_lock(task_id, timeout_minutes=timeout_minutes)
    
    if not lock_job:
        # Someone else already delivered or is delivering
        logger.info(f"{tag} [DELIVER_LOCK_SKIP] Already delivered or delivering task_id={task_id}")
        return {
            'delivered': False,
            'already_delivered': True,
            'lock_acquired': False,
            'error': None
        }
    
    # STEP 2: Lock acquired - we are responsible for delivery
    logger.info(f"{tag} [DELIVER_LOCK_WIN] Won delivery race task_id={task_id} category={category}")
    
    if not result_urls:
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = "No result URLs to deliver"
        logger.error(f"{cid} {tag} [DELIVER_ERROR] {error_msg} task_id={task_id}")
        await storage.mark_delivered(task_id, success=False, error=error_msg)
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': True,
            'error': error_msg
        }
    
    # STEP 3: Deliver media based on category (with retry for Telegram API failures)
    # CRITICAL: Validate result_urls is not empty (defense-in-depth)
    if not result_urls or len(result_urls) == 0:
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = "No result URLs to deliver (empty list)"
        logger.error(f"{cid} {tag} [DELIVER_ERROR] {error_msg} task_id={task_id}")
        await storage.mark_delivered(task_id, success=False, error=error_msg)
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': True,
            'error': error_msg
        }
    
    # CRITICAL: Validate URL format
    url = result_urls[0]  # Primary result
    if not isinstance(url, str) or not url.strip():
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = f"Invalid URL format: {url}"
        logger.error(f"{cid} {tag} [DELIVER_ERROR] {error_msg} task_id={task_id}")
        await storage.mark_delivered(task_id, success=False, error=error_msg)
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': True,
            'error': error_msg
        }
    
    # Validate URL is a valid HTTP/HTTPS URL
    if not url.startswith(('http://', 'https://')):
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        error_msg = f"Invalid URL scheme (must be http:// or https://): {url[:100]}"
        logger.error(f"{cid} {tag} [DELIVER_ERROR] {error_msg} task_id={task_id}")
        await storage.mark_delivered(task_id, success=False, error=error_msg)
        return {
            'delivered': False,
            'already_delivered': False,
            'lock_acquired': True,
            'error': error_msg
        }
    
    logger.info(f"{tag} [DELIVER_START] task_id={task_id} category={category} url={url[:80]}")
    
    import asyncio
    from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
    
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if category in {"image", "text2image", "image2image", "upscale", "enhance"}:
                await _deliver_image(bot, chat_id, url, category, tag)
            elif category in {"video", "text2video", "image2video"}:
                await _deliver_video(bot, chat_id, url, tag)
            elif category in {"audio", "music", "text2audio", "text2music"}:
                await _deliver_audio(bot, chat_id, url, tag)
            else:
                # Unknown category - fallback to document
                logger.warning(f"{tag} [DELIVER_UNKNOWN_CATEGORY] category={category}, using document fallback")
                await _deliver_document(bot, chat_id, url, tag)
            
            # STEP 4: Mark delivered AFTER successful send
            logger.info(f"{tag} [DELIVER_OK] task_id={task_id} category={category}")
            await storage.mark_delivered(task_id, success=True)
            logger.info(f"{tag} [MARK_DELIVERED] task_id={task_id}")
            
            # CRITICAL: Charge balance ONLY after successful delivery
            # If using JobServiceV2, call mark_delivered which charges balance
            if job_service:
                try:
                    # Get job_id from task_id (task_id is kie_task_id in jobs table)
                    # P0-2 FIX: Explicit error handling for get_by_task_id call
                    if not hasattr(job_service, 'get_by_task_id'):
                        logger.error(f"{tag} [BALANCE_CHARGE_ERROR] job_service.get_by_task_id method not found")
                    else:
                        job = await job_service.get_by_task_id(task_id)
                        if job:
                            # CRITICAL FIX: Safe access to job_id with validation
                            job_id = job.get('id')
                            if not job_id:
                                logger.error(f"{tag} [BALANCE_CHARGE_ERROR] Job found but missing 'id' field: {job}")
                            else:
                                await job_service.mark_delivered(job_id)
                                logger.info(f"{tag} [BALANCE_CHARGE_AFTER_DELIVERY] job_id={job_id} task_id={task_id}")
                        else:
                            logger.warning(f"{tag} [BALANCE_CHARGE_WARN] Job not found for task_id={task_id}, cannot charge balance. This may indicate orphan callback or job cleanup.")
                except AttributeError as e:
                    logger.error(f"{tag} [BALANCE_CHARGE_ERROR] job_service missing get_by_task_id method: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"{tag} [BALANCE_CHARGE_ERROR] Failed to charge balance after delivery: {e}", exc_info=True)
            
            return {
                'delivered': True,
                'already_delivered': False,
                'lock_acquired': True,
                'error': None
            }
            
        except TelegramRetryAfter as e:
            # КРИТИЧНО: Telegram rate limit - ВСЕГДА соблюдать retry_after
            last_error = e
            retry_after = e.retry_after if hasattr(e, 'retry_after') else (attempt + 1) * 2
            
            # Записать ошибку в систему защиты
            try:
                from app.security.telegram_protection import get_telegram_protection
                protection = get_telegram_protection()
                await protection.record_error(e)
            except Exception:
                pass  # Не критично, если не удалось записать
            
            if attempt < max_retries - 1:
                logger.warning(
                    f"{tag} [DELIVER_RETRY] task_id={task_id} attempt={attempt+1}/{max_retries} "
                    f"rate_limited, retrying after {retry_after}s"
                )
                # КРИТИЧНО: Соблюдать retry_after точно
                await asyncio.sleep(retry_after)
            else:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(f"{cid} {tag} [DELIVER_FAIL] task_id={task_id} rate limit after {max_retries} attempts")
                break
                
        except TelegramAPIError as e:
            # Other Telegram API errors - retry with exponential backoff
            last_error = e
            
            # Записать ошибку в систему защиты
            try:
                from app.security.telegram_protection import get_telegram_protection
                protection = get_telegram_protection()
                await protection.record_error(e)
                
                # Проверить circuit breaker
                stats = await protection.get_stats()
                if stats.get("circuit_open"):
                    circuit_retry_after = stats.get("circuit_open_until", 0) - asyncio.get_event_loop().time()
                    if circuit_retry_after > 0:
                        logger.error(
                            f"{tag} [DELIVER_FAIL] task_id={task_id} Circuit breaker OPEN. "
                            f"Retry after {circuit_retry_after:.1f}s"
                        )
                        break  # Не повторять, если circuit открыт
            except Exception:
                pass  # Не критично
            
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 2  # 2s, 4s, 6s
                logger.warning(
                    f"{tag} [DELIVER_RETRY] task_id={task_id} attempt={attempt+1}/{max_retries} "
                    f"Telegram API error: {e}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            else:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(f"{cid} {tag} [DELIVER_FAIL] task_id={task_id} Telegram API error after {max_retries} attempts: {e}")
                break
                
        except Exception as e:
            # Non-Telegram errors (network, etc.) - retry with exponential backoff
            last_error = e
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 2  # 2s, 4s, 6s
                logger.warning(
                    f"{tag} [DELIVER_RETRY] task_id={task_id} attempt={attempt+1}/{max_retries} "
                    f"error: {e}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            else:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.exception(f"{cid} {tag} [DELIVER_FAIL] task_id={task_id} failed after {max_retries} attempts")
                break
    
    # STEP 5: On failure - release lock to allow retry
    from app.utils.correlation import correlation_tag
    cid = correlation_tag()
    error_msg = f"{type(last_error).__name__}: {str(last_error)}" if last_error else "Unknown error"
    logger.error(f"{cid} {tag} [DELIVER_FAIL] task_id={task_id} {error_msg}")
    
    await storage.mark_delivered(task_id, success=False, error=error_msg)
    logger.info(f"{tag} [DELIVER_FAIL_RELEASED] Lock released for retry task_id={task_id}")
    
    return {
        'delivered': False,
        'already_delivered': False,
        'lock_acquired': True,
        'error': error_msg
    }


async def _deliver_image(bot: Bot, chat_id: int, url: str, category: str, tag: str):
    """Deliver image with 3-level fallback"""
    caption = "✅ Генерация завершена"
    if category in {"upscale", "enhance"}:
        caption = "✅ Улучшено"
    
    try:
        # Level 1: Direct URL (Telegram fetches)
        await bot.send_photo(chat_id, url, caption=caption)
        logger.info(f"{tag} [DELIVER_IMAGE_OK] method=direct_url")
    except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e1:
        # Specific exceptions for network/API errors
        logger.warning(f"{tag} [DELIVER_IMAGE_FALLBACK_BYTES] direct_url failed: {e1}")
        try:
            # Level 2: Download bytes
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    resp.raise_for_status()
                    image_bytes = await resp.read()
            
            input_file = BufferedInputFile(image_bytes, filename="result.jpg")
            await bot.send_photo(chat_id, photo=input_file, caption=caption)
            logger.info(f"{tag} [DELIVER_IMAGE_OK] method=bytes")
        except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError, OSError) as e2:
            # Specific exceptions for network/API/file errors
            logger.warning(f"{tag} [DELIVER_IMAGE_FALLBACK_DOCUMENT] bytes failed: {e2}")
            # Level 3: Send as document
            await bot.send_document(chat_id, url, caption=f"{caption}\n\nURL: {url}")
            logger.info(f"{tag} [DELIVER_IMAGE_OK] method=document")
        except Exception as e2:
            # Catch-all for unexpected errors
            logger.error(f"{tag} [DELIVER_IMAGE_ERROR] Unexpected error in bytes fallback: {e2}", exc_info=True)
            raise
    except Exception as e1:
        # Catch-all for unexpected errors in direct_url
        logger.error(f"{tag} [DELIVER_IMAGE_ERROR] Unexpected error in direct_url: {e1}", exc_info=True)
        raise


async def _deliver_video(bot: Bot, chat_id: int, url: str, tag: str):
    """Deliver video with fallback"""
    caption = "✅ Видео готово"
    
    try:
        await bot.send_video(chat_id, url, caption=caption)
        logger.info(f"{tag} [DELIVER_VIDEO_OK] method=direct_url")
    except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        # Specific exceptions for network/API errors
        logger.warning(f"{tag} [DELIVER_VIDEO_FALLBACK_DOCUMENT] {e}")
        await bot.send_document(chat_id, url, caption=f"{caption}\n\nURL: {url}")
        logger.info(f"{tag} [DELIVER_VIDEO_OK] method=document")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"{tag} [DELIVER_VIDEO_ERROR] Unexpected error: {e}", exc_info=True)
        raise


async def _deliver_audio(bot: Bot, chat_id: int, url: str, tag: str):
    """Deliver audio with fallback"""
    caption = "✅ Аудио готово"
    
    try:
        await bot.send_audio(chat_id, url, caption=caption)
        logger.info(f"{tag} [DELIVER_AUDIO_OK] method=direct_url")
    except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        # Specific exceptions for network/API errors
        logger.warning(f"{tag} [DELIVER_AUDIO_FALLBACK_DOCUMENT] {e}")
        await bot.send_document(chat_id, url, caption=f"{caption}\n\nURL: {url}")
        logger.info(f"{tag} [DELIVER_AUDIO_OK] method=document")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"{tag} [DELIVER_AUDIO_ERROR] Unexpected error: {e}", exc_info=True)
        raise


async def _deliver_document(bot: Bot, chat_id: int, url: str, tag: str):
    """Deliver as document (generic fallback)"""
    await bot.send_document(chat_id, url, caption="✅ Результат готов")
    logger.info(f"{tag} [DELIVER_DOCUMENT_OK]")
