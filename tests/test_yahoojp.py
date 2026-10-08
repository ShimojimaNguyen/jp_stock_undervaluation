"""会社予想 từ Yahoo JP /performance — fixture là đoạn JSON THẬT của 1870 (2026-10-07)."""
import json
from datetime import date
from pathlib import Path

from src.catalyst.tdnet import effective_date
from src.contracts import AnnualResult, CatalystType, Fundamentals
from src.data.yahoojp_forecast import (
    YahooJPForecastStore,
    parse_performance,
    revision_events,
    to_forecast,
)

PAGE = (Path(__file__).parent / "fixtures" / "yahoojp" / "performance-1870.html").read_text(
    encoding="utf-8")
D = date(2026, 10, 7)


def _f(**kw):
    last = AnnualResult(fiscal_period="2026.03", revenue=140e9, operating_profit=8.5e9,
                        net_income=8.0e9, eps=200.0, source="y", as_of=D)
    return Fundamentals(code="1870", annual=[last], **kw)


def test_parse_company_forecast_not_analyst():
    raw, revs = parse_performance(PAGE)
    assert raw["operatingIncome"] == 9_500_000_000          # 会社予想, yên
    assert raw["netSales"] == 150_000_000_000                # KHÔNG phải 155000 (analyst, 百万円)
    assert raw["updatedDate"] == "2026-08-07"
    assert [r["quarterEndDate"] for r in revs] == ["2026-06-30", "2026-03-31"]


def test_to_forecast_derives_eps_consistently():
    raw, _ = parse_performance(PAGE)
    fc = to_forecast(raw, _f(), D)
    assert fc.fiscal_period == "2027.03" and not fc.irregular
    assert fc.operating_profit == 9.5e9 and fc.announced == date(2026, 8, 7)
    # EPS_fc = 9,3億 × (200 / 80億) → tăng trưởng EPS = tăng trưởng 純利益 = +16,25%
    assert abs(fc.eps - 9.3e9 * 200 / 8.0e9) < 1e-9
    assert "EPS suy" in fc.source


def test_to_forecast_no_eps_when_last_loss():
    raw, _ = parse_performance(PAGE)
    f = _f()
    f.annual[0] = f.annual[0].model_copy(update={"net_income": -1e9})
    assert to_forecast(raw, f, D).eps is None


def test_irregular_when_not_12_months():
    raw, _ = parse_performance(PAGE)
    f = _f()
    f.annual[0] = f.annual[0].model_copy(update={"fiscal_period": "2026.06"})
    assert to_forecast(raw, f, D).irregular is True


def test_revision_event_upward(params):
    raw, revs = parse_performance(PAGE)
    ev = revision_events("1870", revs, date(2026, 8, 7),
                         lambda dt: effective_date(dt, "15:00", set()), params.catalyst.strength)
    assert len(ev) == 1 and ev[0].type is CatalystType.UPWARD_REVISION
    assert ev[0].effective_date == date(2026, 8, 10)   # thứ Sáu, giờ không rõ → phiên kế tiếp
    assert ev[0].method == "code"


def test_no_revision_without_change(params):
    revs = [{"yearEndDate": "2027-03-31", "operatingIncome": 1},
            {"yearEndDate": "2027-03-31", "operatingIncome": 1}]
    assert revision_events("x", revs, date(2026, 8, 7), lambda dt: dt.date(),
                           params.catalyst.strength) == []


def test_missing_block_is_none():
    assert parse_performance("<html>no data</html>") == (None, [])


def test_store_roundtrip(tmp_path):
    raw, revs = parse_performance(PAGE)
    s = YahooJPForecastStore(tmp_path)
    s.put("1870", raw, revs, D)
    assert s.get("1870")["forecast"]["operatingIncome"] == 9_500_000_000
    assert s.get("0000") is None


def test_pipeline_merges_forecast(tmp_path, params):
    """yfinance (thiếu dự báo) + Yahoo JP 会社予想 → cổng bước 2 có đủ dữ liệu."""
    from src.data.adapters import JsonFundamentalsSource
    from src.pipeline import main
    from tests.conftest import make_fundamentals

    f = make_fundamentals(code="9000", forecast=None)
    f.annual[-1] = f.annual[-1].model_copy(update={"net_income": 7e8})
    JsonFundamentalsSource("yfinance", base=tmp_path / "fundamentals").write(f)
    raw = {"yearEndDate": "2027-03-31", "netSales": 175e8, "operatingIncome": 17.5e8,
           "netProfit": 8.75e8, "updatedDate": "2026-08-07"}
    YahooJPForecastStore(tmp_path).put("9000", raw, [], D)
    uni = tmp_path / "u.json"
    uni.write_text(json.dumps({"codes": [{"code": "9000", "name": "x", "market": "STANDARD"}]}))
    out = tmp_path / "o.json"
    assert main(["--fundamentals-source", "yfinance", "--universe", str(uni), "--data-dir",
                 str(tmp_path), "--tdnet-dir", str(tmp_path / "t"), "--as-of", "2026-10-07",
                 "--min-coverage", "0", "--out", str(out)]) == 0
    c = json.loads(out.read_text())["candidates"][0]
    checks = {x["name"]: x["passed"] for x in c["scorecard"]["growth"]["checks"]}
    assert checks["op_forecast_growth"] is True and checks["opm_improving"] is True
    assert c["scorecard"]["valuation"]["eps_growth"] == 0.25


def test_parse_actuals_real_6339():
    from src.data.yahoojp_forecast import parse_actuals, to_annuals

    page = (Path(__file__).parent / "fixtures" / "yahoojp" / "performance-6339.html").read_text(
        encoding="utf-8")
    rows = parse_actuals(page)
    a = to_annuals(rows, D)
    assert [x.fiscal_period for x in a] == ["2025.03", "2026.03"]
    last = a[-1]
    assert last.operating_profit == 3_831_000_000 and last.net_income == -16_262_000_000
    assert last.eps == -309.66 and last.cfo == 8_843_000_000
    assert last.announced == date(2026, 5, 13)
    assert parse_actuals(PAGE) == []          # trang 1870 trích không có khối performance
