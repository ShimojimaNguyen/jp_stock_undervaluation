from src.verify import label_of, verify_candidate

ROWS = [  # Yahoo JP actuals (yên), YoY % do nguồn in
    {"endDate": f"{y}-03-31", "netSales": s, "netSalesYoy": yoy, "operatingIncome": op,
     "operatingCashFlow": cfo, "equityRatio": 60.0}
    for y, s, yoy, op, cfo in [(2023, 100e8, None, 8e8, 5e8), (2024, 115e8, 15.0, 10e8, 6e8),
                               (2025, 132.25e8, 15.0, 12e8, 7e8), (2026, 152.0875e8, 15.0, 14e8, 8e8)]
]
YF = {"annual": [{"fiscal_period": "2025.03", "revenue": 132.25e8},
                 {"fiscal_period": "2026.03", "revenue": 152.0875e8, "operating_profit": 14e8,
                  "cfo": 8e8}],
      "balance_sheet": {"equity": 90e8, "total_assets": 150e8}}


def _cand(mcap=190e8, cagr=0.15):
    return {"code": "9999", "scorecard": {
        "universe": {"market_cap": {"value": mcap}},
        "growth": {"checks": [{"name": "revenue_cagr", "value": cagr}]}}}


def test_all_ok():
    ch = verify_candidate(_cand(), YF, {"actuals": ROWS}, 195e8)
    assert {k: v["status"] for k, v in ch.items()} == {
        "market_cap": "ok", "revenue": "ok", "operating_profit": "ok", "cfo": "ok",
        "equity_ratio": "ok", "revenue_series": "ok"}
    assert label_of(ch) == "verify:ok"


def test_mismatch_flagged():
    yf = {**YF, "annual": YF["annual"][:1] + [{**YF["annual"][1], "operating_profit": 20e8}]}
    ch = verify_candidate(_cand(), yf, {"actuals": ROWS}, 195e8)
    assert ch["operating_profit"]["status"] == "mismatch"
    assert label_of(ch) == "verify:mismatch:operating_profit"


def test_wrong_unit_market_cap_caught():
    ch = verify_candidate(_cand(mcap=190e8 * 1000), YF, {"actuals": ROWS}, 195e8)
    assert ch["market_cap"]["status"] == "mismatch"      # sai bậc đơn vị 1000× (pillar §8)


def test_missing_path_is_partial_not_ok():
    ch = verify_candidate(_cand(), YF, None, None)
    assert ch["market_cap"]["status"] == "unchecked"
    assert label_of(ch) == "verify:partial"


def test_revenue_series_disagreement():
    yf = {**YF, "annual": [{"fiscal_period": "2025.03", "revenue": 100e8}] + YF["annual"][1:]}
    ch = verify_candidate(_cand(), yf, {"actuals": ROWS}, 195e8)
    assert ch["revenue_series"]["status"] == "mismatch"
