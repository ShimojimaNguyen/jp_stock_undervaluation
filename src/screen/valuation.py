"""Bước 3 — định giá: PEG và net cash theo ĐÚNG công thức 清原.

  PEG          = PER dự phóng / (tăng trưởng EPS dự phóng × 100)
                 tăng trưởng ≤ 0 hoặc thiếu → None; tăng trưởng bị cap ở eps_growth_cap
  ネットキャッシュ = 流動資産 + 投資有価証券 × 0.7 − 負債合計
  比率         = ネットキャッシュ / 時価総額,  時価総額 = 株価 × (発行済 − 自己株)

Thiếu BẤT KỲ thành phần nào → None. Không coi 投資有価証券 thiếu là 0: một công ty
không công bố dòng đó khác với một công ty có 0 yên chứng khoán đầu tư.
"""
from __future__ import annotations

from src.contracts import BalanceSheet, Fundamentals, Sourced, Valuation
from src.params import ValuationParams
from src.screen.growth import forecast_is_current
from src.screen.numeric import growth, ratio, rnd


def kiyohara_net_cash(bs: BalanceSheet | None, haircut: float) -> float | None:
    if bs is None:
        return None
    ca, inv, tl = bs.current_assets, bs.investment_securities, bs.total_liabilities
    if ca is None or inv is None or tl is None:
        return None
    return ca + inv * haircut - tl


def eps_forecast_growth(f: Fundamentals) -> float | None:
    if not forecast_is_current(f):
        return None
    return growth(f.forecast.eps, f.annual[-1].eps)


def peg(per: float | None, eps_growth: float | None, cap: float, ndigits: int) -> float | None:
    if per is None or per <= 0 or eps_growth is None or eps_growth <= 0:
        return None
    return rnd(per / (min(eps_growth, cap) * 100), ndigits)


def valuation(f: Fundamentals, price: Sourced, mcap: Sourced, p: ValuationParams) -> Valuation:
    nd = p.round_ndigits
    eps_fc = f.forecast.eps if forecast_is_current(f) else None
    # PER tính từ CÙNG nguồn EPS với tăng trưởng EPS — không trộn PER của nguồn
    # giá (Kabutan dùng 修正1株益, lệch ~1–2% có hệ thống với nguồn khác).
    per = ratio(price.value, eps_fc) if eps_fc is not None and eps_fc > 0 else None
    g = eps_forecast_growth(f)
    nc = kiyohara_net_cash(f.balance_sheet, p.investment_securities_haircut)
    sources = [s for s in (
        price.source,
        f.forecast.source if f.forecast else None,
        f.balance_sheet.source if f.balance_sheet else None,
        mcap.source,
    ) if s]
    return Valuation(
        code=f.code,
        per_forecast=rnd(per, nd),
        eps_growth=rnd(g, nd),
        eps_growth_capped=rnd(min(g, p.eps_growth_cap), nd) if g is not None else None,
        peg=peg(per, g, p.eps_growth_cap, nd),
        market_cap=mcap.value,
        net_cash=nc,
        net_cash_ratio=rnd(ratio(nc, mcap.value), nd),
        as_of=price.as_of,
        sources=list(dict.fromkeys(sources)),
    )
