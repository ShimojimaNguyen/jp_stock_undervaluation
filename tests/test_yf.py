"""Adapter yfinance — DataFrame GIẢ, nhãn dòng lấy đúng như yfinance trả trên Actions 2026-10-07."""
from datetime import date

import pandas as pd

from src.contracts import Market, Tier
from src.data.yf_fundamentals import build_fundamentals
from src.screen.growth import growth_gate
from src.screen.universe import market_cap
from src.screen.valuation import kiyohara_net_cash

COLS = [pd.Timestamp(f"{y}-03-31") for y in (2026, 2025, 2024, 2023, 2022)]
NAN = float("nan")


def _df(rows):
    return pd.DataFrame({c: [rows[k][i] for k in rows] for i, c in enumerate(COLS)},
                        index=list(rows))


INCOME = _df({"Total Revenue": [152.0875e8, 132.25e8, 115e8, 100e8, NAN],
              "Operating Income": [14e8, 12e8, 10e8, 8e8, NAN],
              "Diluted EPS": [84.0, 72.0, 60.0, 50.0, NAN]})
CASH = _df({"Operating Cash Flow": [8e8, 7e8, 6e8, 5e8, NAN]})
BAL = _df({"Current Assets": [120e8, 1, 1, 1, NAN],
           "Total Liabilities Net Minority Interest": [60e8, 1, 1, 1, NAN],
           "Investmentin Financial Assets": [10e8, 1, 1, 1, NAN],
           "Total Assets": [150e8, 1, 1, 1, NAN], "Stockholders Equity": [90e8, 1, 1, 1, NAN],
           "Share Issued": [10_000_000, 1, 1, 1, NAN],
           "Treasury Shares Number": [500_000, 1, 1, 1, NAN]})


def test_build_fundamentals_maps_fields(params):
    f = build_fundamentals("9999", INCOME, BAL, CASH, Market.GROWTH, "x", date(2026, 10, 7))
    assert [a.fiscal_period for a in f.annual] == ["2023.03", "2024.03", "2025.03", "2026.03"]
    assert f.annual[-1].cfo == 8e8 and f.annual[0].months == 12
    assert f.forecast is None
    assert kiyohara_net_cash(f.balance_sheet, 0.7) == 120e8 + 7e8 - 60e8
    assert f.shares_issued.value == 10_000_000 and f.treasury_shares.value == 500_000
    g = growth_gate(f, params.growth)
    by = {c.name: c.passed for c in g.checks}
    assert by["revenue_cagr"] and by["cfo_positive"] and by["equity_ratio"]
    assert by["op_forecast_growth"] is None and not g.passed     # thiếu 会社予想 ≠ qua


def test_zero_investment_securities_is_unknown():
    bal = BAL.copy()
    bal.loc["Investmentin Financial Assets", COLS[0]] = 0.0
    f = build_fundamentals("9999", INCOME, bal, CASH, None, None, date(2026, 10, 7))
    assert f.balance_sheet.investment_securities is None
    assert kiyohara_net_cash(f.balance_sheet, 0.7) is None


def test_nan_is_none_not_zero():
    inc = INCOME.copy()
    inc.loc["Operating Income", COLS[0]] = NAN
    f = build_fundamentals("9999", inc, BAL, CASH, None, None, date(2026, 10, 7))
    assert f.annual[-1].operating_profit is None


def test_irregular_period_detected():
    cols = [pd.Timestamp("2025-12-31"), pd.Timestamp("2025-03-31"), pd.Timestamp("2024-03-31")]
    inc = pd.DataFrame({c: [100e8, 1e8, 1.0] for c in cols},
                       index=["Total Revenue", "Operating Income", "Diluted EPS"])
    f = build_fundamentals("9999", inc, None, None, None, None, date(2026, 10, 7))
    assert [a.months for a in f.annual] == [12, 12, None]


def test_awaiting_forecast_listed(params):
    from src.contracts import PriceSnapshot, Sourced
    from src.pipeline import awaiting_forecast, build_export, evaluate_code

    f = build_fundamentals("9999", INCOME, BAL, CASH, Market.GROWTH, "x", date(2026, 10, 7))
    snap = PriceSnapshot(code="9999", close=Sourced.of(2000.0, date(2026, 10, 6), "y"))
    c = evaluate_code("9999", f, snap, None, {}, [], date(2026, 10, 7), params)
    assert c.tier is Tier.NONE and awaiting_forecast(c)
    mcap = market_cap(snap.close, f.shares_issued, f.treasury_shares)
    assert mcap.value == 2000.0 * 9_500_000
    exp = build_export([c], date(2026, 10, 7), params, [], [])
    assert exp.counts["awaiting_forecast"] == 1 and exp.awaiting_forecast[0].code == "9999"
