"""
Payment Gateway Utility — Abstract base and registry for payment processors.

Each gateway (bKash, Nagad, Rocket) implements BasePaymentProcessor.
The PaymentGatewayRegistry maps gateway strings to processor instances.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Optional

from ..choices import PaymentGateway
from ..exceptions import GatewayError, GatewayTimeoutError, GatewayAuthError

logger = logging.getLogger(__name__)


class PayoutResult:
    """
    Standardised result object returned by all gateway processors.

    Attributes:
        success:           True if the payout was accepted by the gateway.
        gateway_reference: Transaction ID from the gateway (set on success).
        error_code:        Short error code (set on failure).
        error_message:     Human-readable error description.
        raw_response:      Full response dict from the gateway.
    """

    __slots__ = (
        "success", "gateway_reference", "error_code",
        "error_message", "raw_response",
    )

    def __init__(
        self,
        *,
        success: bool,
        gateway_reference: str = "",
        error_code: str = "",
        error_message: str = "",
        raw_response: Optional[dict] = None,
    ) -> None:
        if not isinstance(success, bool):
            raise TypeError("success must be a bool.")
        if success and not gateway_reference:
            raise ValueError("gateway_reference must be set on success.")

        self.success = success
        self.gateway_reference = gateway_reference
        self.error_code = error_code
        self.error_message = error_message
        self.raw_response = raw_response or {}

    def __repr__(self) -> str:  # pragma: no cover
        if self.success:
            return f"<PayoutResult SUCCESS ref={self.gateway_reference!r}>"
        return f"<PayoutResult FAILED code={self.error_code!r} msg={self.error_message!r}>"


class BasePaymentProcessor(ABC):
    """
    Abstract base class for all payment gateway processors.

    Subclasses must implement:
        - send_payout(account_number, amount, reference, **kwargs) → PayoutResult
        - verify_transaction(gateway_reference) → PayoutResult
        - validate_account(account_number) → bool
    """

    gateway: str = ""   # Override in subclass

    def __init__(self, config: dict) -> None:
        """
        Args:
            config: Gateway-specific configuration dict
                    (e.g. API key, base URL, merchant ID).
        """
        if not isinstance(config, dict):
            raise TypeError("config must be a dict.")
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Override to validate required config keys."""
        pass

    @abstractmethod
    def send_payout(
        self,
        *,
        account_number: str,
        amount: Decimal,
        reference: str,
        **kwargs: Any,
    ) -> PayoutResult:
        """
        Dispatch a payout to the recipient.

        Args:
            account_number: Recipient wallet/bank number.
            amount:         Net payout amount (after fee deduction).
            reference:      Unique idempotency key for this payout.
            **kwargs:       Gateway-specific extra parameters.

        Returns:
            PayoutResult

        Raises:
            GatewayTimeoutError: On network/timeout failure.
            GatewayAuthError:    On authentication failure.
            GatewayError:        On other gateway errors.
        """

    @abstractmethod
    def verify_transaction(self, gateway_reference: str) -> PayoutResult:
        """
        Verify the status of a previously initiated payout.

        Args:
            gateway_reference: Transaction ID from the gateway.

        Returns:
            PayoutResult
        """

    @abstractmethod
    def validate_account(self, account_number: str) -> bool:
        """
        Validate a recipient account number format.

        Args:
            account_number: The account/wallet number to validate.

        Returns:
            True if valid, False otherwise.
        """

    def _require_config(self, *keys: str) -> None:
        """Assert that required config keys are present and non-empty."""
        missing = [k for k in keys if not self.config.get(k)]
        if missing:
            raise GatewayAuthError(
                f"{self.__class__.__name__}: missing required config keys: {missing}"
            )


# ---------------------------------------------------------------------------
# Gateway Registry
# ---------------------------------------------------------------------------

class PaymentGatewayRegistry:
    """
    Registry mapping PaymentGateway choices to processor instances.

    Usage:
        registry = PaymentGatewayRegistry()
        registry.register(PaymentGateway.BKASH, BkashProcessor(config))
        processor = registry.get(PaymentGateway.BKASH)
        result = processor.send_payout(...)
    """

    def __init__(self) -> None:
        self._processors: dict[str, BasePaymentProcessor] = {}

    def register(self, gateway: str, processor: BasePaymentProcessor) -> None:
        """
        Register a processor for a gateway.

        Args:
            gateway:   PaymentGateway choice string.
            processor: Configured BasePaymentProcessor instance.

        Raises:
            ValueError: If gateway is not a valid PaymentGateway choice.
            TypeError:  If processor is not a BasePaymentProcessor subclass.
        """
        if gateway not in PaymentGateway.values:
            raise ValueError(
                f"Invalid gateway '{gateway}'. Valid: {PaymentGateway.values}"
            )
        if not isinstance(processor, BasePaymentProcessor):
            raise TypeError(
                f"processor must be a BasePaymentProcessor instance, got {type(processor).__name__}."
            )
        self._processors[gateway] = processor
        logger.info("PaymentGatewayRegistry: registered processor for gateway '%s'.", gateway)

    def get(self, gateway: str) -> BasePaymentProcessor:
        """
        Retrieve the processor for a gateway.

        Args:
            gateway: PaymentGateway choice string.

        Returns:
            The registered BasePaymentProcessor.

        Raises:
            GatewayError: If no processor is registered for the gateway.
        """
        if not gateway or not isinstance(gateway, str):
            raise GatewayError("gateway must be a non-empty string.")
        processor = self._processors.get(gateway)
        if processor is None:
            raise GatewayError(
                f"No processor registered for gateway '{gateway}'. "
                f"Registered: {list(self._processors.keys())}"
            )
        return processor

    def is_registered(self, gateway: str) -> bool:
        return gateway in self._processors

    def registered_gateways(self) -> list[str]:
        return list(self._processors.keys())
