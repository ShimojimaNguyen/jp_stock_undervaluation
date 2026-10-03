"""Bước 7 — ThesisCheck mỗi quý: INTACT / WEAKENING / BROKEN (code).

  BROKEN    doanh thu luỹ kế YoY ≤ 0; hoặc 下方修正/減配 trong cửa sổ;
            hoặc cổng tăng trưởng giờ TRƯỢT (không tính trường hợp thiếu dữ liệu)
  WEAKENING tăng trưởng doanh thu YoY chậm lại ≥ N điểm % so với quý trước;
            OPM giảm ≥ M điểm % YoY; 特別損失 trong cửa sổ; mất catalyst
            (có catalyst dương ở cửa sổ trước, cửa sổ này không còn)
  INTACT    còn lại

RSI cao KHÔNG phải điều kiện bán với nhãn 10x — module này không đọc RSI.
"""
from __future__ import annotations

from datetime import date, timedelta

from src.contracts import (
    CatalystEvent,
    CatalystStrength,
    CatalystType,
    GrowthGate,
    QuarterResult,
    ThesisCheck,
    ThesisStatus,
)
from src.params import ThesisParams

BREAKING = {CatalystType.DOWNWARD_REVISION, CatalystType.DIVIDEND_CUT}


def thesis_check(code: str, as_of: date, quarters: list[QuarterResult],
                 catalysts: list[CatalystEvent], growth: GrowthGate | None,
                 p: ThesisParams) -> ThesisCheck:
    broken: list[str] = []
    weak: list[str] = []
    missing = False

    win_start = as_of - timedelta(days=p.catalyst_lookback_days)
    prev_start = win_start - timedelta(days=p.catalyst_lookback_days)
    in_win = [c for c in catalysts if win_start <= c.effective_date <= as_of]
    in_prev = [c for c in catalysts if prev_start <= c.effective_date < win_start]

    cur = quarters[-1] if quarters else None
    prev = quarters[-2] if len(quarters) >= 2 else None

    if cur is None or cur.revenue_yoy is None:
        missing = True
    else:
        if round(cur.revenue_yoy, 4) <= round(p.broken_revenue_yoy_max, 4):
            broken.append(f"revenue_yoy={round(cur.revenue_yoy, 4)}")
        if prev is not None and prev.revenue_yoy is not None:
            drop = round(prev.revenue_yoy - cur.revenue_yoy, 4)
            if drop >= round(p.weakening_revenue_yoy_drop, 4):
                weak.append(f"revenue_yoy_slowdown={drop}")
    if cur is not None and cur.opm is not None and cur.opm_prev_year is not None:
        d = round(cur.opm_prev_year - cur.opm, 4)
        if d >= round(p.opm_drop_weakening, 4):
            weak.append(f"opm_drop={d}")
    elif cur is not None:
        missing = True

    for c in in_win:
        if c.type in BREAKING:
            broken.append(f"{c.type.value}@{c.effective_date}")
        elif c.type is CatalystType.EXTRAORDINARY_LOSS:
            weak.append(f"{c.type.value}@{c.effective_date}")

    def positive(cs):
        return [c for c in cs if c.strength.rank >= CatalystStrength.LOW.rank]

    if positive(in_prev) and not positive(in_win):
        weak.append("catalyst_lost")

    if growth is not None and not growth.passed and not growth.insufficient_data:
        broken.append("growth_gate_failed")
    elif growth is None or growth.insufficient_data:
        missing = True

    if broken:
        status, reasons = ThesisStatus.BROKEN, broken + weak
    elif weak:
        status, reasons = ThesisStatus.WEAKENING, weak
    else:
        status, reasons = ThesisStatus.INTACT, []
    return ThesisCheck(code=code, as_of=as_of, status=status, reasons=reasons,
                       insufficient_data=missing)
