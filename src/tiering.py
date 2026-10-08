"""Bước 8 — phân tầng A/B/C (code, tham số ở config/params.yaml `tiers`).

  A = qua bước 1 + 2, PEG ≤ 1, net cash ratio ≥ 0,3, checklist ≥ 3/5,
      ≥ 1 catalyst dương bậc ≥ 中 (MEDIUM)            → nhãn "10x"
  B = qua bước 2 (+ bước 1 nếu b_requires_universe), PEG ≤ 1,5,
      và (checklist ≥ 2/5 hoặc có catalyst dương)
  C = chỉ qua bước 2
  NONE = không qua bước 2 (kể cả vì thiếu dữ liệu)

Giá trị None ở bất kỳ điều kiện nào = điều kiện đó KHÔNG đạt (không suy ra).
entry_signal không tham gia — tách riêng.
"""
from __future__ import annotations

from datetime import date, timedelta

from src.contracts import CatalystEvent, CatalystStrength, ScoreCard, Tier
from src.params import Params


def active_catalysts(events: list[CatalystEvent], as_of: date, lookback_days: int
                     ) -> list[CatalystEvent]:
    """Chỉ catalyst có hiệu lực TRONG cửa sổ [as_of − N, as_of] — không look-ahead."""
    start = as_of - timedelta(days=lookback_days)
    return [e for e in events if start <= e.effective_date <= as_of]


def _le(x: float | None, th: float) -> bool:
    return x is not None and round(x, 4) <= round(th, 4)


def _ge(x: float | None, th: float) -> bool:
    return x is not None and round(x, 4) >= round(th, 4)


def assign_tier(sc: ScoreCard, as_of: date, p: Params) -> tuple[Tier, list[str], list[str]]:
    """→ (tầng, nhãn, lý do). Lý do liệt kê điều kiện nào đạt/trượt để kiểm lại được."""
    t = p.tiers
    reasons: list[str] = []
    uni = bool(sc.universe and sc.universe.passed)
    grw = bool(sc.growth and sc.growth.passed)
    if not grw:
        # Một check ĐO ĐƯỢC đã trượt → "fail", dù check khác còn trống: trống ở đây
        # thường vì không cần tra (vd không hỏi 会社予想 cho mã đã trượt CAGR).
        known_fail = bool(sc.growth and any(c.passed is False for c in sc.growth.checks))
        why = "fail" if known_fail or not sc.growth else (
            "insufficient_data" if sc.growth.insufficient_data else "fail")
        return Tier.NONE, [], [f"growth:{why}"]
    reasons.append("growth:pass")
    if uni:
        reasons.append("universe:pass")
    elif sc.universe is None or sc.universe.insufficient_data:
        reasons.append("universe:insufficient_data")
    else:
        reasons.append("universe:fail")

    v = sc.valuation
    peg = v.peg if v else None
    ncr = v.net_cash_ratio if v else None
    score = sc.checklist.score if sc.checklist else 0
    cats = active_catalysts(sc.catalysts, as_of, t.catalyst_lookback_days)
    pos = [c for c in cats if c.strength.rank >= CatalystStrength.LOW.rank]
    strong = [c for c in cats if c.strength.rank >= t.a_catalyst_min_strength.rank]
    reasons += [f"peg:{peg}", f"net_cash_ratio:{ncr}",
                f"checklist:{score}/{t.checklist_total}", f"catalysts:{len(pos)}(≥中:{len(strong)})"]

    if (uni and _le(peg, p.valuation.peg_max_tier_a)
            and _ge(ncr, p.valuation.net_cash_ratio_min_tier_a)
            and score >= t.a_checklist_min and strong):
        return Tier.A, ["10x"], reasons
    if ((uni or not t.b_requires_universe) and _le(peg, p.valuation.peg_max_tier_b)
            and (score >= t.b_checklist_min or pos)):
        return Tier.B, [], reasons
    return Tier.C, [], reasons
