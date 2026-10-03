"""Bước 2 — lọc tăng trưởng (bắt buộc). Thiếu dữ liệu = KHÔNG qua (insufficient_data).

Năm checks, tất cả phải True:
  revenue_cagr      CAGR doanh thu 3 năm (4 năm thực hiện liên tiếp, đủ 12 tháng)
  op_forecast       dự báo OP của công ty / OP thực hiện năm gần nhất − 1
  opm_improving     OPM dự báo > OPM năm gần nhất
  cfo_positive      営業CF năm gần nhất > 0
  equity_ratio      自己資本 / 総資産
"""
from __future__ import annotations

from src.contracts import AnnualResult, Fundamentals, GateCheck, GrowthGate
from src.params import GrowthParams
from src.screen.numeric import cagr, ge, growth, gt, ratio, rnd


def _last_n_full_years(annual: list[AnnualResult], n: int) -> list[AnnualResult] | None:
    """n năm cuối, phải đủ 12 tháng — kỳ đổi niên độ (変) làm CAGR vô nghĩa."""
    if len(annual) < n:
        return None
    rows = annual[-n:]
    if any(r.months != 12 for r in rows):
        return None
    return rows


def revenue_cagr(f: Fundamentals, years: int) -> tuple[float | None, str | None]:
    rows = _last_n_full_years(f.annual, years + 1)
    if rows is None:
        return None, f"cần {years + 1} năm thực hiện đủ 12 tháng"
    return cagr(rows[0].revenue, rows[-1].revenue, years), None


def forecast_is_current(f: Fundamentals) -> bool:
    """Dự báo phải là cho kỳ SAU năm thực hiện gần nhất, không phải dự báo cũ."""
    if f.forecast is None or not f.annual:
        return False
    return f.forecast.fiscal_period > f.annual[-1].fiscal_period


def op_forecast_growth(f: Fundamentals) -> tuple[float | None, str | None]:
    if not forecast_is_current(f):
        return None, "thiếu dự báo công ty cho kỳ kế tiếp"
    return growth(f.forecast.operating_profit, f.annual[-1].operating_profit), None


def opm_pair(f: Fundamentals) -> tuple[float | None, float | None]:
    """(OPM năm gần nhất, OPM dự báo)."""
    if not f.annual:
        return None, None
    last = ratio(f.annual[-1].operating_profit, f.annual[-1].revenue)
    fc = None
    if forecast_is_current(f):
        fc = ratio(f.forecast.operating_profit, f.forecast.revenue)
    return last, fc


def equity_ratio(f: Fundamentals) -> float | None:
    bs = f.balance_sheet
    if bs is None or bs.total_assets is None or bs.total_assets <= 0:
        return None
    return ratio(bs.equity, bs.total_assets)


def growth_gate(f: Fundamentals, p: GrowthParams) -> GrowthGate:
    nd = p.round_ndigits
    checks: list[GateCheck] = []

    rc, note = revenue_cagr(f, p.revenue_cagr_years)
    checks.append(GateCheck(name="revenue_cagr", value=rnd(rc, nd), threshold=p.revenue_cagr_min,
                            passed=ge(rc, p.revenue_cagr_min, nd), note=note))

    og, note = op_forecast_growth(f)
    checks.append(GateCheck(name="op_forecast_growth", value=rnd(og, nd),
                            threshold=p.op_forecast_growth_min,
                            passed=ge(og, p.op_forecast_growth_min, nd), note=note))

    last_opm, fc_opm = opm_pair(f)
    opm_ok = None
    if last_opm is not None and fc_opm is not None:
        opm_ok = gt(fc_opm, last_opm, nd) if p.opm_improving else True
    checks.append(GateCheck(name="opm_improving", value=rnd(fc_opm, nd),
                            threshold=rnd(last_opm, nd), passed=opm_ok))

    cfo = f.annual[-1].cfo if f.annual else None
    checks.append(GateCheck(name="cfo_positive", value=cfo, threshold=p.cfo_min_jpy,
                            passed=None if cfo is None else cfo > p.cfo_min_jpy))

    er = equity_ratio(f)
    checks.append(GateCheck(name="equity_ratio", value=rnd(er, nd), threshold=p.equity_ratio_min,
                            passed=ge(er, p.equity_ratio_min, nd)))

    as_of = max((d for d in (
        f.annual[-1].as_of if f.annual else None,
        f.forecast.as_of if f.forecast else None,
        f.balance_sheet.as_of if f.balance_sheet else None,
    ) if d is not None), default=None)
    return GrowthGate(
        code=f.code, checks=checks,
        passed=all(c.passed is True for c in checks),
        insufficient_data=any(c.passed is None for c in checks),
        as_of=as_of,
    )
