"""
Providers layer - centralized abstraction for all external service calls.

This layer ensures that:
1. All external calls go through providers
2. DRY_RUN mode is enforced at the provider level
3. No "accidental" real API calls can happen
4. Beautiful preview results are shown to users in DRY_RUN mode
"""

from app.providers.base import BaseProvider, ProviderResult
from app.providers.kie_provider import KieProvider, get_kie_provider
from app.providers.payment_provider import PaymentProvider, get_payment_provider

__all__ = [
    "BaseProvider",
    "ProviderResult",
    "KieProvider",
    "get_kie_provider",
    "PaymentProvider",
    "get_payment_provider",
]

