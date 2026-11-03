"""Order calculations used by the checkout and the order history pages."""

import time
from datetime import datetime, timedelta

SALES_TAX_RATE = 0.08
FREE_SHIPPING_THRESHOLD = 50.00
FLAT_SHIPPING_FEE = 4.99
CANCELLATION_WINDOW = timedelta(minutes=30)


def calculate_order_total(subtotal: float, discount: float = 0.0) -> float:
    """Total charged to the customer: discount first, then 8% sales tax, then shipping.
    Shipping is free when the discounted subtotal is at least 50.00."""
    if subtotal < 0 or discount < 0:
        raise ValueError("amounts must not be negative")
    discounted = max(subtotal - discount, 0.0)
    shipping = 0.0 if discounted >= FREE_SHIPPING_THRESHOLD else FLAT_SHIPPING_FEE
    return round(discounted * (1 + SALES_TAX_RATE) + shipping, 2)


def apply_discount_code(subtotal: float, code: str) -> float:
    """SAVE10 takes 10% off; WELCOME5 takes 5.00 off orders of 20.00 or more."""
    code = code.strip().upper()
    if code == "SAVE10":
        return round(subtotal * 0.10, 2)
    if code == "WELCOME5" and subtotal >= 20:
        return 5.00
    raise ValueError(f"unknown or inapplicable discount code: {code}")


def can_cancel(status: str, placed_at: datetime, now: datetime) -> bool:
    """Only pending orders can be cancelled, and only within 30 minutes of being placed."""
    return status == "pending" and now - placed_at <= CANCELLATION_WINDOW


def with_retries(call, attempts: int = 3, base_delay: float = 0.5):
    """Call `call()`, retrying on ConnectionError with exponential backoff (0.5s, 1s, 2s)."""
    for attempt in range(attempts):
        try:
            return call()
        except ConnectionError:
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay * 2**attempt)
