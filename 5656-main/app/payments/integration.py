"""
Integration of payments with generation flow.
Ensures charges are only committed on success.
Handles FREE tier models (no charge).
Includes user rate limiting to prevent spam/abuse.
"""
import logging
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from app.payments.charges import ChargeManager, get_charge_manager
from app.kie.generator import KieGenerator
from app.utils.metrics import track_generation
from app.pricing.free_models import is_free_model
from app.utils.correlation import ensure_correlation_id, correlation_tag
from app.utils.user_rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


async def generate_with_payment(
    model_id: str,
    user_inputs: Dict[str, Any],
    user_id: int,
    amount: float,
    progress_callback: Optional[Any] = None,
    timeout: int = 300,
    task_id: Optional[str] = None,
    reserve_balance: bool = False,
    charge_manager: Optional[ChargeManager] = None,
    chat_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate with payment safety guarantees:
    - FREE models: no charge
    - Paid models: charge only on success, auto-refund on fail/timeout
    
    Args:
        model_id: Model identifier
        user_inputs: User inputs
        user_id: User identifier
        amount: Charge amount (ignored for FREE models)
        progress_callback: Progress callback
        timeout: Generation timeout
        chat_id: Telegram chat ID for result delivery
        
    Returns:
        Result dict with generation and payment info
    """
    ensure_correlation_id(task_id or f"{user_id}:{model_id}")
    
    # CRITICAL LOGGING: Log inputs at entry with correlation
    logger.info(f"{correlation_tag()} [PAYMENT] generate_with_payment called:")
    logger.info(f"{correlation_tag()} [PAYMENT]   - user_id: {user_id}")
    logger.info(f"{correlation_tag()} [PAYMENT]   - model_id: {model_id}")
    logger.info(f"{correlation_tag()} [PAYMENT]   - user_inputs keys: {list(user_inputs.keys())}")
    logger.info(f"{correlation_tag()} [PAYMENT]   - amount: {amount}")
    
    # BATCH 40: Check if user is admin (unlimited generations, no payment)
    from app.admin.permissions import is_admin
    user_is_admin = is_admin(user_id)
    
    if user_is_admin:
        logger.info(
            f"{correlation_tag()} [ADMIN] 🔓 User {user_id} is ADMIN - unlimited generations, no payment"
        )
        # Admin bypass: no rate limit, no payment, just generate
        generator = KieGenerator()
        gen_result = await generator.generate(
            model_id, user_inputs, progress_callback, timeout,
            user_id=user_id, chat_id=chat_id or user_id, price=0.0
        )
        return {
            **gen_result,
            'charge_task_id': None,
            'payment_status': 'admin_unlimited',
            'payment_message': '🔓 Админ: безлимит, без оплаты'
        }
    
    # ✅ ITERATION 8: Check user rate limit BEFORE any payment/generation
    is_free = is_free_model(model_id)
    rate_limiter = get_rate_limiter()
    rate_check = rate_limiter.check_rate_limit(user_id, is_paid=not is_free)
    
    if not rate_check["allowed"]:
        logger.warning(
            f"{correlation_tag()} [RATE_LIMIT] ⏱ User {user_id} limited: {rate_check['reason']} "
            f"(wait {rate_check['wait_seconds']}s)"
        )
        return {
            'success': False,
            'message': f"⏱ Превышен лимит генераций. Подождите {rate_check['wait_seconds']}с\n"
                       f"Причина: {rate_check['reason']}",
            'error_code': 'RATE_LIMIT_EXCEEDED',
            'rate_limit_info': rate_check
        }
    
    # Check DRY_RUN mode
    dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
    if dry_run:
        logger.info(f"{correlation_tag()} [DRY_RUN] EXTERNAL_CALL_BLOCKED reason=DRY_RUN model={model_id}")
        # Return mock result without real generation
        mock_task_id = f"mock_job_{uuid4().hex[:8]}"
        return {
            'success': True,
            'message': f'✅ Запрос принят (DRY_RUN), job_id={mock_task_id}, статус=mock_done',
            'result_urls': [f'mock://result/{mock_task_id}.jpg'],
            'result_object': {'url': f'mock://result/{mock_task_id}.jpg'},
            'task_id': mock_task_id,
            'charge_task_id': None,
            'payment_status': 'dry_run_mock'
        }
    
    # Check if model is FREE (TOP-5 cheapest)
    if is_free:
        logger.info(f"{correlation_tag()} 🆓 Model {model_id} is FREE - skipping payment")
        generator = KieGenerator()
        gen_result = await generator.generate(
            model_id, user_inputs, progress_callback, timeout,
            user_id=user_id, chat_id=chat_id or user_id, price=0.0
        )
        
        # CRITICAL: If KIE returns 402 for "free" model, it's a config mismatch
        if not gen_result.get('success') and gen_result.get('error_code') == 'INSUFFICIENT_CREDITS':
            logger.error(
                f"⚠️ Model {model_id} marked FREE but KIE returned 402! "
                f"This is a SOURCE_OF_TRUTH mismatch. Model requires credits."
            )
            # Return honest error to user
            return {
                **gen_result,
                'charge_task_id': None,
                'payment_status': 'free_tier_mismatch',
                'message': (
                    f"❌ Модель {model_id} помечена как бесплатная, но требует кредиты KIE.ai. "
                    f"Пожалуйста, пополните баланс KIE.ai или выберите другую модель."
                ),
            }
        
        # BATCH 41: Add upsell flag for free models (lead magnet → conversion)
        return {
            **gen_result,
            'charge_task_id': None,
            'payment_status': 'free_tier',
            'payment_message': '🆓 FREE модель - генерация бесплатна',
            'show_upsell': True  # Trigger upsell message in UI
        }
    
    # Paid model - proceed with charging
    charge_manager = charge_manager or get_charge_manager()
    generator = KieGenerator()
    charge_task_id = task_id or f"charge_{user_id}_{model_id}_{uuid4().hex[:8]}"
    ensure_correlation_id(charge_task_id)
    
    # Create pending charge
    logger.info(f"{correlation_tag()} Creating pending charge for {charge_task_id}")
    charge_result = await charge_manager.create_pending_charge(
        task_id=charge_task_id,
        user_id=user_id,
        amount=amount,
        model_id=model_id,
        reserve_balance=reserve_balance
    )
    
    if charge_result['status'] == 'already_committed':
        # Already paid, just generate
        gen_result = await generator.generate(
            model_id, user_inputs, progress_callback, timeout,
            user_id=user_id, chat_id=chat_id or user_id, price=amount
        )
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': 'already_committed',
            'payment_message': 'Оплата уже подтверждена'
        }
    if charge_result['status'] == 'insufficient_balance':
        return {
            'success': False,
            'message': '❌ Недостаточно средств. Пополните баланс и попробуйте снова.',
            'result_urls': [],
            'result_object': None,
            'error_code': 'INSUFFICIENT_BALANCE',
            'error_message': 'Insufficient balance',
            'task_id': None,
            'charge_task_id': charge_task_id,
            'payment_status': charge_result['status'],
            'payment_message': charge_result['message']
        }
    
    # BATCH 40: Generate first, charge ONLY on success
    # Strategy: Hold (reserve) → Generate → Charge (commit) OR Release (refund)
    start_time = time.time()
    logger.info(f"{correlation_tag()} Starting generation for model={model_id}")
    gen_result = await generator.generate(
        model_id, user_inputs, progress_callback, timeout,
        user_id=user_id, chat_id=chat_id or user_id, price=amount
    )
    duration = time.time() - start_time
    
    # Track metrics
    success = gen_result.get('success', False)
    await track_generation(
        model_id=model_id,
        success=success,
        duration=duration,
        price_rub=amount if success else 0.0
    )
    
    # CRITICAL: DO NOT charge balance here - wait for successful delivery
    # Balance will be charged in mark_delivered() after result is successfully sent to user
    # This ensures user only pays when they actually receive the result
    if gen_result.get('success'):
        # SUCCESS: Keep charge in pending state, will be committed after delivery
        # DO NOT commit charge here - wait for delivery confirmation
        logger.info(f"{correlation_tag()} Generation succeeded for {charge_task_id}, charge will be committed after delivery")
        # Note: commit_charge will be called in mark_delivered() after successful delivery
        
        # ✅ ITERATION 8: Record successful generation for rate limiting
        rate_limiter.record_generation(user_id, is_paid=not is_free)
        logger.info(
            f"{correlation_tag()} [RATE_LIMIT] ✅ Generation recorded: user={user_id}, "
            f"paid={not is_free}, stats={rate_limiter.get_user_stats(user_id)}"
        )
        
        # Add to history
        result_urls = gen_result.get('result_urls', [])
        result_text = '\n'.join(result_urls) if result_urls else 'Success'
        charge_manager.add_to_history(user_id, model_id, user_inputs, result_text, True)
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': 'pending_delivery',  # Changed: charge will be committed after delivery
            'payment_message': 'Оплата будет списана после успешной доставки результата'
        }
    else:
        # FAIL/TIMEOUT: Release charge (auto-refund)
        logger.info(f"{correlation_tag()} Releasing charge for {charge_task_id}")
        release_result = await charge_manager.release_charge(
            charge_task_id,
            reason=gen_result.get('error_code', 'generation_failed')
        )
        # Add to history
        error_msg = gen_result.get('message', 'Failed')
        charge_manager.add_to_history(user_id, model_id, user_inputs, error_msg, False)
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': release_result['status'],
            'payment_message': release_result['message']
        }
