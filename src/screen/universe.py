"""Bước 1 — universe: thị trường TSE, vốn hoá 50–1000億円, thanh khoản GTGD TB 20 phiên."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.contracts import GateCheck, Market, Quality, Sourced, UniverseGate
from src.params import UniverseParams


def market_cap(price: Sourced, shares_issued: Sourced, treasury: Sourced) -> Sourced:
    """時価総額 = 株価 × (発行済 − 自己株) — đúng định nghĩa 清原.

    Thiếu bất kỳ thành phần nào (kể cả 自己株) → None. Không giả định 自己株 = 0.
    """
    if price.value is None or shares_issued.value is None or treasury.value is None:
        return Sourced.missing()
    outstanding = shares_issued.value - treasury.value
    if outstanding <= 0:
        return Sourced.missing()
    q = Quality.LIVE
    if Quality.STALE in (price.quality, shares_issued.quality, treasury.quality):
        q = Quality.STALE
    src = " × ".join(dict.fromkeys(s for s in (price.source, shares_issued.source, treasury.source) if s))
    return Sourced.of(price.value * outstanding, price.as_of, src, q)


def adtv(closes: Sequence[float | None], volumes: Sequence[float | None],
         window: int) -> float | None:
    """GTGD bình quân `window` phiên cuối của chuỗi (chuỗi chỉ gồm phiên ĐÃ đóng).

    Thiếu phiên hoặc phiên nào thiếu close/volume → None (không lấp 0).
    """
    if len(closes) != len(volumes) or len(closes) < window:
        return None
    vals = []
    for c, v in zip(closes[-window:], volumes[-window:], strict=True):
        if c is None or v is None:
            return None
        vals.append(c * v)
    return sum(vals) / window


def universe_gate(code: str, market: Market | None, mcap: Sourced, adtv_jpy: Sourced,
                  p: UniverseParams, as_of: date | None = None) -> UniverseGate:
    checks = [
        GateCheck(name="market", passed=None if market is None else market in p.markets,
                  note=None if market is None else market.value),
        GateCheck(name="market_cap_min", value=mcap.value, threshold=p.market_cap_min_jpy,
                  passed=None if mcap.value is None else mcap.value >= p.market_cap_min_jpy),
        GateCheck(name="market_cap_max", value=mcap.value, threshold=p.market_cap_max_jpy,
                  passed=None if mcap.value is None else mcap.value <= p.market_cap_max_jpy),
        GateCheck(name="adtv_min", value=adtv_jpy.value, threshold=p.adtv_min_jpy,
                  passed=None if adtv_jpy.value is None else adtv_jpy.value >= p.adtv_min_jpy),
    ]
    return UniverseGate(
        code=code, market=market, market_cap=mcap, adtv=adtv_jpy, checks=checks,
        passed=all(c.passed is True for c in checks),
        insufficient_data=any(c.passed is None for c in checks),
        as_of=as_of or mcap.as_of,
    )
