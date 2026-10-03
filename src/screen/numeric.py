"""Phép tính nhỏ dùng chung — tất cả trả None khi thiếu, không bao giờ 0."""
from __future__ import annotations

import math


def rnd(x: float | None, ndigits: int) -> float | None:
    """Làm tròn TRƯỚC khi so ngưỡng (0.82−0.67 = 0.1499999… không được trượt 0.15)."""
    if x is None:
        return None
    x = float(x)  # numpy scalar → float: np.False_ `is False` là False, sẽ lọt cổng
    if not math.isfinite(x):
        return None
    return round(x, ndigits)


def ge(x: float | None, threshold: float, ndigits: int) -> bool | None:
    v = rnd(x, ndigits)
    return None if v is None else v >= round(threshold, ndigits)


def le(x: float | None, threshold: float, ndigits: int) -> bool | None:
    v = rnd(x, ndigits)
    return None if v is None else v <= round(threshold, ndigits)


def gt(x: float | None, threshold: float, ndigits: int) -> bool | None:
    v = rnd(x, ndigits)
    return None if v is None else v > round(threshold, ndigits)


def ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def growth(new: float | None, base: float | None) -> float | None:
    """Tăng trưởng new/base − 1. Gốc ≤ 0 → None (tăng trưởng từ lỗ không có nghĩa)."""
    if new is None or base is None or base <= 0:
        return None
    return new / base - 1


def cagr(first: float | None, last: float | None, years: int) -> float | None:
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1 / years) - 1
