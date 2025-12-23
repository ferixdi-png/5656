"""
Payment charges with safety invariants:
- Charge only on generation success
- Auto-refund on fail/timeout/cancel
- Idempotent protection against double charges
"""
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ChargeManager:
    """Manages payment charges with idempotency and safety guarantees."""
    
    def __init__(self, storage=None):
        """
        Initialize charge manager.
        
        Args:
            storage: Storage backend for tracking charges
        """
        self.storage = storage
        self._pending_charges: Dict[str, Dict[str, Any]] = {}  # task_id -> charge_info
        self._committed_charges: Set[str] = set()  # task_id set for idempotency
        self._released_charges: Set[str] = set()  # task_id set for released charges
    
    async def create_pending_charge(
        self,
        task_id: str,
        user_id: int,
        amount: float,
        model_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create pending charge (reserve funds, don't charge yet).
        
        Args:
            task_id: Task identifier
            user_id: User identifier
            amount: Charge amount
            model_id: Model identifier
            metadata: Optional metadata
            
        Returns:
            Charge info dict
        """
        # Check if already committed (idempotency)
        if task_id in self._committed_charges:
            logger.warning(f"Charge for task {task_id} already committed, skipping")
            return {
                'status': 'already_committed',
                'task_id': task_id,
                'message': 'Оплата уже подтверждена'
            }
        
        # Check if already released
        if task_id in self._released_charges:
            logger.warning(f"Charge for task {task_id} already released, skipping")
            return {
                'status': 'already_released',
                'task_id': task_id,
                'message': 'Оплата уже отменена'
            }
        
        charge_info = {
            'task_id': task_id,
            'user_id': user_id,
            'amount': amount,
            'model_id': model_id,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self._pending_charges[task_id] = charge_info
        
        # Store in persistent storage if available
        if self.storage:
            try:
                await self.storage.save_pending_charge(charge_info)
            except Exception as e:
                logger.error(f"Failed to save pending charge: {e}")
        
        logger.info(f"Created pending charge for task {task_id}, amount: {amount}")
        return {
            'status': 'pending',
            'task_id': task_id,
            'amount': amount,
            'message': 'Ожидание оплаты'
        }
    
    async def commit_charge(self, task_id: str) -> Dict[str, Any]:
        """
        Commit charge (actually charge user) - ONLY on generation success.
        Idempotent: repeated calls are no-op.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Commit result dict
        """
        # Idempotency check
        if task_id in self._committed_charges:
            logger.info(f"Charge for task {task_id} already committed (idempotent)")
            return {
                'status': 'already_committed',
                'task_id': task_id,
                'message': 'Оплата уже подтверждена',
                'idempotent': True
            }
        
        # Check if charge exists
        if task_id not in self._pending_charges:
            logger.warning(f"No pending charge found for task {task_id}")
            return {
                'status': 'not_found',
                'task_id': task_id,
                'message': 'Оплата не найдена'
            }
        
        charge_info = self._pending_charges[task_id]
        
        # Check if already released
        if task_id in self._released_charges:
            logger.warning(f"Charge for task {task_id} was released, cannot commit")
            return {
                'status': 'already_released',
                'task_id': task_id,
                'message': 'Оплата была отменена'
            }
        
        # Actually charge user (call payment API)
        try:
            # TODO: Replace with actual payment API call
            charge_result = await self._execute_charge(charge_info)
            
            if charge_result.get('success'):
                # Mark as committed
                self._committed_charges.add(task_id)
                charge_info['status'] = 'committed'
                charge_info['committed_at'] = datetime.now().isoformat()
                
                # Remove from pending
                if task_id in self._pending_charges:
                    del self._pending_charges[task_id]
                
                # Store in persistent storage
                if self.storage:
                    try:
                        await self.storage.save_committed_charge(charge_info)
                    except Exception as e:
                        logger.error(f"Failed to save committed charge: {e}")
                
                logger.info(f"Committed charge for task {task_id}, amount: {charge_info['amount']}")
                return {
                    'status': 'committed',
                    'task_id': task_id,
                    'amount': charge_info['amount'],
                    'message': 'Оплачено',
                    'idempotent': False
                }
            else:
                logger.error(f"Failed to execute charge for task {task_id}: {charge_result.get('error')}")
                return {
                    'status': 'failed',
                    'task_id': task_id,
                    'message': 'Ошибка при списании средств',
                    'error': charge_result.get('error')
                }
        except Exception as e:
            logger.error(f"Exception during charge commit for task {task_id}: {e}", exc_info=True)
            return {
                'status': 'error',
                'task_id': task_id,
                'message': 'Произошла ошибка при списании',
                'error': str(e)
            }
    
    async def release_charge(self, task_id: str, reason: str = "generation_failed") -> Dict[str, Any]:
        """
        Release charge (refund/auto-refund) on fail/timeout/cancel.
        Idempotent: repeated calls are no-op.
        
        Args:
            task_id: Task identifier
            reason: Release reason (generation_failed, timeout, cancelled, etc.)
            
        Returns:
            Release result dict
        """
        # Idempotency check
        if task_id in self._released_charges:
            logger.info(f"Charge for task {task_id} already released (idempotent)")
            return {
                'status': 'already_released',
                'task_id': task_id,
                'message': 'Оплата уже отменена',
                'idempotent': True
            }
        
        # Check if already committed
        if task_id in self._committed_charges:
            # Need to refund
            logger.info(f"Refunding committed charge for task {task_id}")
            try:
                refund_result = await self._execute_refund(task_id, reason)
                if refund_result.get('success'):
                    self._released_charges.add(task_id)
                    return {
                        'status': 'refunded',
                        'task_id': task_id,
                        'message': 'Деньги возвращены',
                        'idempotent': False
                    }
                else:
                    return {
                        'status': 'refund_failed',
                        'task_id': task_id,
                        'message': 'Ошибка при возврате средств',
                        'error': refund_result.get('error')
                    }
            except Exception as e:
                logger.error(f"Exception during refund for task {task_id}: {e}", exc_info=True)
                return {
                    'status': 'refund_error',
                    'task_id': task_id,
                    'message': 'Произошла ошибка при возврате',
                    'error': str(e)
                }
        
        # Release pending charge (no actual charge happened, just cleanup)
        if task_id in self._pending_charges:
            charge_info = self._pending_charges[task_id]
            charge_info['status'] = 'released'
            charge_info['released_at'] = datetime.now().isoformat()
            charge_info['release_reason'] = reason
            
            self._released_charges.add(task_id)
            
            # Remove from pending
            del self._pending_charges[task_id]
            
            # Store in persistent storage
            if self.storage:
                try:
                    await self.storage.save_released_charge(charge_info)
                except Exception as e:
                    logger.error(f"Failed to save released charge: {e}")
            
            logger.info(f"Released pending charge for task {task_id}, reason: {reason}")
            return {
                'status': 'released',
                'task_id': task_id,
                'message': 'Деньги не списаны',
                'idempotent': False
            }
        
        # No charge found
        logger.warning(f"No charge found for task {task_id} to release")
        return {
            'status': 'not_found',
            'task_id': task_id,
            'message': 'Оплата не найдена'
        }
    
    async def get_charge_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current charge status for user visibility.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Status dict with user-friendly message
        """
        if task_id in self._committed_charges:
            return {
                'status': 'committed',
                'message': 'Оплачено'
            }
        
        if task_id in self._released_charges:
            return {
                'status': 'released',
                'message': 'Деньги не списаны'
            }
        
        if task_id in self._pending_charges:
            return {
                'status': 'pending',
                'message': 'Ожидание оплаты'
            }
        
        return {
            'status': 'not_found',
            'message': 'Оплата не найдена'
        }
    
    async def _execute_charge(self, charge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute actual charge (to be implemented with real payment API)."""
        # TODO: Implement actual payment API call
        logger.info(f"Executing charge: {charge_info}")
        return {'success': True, 'transaction_id': f"tx_{charge_info['task_id']}"}
    
    async def _execute_refund(self, task_id: str, reason: str) -> Dict[str, Any]:
        """Execute actual refund (to be implemented with real payment API)."""
        # TODO: Implement actual refund API call
        logger.info(f"Executing refund for task {task_id}, reason: {reason}")
        return {'success': True, 'refund_id': f"refund_{task_id}"}


# Global instance
_charge_manager: Optional[ChargeManager] = None


def get_charge_manager(storage=None) -> ChargeManager:
    """Get or create global charge manager instance."""
    global _charge_manager
    if _charge_manager is None:
        _charge_manager = ChargeManager(storage)
    return _charge_manager

