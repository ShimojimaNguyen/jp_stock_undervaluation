"""Nguồn L0: 株探 /stock/finance (HTML THẬT + một fixture dựng tay), JPX universe, pipeline CLI."""
import json
from datetime import date
from pathlib import Path

import pytest

from src.contracts import Market, PriceSnapshot, Quality, Sourced
from src.data.jpx_universe import parse_rows, segment_of
from src.data.kabutan_finance import (
    KabutanPriceSource,
    LayoutChanged,
    market_cap_jpy,
    num,
    parse_finance_html,
)
from src.pipeline import PriceChain
from src.screen.growth import growth_gate
from src.screen.valuation import eps_forecast_growth

FIX = Path(__file__).parent / "fixtures" / "kabutan"
D = date(2026, 9, 29)


def _page(code):
    return (FIX / f"kabutan-{code}.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- tiện ích
def test_num_never_zero_for_blank():
    assert num("1,234.5") == 1234.5 and num("+6.5") == 6.5 and num("-9.7") == -9.7
    for blank in ("－", "-", "", None, "abc"):
        assert num(blank) is None


def test_market_cap_units():
    assert market_cap_jpy("42兆555億円") == 42e12 + 555e8
    assert market_cap_jpy("200億円") == 200e8
    assert market_cap_jpy("－") is None


# ---------------------------------------------------------------- HTML thật
def test_toyota_real_page():
    f, s = parse_finance_html(_page("7203"), "7203")
    assert f.name == "トヨタ自動車" and f.market is Market.PRIME
    assert s.close.value == 2881.5 and s.close.as_of == D        # <time> sát trước 前日比
    assert f.market_cap_reported.value == 42e12 + 555e8
    assert f.market_cap_reported.quality is Quality.PROXY
    assert [a.fiscal_period for a in f.annual] == ["2023.03", "2024.03", "2025.03", "2026.03"]
    last = f.annual[-1]
    assert last.revenue == 50_684_952 * 1e6 and last.operating_profit == 3_766_216 * 1e6
    assert last.eps == 295.3 and last.announced == date(2026, 5, 8)
    assert f.forecast.fiscal_period == "2027.03" and f.forecast.eps == 275.1
    # đối chiếu đường tính thứ hai (pillar §8): giá / EPS dự phóng ≈ PER trang in (10,5)
    assert abs(s.close.value / f.forecast.eps - 10.5) / 10.5 < 0.03


def test_nichirei_irregular_forecast_blocks_growth(params):
    f, _ = parse_finance_html(_page("2871"), "2871")
    assert f.forecast.irregular is True and f.forecast.fiscal_period == "2026.12"
    assert eps_forecast_growth(f) is None                 # 9 tháng vs 12 tháng: không so
    g = growth_gate(f, params.growth)
    assert next(c for c in g.checks if c.name == "op_forecast_growth").passed is None


def test_keyence_no_forecast_is_null():
    f, _ = parse_finance_html(_page("6861"), "6861")
    assert f.forecast.revenue is None and f.forecast.operating_profit is None
    assert f.forecast.eps is None


def test_nok_empty_header_is_null_not_zero():
    f, s = parse_finance_html(_page("7240"), "7240", fetched=D)
    assert f.market is None and s.close.value is None
    assert f.market_cap_reported.value is None
    assert len(f.annual) == 4 and f.annual[0].as_of == D   # kỳ = ngày tải


def test_real_pages_have_no_bs_cf_tables():
    f, _ = parse_finance_html(_page("7203"), "7203")
    assert f.balance_sheet is None and all(a.cfo is None for a in f.annual)


def test_layout_changed_is_distinct_error():
    with pytest.raises(LayoutChanged):
        parse_finance_html("<html><body>maintenance</body></html>", "7203", fetched=D)


# ---------------------------------------------------------------- fixture dựng tay
def test_synthetic_full_page_passes_growth(params):
    f, s = parse_finance_html(_page("synthetic-bs-cf"), "9999")
    assert f.market is Market.STANDARD and s.close.value == 2000
    assert f.annual[-1].cfo == 800e6 and f.annual[-2].cfo == 700e6
    assert f.balance_sheet.total_assets == 15_000e6 and f.balance_sheet.equity == 9_000e6
    assert f.balance_sheet.period_end == date(2026, 3, 31)
    g = growth_gate(f, params.growth)
    assert g.passed, [c for c in g.checks if c.passed is not True]


# ---------------------------------------------------------------- giá
def test_price_chain_falls_back(tmp_path):
    d = tmp_path / "prices" / "kabutan"
    d.mkdir(parents=True)
    (d / "9999.json").write_text(PriceSnapshot(
        code="9999", close=Sourced.of(2000.0, D, "kabutan")).model_dump_json())

    class Missing:
        name = "kiyohara"

        def snapshot(self, code):
            raise FileNotFoundError

    chain = PriceChain([Missing(), KabutanPriceSource(tmp_path)])
    assert chain.snapshot("9999").close.value == 2000.0
    assert chain.snapshot("0000") is None


# ---------------------------------------------------------------- JPX
def _row(code, seg, d=20260831.0):
    return {"日付": d, "コード": code, "銘柄名": "x", "市場・商品区分": seg}


def test_segment_of():
    assert segment_of("プライム（内国株式）") is Market.PRIME
    assert segment_of("グロース（内国株式）") is Market.GROWTH
    assert segment_of("ETF・ETN") is None
    assert segment_of("プライム（外国株式）") is None
    assert segment_of("PRO Market") is None


def test_parse_rows():
    rows = [_row("7203", "プライム（内国株式）"), _row("285A", "スタンダード（内国株式）"),
            _row("1305", "ETF・ETN"), _row(None, "グロース（内国株式）")]
    codes, snap, skipped = parse_rows(rows)
    assert [c["code"] for c in codes] == ["285A", "7203"]
    assert snap == date(2026, 8, 31) and skipped == 2


def test_parse_rows_missing_column_stops():
    with pytest.raises(ValueError):
        parse_rows([{"日付": 1, "コード": "7203", "銘柄名": "x"}])


# ---------------------------------------------------------------- pipeline CLI
def _setup(tmp_path, n_have, n_total):
    from src.data.adapters import JsonFundamentalsSource
    from tests.conftest import make_fundamentals

    fs = JsonFundamentalsSource("kabutan", base=tmp_path / "fundamentals")
    codes = [f"{9000 + i}" for i in range(n_total)]
    for c in codes[:n_have]:
        fs.write(make_fundamentals(code=c))
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({"codes": [{"code": c, "name": "x", "market": "STANDARD"}
                                         for c in codes]}))
    return uni


def _run(tmp_path, uni):
    from src.pipeline import main

    out = tmp_path / "out" / "tenbagger-candidates.json"
    rc = main(["--fundamentals-source", "kabutan", "--universe", str(uni),
               "--data-dir", str(tmp_path), "--snapshot", str(tmp_path / "none.json"),
               "--tdnet-dir", str(tmp_path / "tdnet"), "--as-of", "2026-10-02",
               "--out", str(out)])
    return rc, out


def test_pipeline_refuses_low_coverage(tmp_path):
    rc, out = _run(tmp_path, _setup(tmp_path, 1, 3))
    assert rc == 0 and not out.exists()
    assert out.with_suffix(".sample.json").exists()


def test_pipeline_writes_when_covered(tmp_path):
    rc, out = _run(tmp_path, _setup(tmp_path, 3, 3))
    assert rc == 0 and out.exists()
    exp = json.loads(out.read_text())
    assert exp["universe_count"] == 3
    assert any("phủ 100.0%" in n for n in exp["notes"])
