import json
from datetime import date

import pytest
from pydantic import ValidationError

from src.contracts import AnnualResult, BalanceSheet, Forecast, Market, Sourced
from src.data.adapters import JsonFundamentalsSource, KiyoharaSnapshotSource
from src.screen.growth import growth_gate
from src.screen.numeric import ge, rnd
from src.screen.universe import adtv, market_cap, universe_gate
from src.screen.valuation import kiyohara_net_cash, peg, valuation
from tests.conftest import SRC, D, make_fundamentals

PRICE = Sourced.of(2000.0, D, "px")


def _mcap(f):
    return market_cap(PRICE, f.shares_issued, f.treasury_shares)


# ---------------------------------------------------------------- numeric
def test_round_before_compare():
    assert 0.82 - 0.67 < 0.15                      # bẫy float thật
    assert ge(0.82 - 0.67, 0.15, 4) is True        # làm tròn trước → qua
    assert ge(None, 0.15, 4) is None
    assert rnd(float("nan"), 4) is None


# ---------------------------------------------------------------- bước 1
def test_market_cap_uses_outstanding_shares(fundamentals):
    m = _mcap(fundamentals)
    assert m.value == 2000.0 * 9_500_000


def test_market_cap_missing_treasury_is_none(fundamentals):
    m = market_cap(PRICE, fundamentals.shares_issued, Sourced.missing())
    assert m.value is None


def test_adtv_requires_full_window():
    assert adtv([100.0] * 19, [1000.0] * 19, 20) is None
    assert adtv([100.0] * 20, [1000.0] * 20, 20) == 100_000.0
    assert adtv([100.0] * 19 + [None], [1000.0] * 20, 20) is None


def test_universe_gate(params, fundamentals):
    m = _mcap(fundamentals)  # 190億
    a = Sourced.of(5e7, D, SRC)
    g = universe_gate("9999", Market.STANDARD, m, a, params.universe)
    assert g.passed and not g.insufficient_data
    big = Sourced.of(2e11, D, SRC)
    assert not universe_gate("9999", Market.PRIME, big, a, params.universe).passed
    thin = Sourced.of(1e7, D, SRC)
    assert not universe_gate("9999", Market.PRIME, m, thin, params.universe).passed
    g = universe_gate("9999", Market.GROWTH, m, Sourced.missing(), params.universe)
    assert not g.passed and g.insufficient_data


# ---------------------------------------------------------------- bước 2
def test_growth_gate_passes(params, fundamentals):
    g = growth_gate(fundamentals, params.growth)
    assert g.passed, [c for c in g.checks if c.passed is not True]
    rc = next(c for c in g.checks if c.name == "revenue_cagr")
    assert rc.value == 0.15


def test_growth_gate_missing_years_is_insufficient(params):
    f = make_fundamentals()
    f = f.model_copy(update={"annual": f.annual[1:]})
    g = growth_gate(f, params.growth)
    assert not g.passed and g.insufficient_data


def test_growth_gate_irregular_period_blocks_cagr(params):
    f = make_fundamentals()
    rows = list(f.annual)
    rows[1] = rows[1].model_copy(update={"months": 9})
    g = growth_gate(f.model_copy(update={"annual": rows}), params.growth)
    assert next(c for c in g.checks if c.name == "revenue_cagr").passed is None


def test_growth_gate_stale_forecast(params):
    f = make_fundamentals(forecast=Forecast(fiscal_period="2026.03", revenue=1, operating_profit=1,
                                            eps=1, source=SRC, as_of=D))
    g = growth_gate(f, params.growth)
    assert next(c for c in g.checks if c.name == "op_forecast_growth").passed is None
    assert not g.passed


def test_growth_gate_fails_on_negative_cfo(params):
    f = make_fundamentals()
    rows = list(f.annual)
    rows[-1] = rows[-1].model_copy(update={"cfo": -1e8})
    g = growth_gate(f.model_copy(update={"annual": rows}), params.growth)
    assert next(c for c in g.checks if c.name == "cfo_positive").passed is False
    assert not g.passed and not g.insufficient_data


def test_growth_gate_low_equity_ratio(params):
    f = make_fundamentals()
    bs = f.balance_sheet.model_copy(update={"equity": 50e8})  # 33%
    g = growth_gate(f.model_copy(update={"balance_sheet": bs}), params.growth)
    assert next(c for c in g.checks if c.name == "equity_ratio").passed is False


def test_growth_gate_op_growth_from_loss_is_none(params):
    f = make_fundamentals()
    rows = list(f.annual)
    rows[-1] = rows[-1].model_copy(update={"operating_profit": -1e8})
    g = growth_gate(f.model_copy(update={"annual": rows}), params.growth)
    assert next(c for c in g.checks if c.name == "op_forecast_growth").passed is None


# ---------------------------------------------------------------- bước 3
def test_kiyohara_net_cash_formula():
    bs = BalanceSheet(period_end=D, current_assets=100.0, investment_securities=50.0,
                      total_liabilities=80.0, source=SRC, as_of=D)
    assert kiyohara_net_cash(bs, 0.7) == pytest.approx(100 + 35 - 80)


@pytest.mark.parametrize("field", ["current_assets", "investment_securities", "total_liabilities"])
def test_net_cash_missing_component_is_none(field):
    bs = BalanceSheet(period_end=D, current_assets=100.0, investment_securities=50.0,
                      total_liabilities=80.0, source=SRC, as_of=D)
    assert kiyohara_net_cash(bs.model_copy(update={field: None}), 0.7) is None


def test_peg_rules():
    assert peg(20.0, 0.25, 0.5, 4) == 0.8
    assert peg(20.0, 0.0, 0.5, 4) is None
    assert peg(20.0, -0.1, 0.5, 4) is None
    assert peg(20.0, 1.0, 0.5, 4) == 0.4      # cap 50%
    assert peg(None, 0.2, 0.5, 4) is None
    assert peg(-5.0, 0.2, 0.5, 4) is None


def test_valuation_end_to_end(params, fundamentals):
    v = valuation(fundamentals, PRICE, _mcap(fundamentals), params.valuation)
    assert v.per_forecast == round(2000 / 105, 4)
    assert v.eps_growth == 0.25
    assert v.peg == round((2000 / 105) / 25, 4)
    assert v.net_cash == pytest.approx(120e8 + 7e8 - 60e8)
    assert v.net_cash_ratio == round(67e8 / 190e8, 4)
    assert v.sources


def test_valuation_without_forecast_is_none(params):
    f = make_fundamentals(forecast=None)
    v = valuation(f, PRICE, _mcap(f), params.valuation)
    assert v.peg is None and v.per_forecast is None and v.eps_growth is None


# ---------------------------------------------------------------- adapters
def test_kiyohara_snapshot_adapter(tmp_path):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps({
        "fetchedAt": "2026-09-29T08:57:09.506Z", "sourceId": "kabutan",
        "snapshots": [
            {"code": "1332", "price": 1117, "per": 11.7, "perBasis": "予想",
             "updatedAt": "2026-09-29T15:30+09:00", "source": "kabutan"},
            {"code": "6861", "price": 60000, "per": None, "perBasis": "予想",
             "updatedAt": "2026-09-29T15:30+09:00", "source": "kabutan"},
        ]}), encoding="utf-8")
    s = KiyoharaSnapshotSource(p)
    snap = s.snapshot("1332")
    assert snap.close.value == 1117 and snap.close.as_of == date(2026, 9, 29)
    assert snap.per_forecast.value == 11.7
    assert s.snapshot("6861").per_forecast.value is None
    assert s.snapshot("0000") is None
    assert s.codes() == ["1332", "6861"]


def test_kiyohara_snapshot_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        KiyoharaSnapshotSource(tmp_path / "nope.json").snapshot("1332")


def test_json_fundamentals_roundtrip_idempotent(tmp_path, fundamentals):
    s = JsonFundamentalsSource("edinet", base=tmp_path)
    s.write(fundamentals)
    s.write(fundamentals)
    assert s.codes() == ["9999"]
    assert s.get("9999") == fundamentals
    assert s.get("0000") is None
    assert (tmp_path / "edinet" / "9999.json").exists()


def test_annual_result_requires_source():
    with pytest.raises(ValidationError):
        AnnualResult(fiscal_period="2026.03", as_of=D)  # thiếu source


def test_rnd_returns_python_float_for_numpy():
    import numpy as np

    v = rnd(np.float64(1.999), 4)
    assert type(v) is float
    assert ge(np.float64(1.999), 2.0, 4) is False   # `is False` phải đúng, không phải np.False_
