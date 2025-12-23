"""
Integration of payments with generation flow.
Ensures charges are only committed on success.
"""
import logging
from typing import Dict, Any, Optional
from uuid import uuid4

from app.payments.charges import ChargeManager, get_charge_manager
from app.kie.generator import KieGenerator

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
    commit_on_success: bool = True
) -> Dict[str, Any]:
    """
    Generate with payment safety guarantees:
    - Charge only on success
    - Auto-refund on fail/timeout
    
    Args:
        model_id: Model identifier
        user_inputs: User inputs
        user_id: User identifier
        amount: Charge amount
        progress_callback: Progress callback
        timeout: Generation timeout
        
    Returns:
        Result dict with generation and payment info
    """
    charge_manager = charge_manager or get_charge_manager()
    generator = KieGenerator()
    charge_task_id = task_id or f"charge_{user_id}_{model_id}_{uuid4().hex[:8]}"
    
    # Create pending charge
    charge_result = await charge_manager.create_pending_charge(
        task_id=charge_task_id,
        user_id=user_id,
        amount=amount,
        model_id=model_id,
        reserve_balance=reserve_balance
    )
    
    if charge_result['status'] == 'already_committed':
        # Already paid, just generate
        gen_result = await generator.generate(model_id, user_inputs, progress_callback, timeout)
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
    
    # Generate
    gen_result = await generator.generate(model_id, user_inputs, progress_callback, timeout)
    
    # Determine task_id from generation (if available)
    # Commit or release charge based on generation result
    if gen_result.get('success'):
        if not commit_on_success:
            return {
                **gen_result,
                'charge_task_id': charge_task_id,
                'payment_status': 'pending',
                'payment_message': 'Ожидание подтверждения'
            }
        # SUCCESS: Commit charge
        commit_result = await charge_manager.commit_charge(charge_task_id)
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': commit_result['status'],
            'payment_message': commit_result['message']
        }
    else:
        # FAIL/TIMEOUT: Release charge (auto-refund)
        release_result = await charge_manager.release_charge(
            charge_task_id,
            reason=gen_result.get('error_code', 'generation_failed')
        )
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': release_result['status'],
            'payment_message': release_result['message']
        }
