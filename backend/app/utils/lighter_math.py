"""
Lighter Protocol Integer Scaling & Precision Engine.

Lighter requires all prices and sizes to be submitted as scaled integers.
This module provides deterministic conversion functions with no floating-point
rounding artifacts.

Example:
    Price $45,000 with 2 decimals → 4,500,000 (scaled int)
    Size 0.001 BTC with 6 decimals → 1,000 (scaled int)
"""

import logging
import math
from typing import Tuple

logger = logging.getLogger(__name__)

# Default market decimals for BTC/USDC on Lighter
DEFAULT_PRICE_DECIMALS = 2
DEFAULT_SIZE_DECIMALS = 6


def scale_price(price: float, decimals: int) -> int:
    """
    Convert float price to scaled integer.

    Args:
        price: Price as float (e.g., 45000.25)
        decimals: Decimal places for scaling (e.g., 2 for USDC)

    Returns:
        Scaled integer (e.g., 4500025)

    Raises:
        ValueError: If price is negative, NaN, or inf
    """
    if math.isnan(price) or math.isinf(price):
        raise ValueError(f"Price must be a finite number, got {price}")
    if price < 0:
        raise ValueError(f"Price must be non-negative, got {price}")

    scaled = int(round(price * (10 ** decimals)))
    logger.debug(f"[LIGHTER_MATH] scale_price({price}, {decimals}) → {scaled}")
    return scaled


def scale_size(size: float, decimals: int) -> int:
    """
    Convert float size to scaled integer.

    Args:
        size: Size as float (e.g., 0.001 BTC)
        decimals: Decimal places for scaling (e.g., 6)

    Returns:
        Scaled integer (e.g., 1000)

    Raises:
        ValueError: If size is negative, NaN, or inf
    """
    if math.isnan(size) or math.isinf(size):
        raise ValueError(f"Size must be a finite number, got {size}")
    if size < 0:
        raise ValueError(f"Size must be non-negative, got {size}")

    scaled = int(round(size * (10 ** decimals)))
    logger.debug(f"[LIGHTER_MATH] scale_size({size}, {decimals}) → {scaled}")
    return scaled


def unscale_price(scaled: int, decimals: int) -> float:
    """
    Convert scaled integer back to float price.

    Args:
        scaled: Scaled integer (e.g., 4500025)
        decimals: Decimal places used during scaling

    Returns:
        Float price (e.g., 45000.25)

    Raises:
        ValueError: If decimals is negative
    """
    if decimals < 0:
        raise ValueError(f"Decimals must be non-negative, got {decimals}")

    unscaled = scaled / (10 ** decimals)
    logger.debug(f"[LIGHTER_MATH] unscale_price({scaled}, {decimals}) → {unscaled}")
    return unscaled


def unscale_size(scaled: int, decimals: int) -> float:
    """
    Convert scaled integer back to float size.

    Args:
        scaled: Scaled integer (e.g., 1000)
        decimals: Decimal places used during scaling

    Returns:
        Float size (e.g., 0.001)

    Raises:
        ValueError: If decimals is negative
    """
    if decimals < 0:
        raise ValueError(f"Decimals must be non-negative, got {decimals}")

    unscaled = scaled / (10 ** decimals)
    logger.debug(f"[LIGHTER_MATH] unscale_size({scaled}, {decimals}) → {unscaled}")
    return unscaled


def calculate_btc_quantity(
    size_usdt: float,
    price: float,
    size_decimals: int
) -> Tuple[float, int]:
    """
    Calculate BTC quantity from USDT margin and current price.

    Returns both the float quantity and the scaled integer.

    Args:
        size_usdt: Margin in USDT (e.g., 1000)
        price: Current BTC price in USDC (e.g., 45000)
        size_decimals: Decimal places for size scaling

    Returns:
        Tuple of (quantity_float, quantity_scaled)
        Example: (0.02222..., 22222) for $1000 at $45k with 6 decimals

    Raises:
        ValueError: If inputs are invalid or price is zero
    """
    if math.isnan(price) or math.isinf(price):
        raise ValueError(f"Price must be a finite number, got {price}")
    if price <= 0:
        raise ValueError(f"Price must be positive, got {price}")
    if size_usdt < 0:
        raise ValueError(f"Size USDT must be non-negative, got {size_usdt}")

    quantity_float = size_usdt / price
    quantity_scaled = scale_size(quantity_float, size_decimals)

    logger.info(
        f"[LIGHTER_MATH] calculate_btc_quantity(${size_usdt}, ${price}, {size_decimals}) "
        f"→ {quantity_float:.8f} BTC (scaled: {quantity_scaled})"
    )
    return quantity_float, quantity_scaled


def validate_scaled_values(price_scaled: int, size_scaled: int) -> bool:
    """
    Basic validation that scaled values are reasonable (positive integers).

    Args:
        price_scaled: Scaled price integer
        size_scaled: Scaled size integer

    Returns:
        True if both are non-negative integers

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(price_scaled, int) or not isinstance(size_scaled, int):
        raise ValueError(
            f"Scaled values must be integers, got "
            f"price={type(price_scaled).__name__}, size={type(size_scaled).__name__}"
        )
    if price_scaled < 0 or size_scaled < 0:
        raise ValueError(
            f"Scaled values must be non-negative, got price={price_scaled}, size={size_scaled}"
        )
    return True
