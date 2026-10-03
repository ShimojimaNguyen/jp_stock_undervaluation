import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.catalyst.tdnet import (
    Disclosure,
    classify,
    classify_title,
    effective_date,
    event_from_jev_choice,
    fetch_day,
    parse_list_html,
    prime_eligibility,
    read_day,
    upgrade_likelihood,
    write_day,
)
from src.contracts import CatalystStrength, CatalystType, EntrySignal, QuarterResult
from src.signals.gainers import completed_sessions, evaluate, parse_chart_json, rsi_wilder

FIX = Path(__file__).parent / "fixtures"
DAY = date(2026, 10, 2)  # thứ Sáu
BASE = "https://www.release.tdnet.info/inbs/"


@pytest.fixture
def disclosures():
    return parse_list_html((FIX / "tdnet_list_sample.html").read_text(encoding="utf-8"), DAY, BASE)


# ================================================================ TDnet
def test_parse_list(disclosures):
    assert [d.code for d in disclosures] == ["9991", "9992", "9993", "285A"]  # dòng hỏng bị bỏ
    d = disclosures[0]
    assert d.disclosed_at == datetime(2026, 10, 2, 9, 0)
    assert d.url == BASE + "140120261002000001.pdf"
    assert d.exchange == "東"


def test_classify_title_rules():
    assert classify_title("通期業績予想の上方修正及び増配に関するお知らせ") == [
        CatalystType.UPWARD_REVISION, CatalystType.DIVIDEND_INCREASE]
    assert classify_title("自己株式の取得状況に関するお知らせ") == [CatalystType.BUYBACK]
    assert classify_title("当社株式に対する公開買付けの開始") == [CatalystType.TENDER_OFFER]
    assert classify_title("スタンダード市場からプライム市場への市場区分の変更") == [CatalystType.MARKET_CHANGE]
    assert classify_title("特別損失の計上に関するお知らせ") == [CatalystType.EXTRAORDINARY_LOSS]
    assert classify_title("業績予想の修正に関するお知らせ") == [CatalystType.FORECAST_REVISION]
    assert classify_title("防衛省向け大型案件の受注に関するお知らせ") == []


@pytest.mark.parametrize("hhmm,expected", [
    ((9, 0), date(2026, 10, 2)),
    ((14, 59), date(2026, 10, 2)),
    ((15, 0), date(2026, 10, 5)),     # cutoff đúng 15:00 → phiên kế tiếp (thứ Hai)
    ((16, 30), date(2026, 10, 5)),
])
def test_effective_date_cutoff(hhmm, expected):
    assert effective_date(datetime(2026, 10, 2, *hhmm), "15:00", set()) == expected


def test_effective_date_weekend_and_holiday():
    assert effective_date(datetime(2026, 10, 3, 10, 0), "15:00", set()) == date(2026, 10, 5)
    hol = {date(2026, 10, 12)}
    assert effective_date(datetime(2026, 10, 9, 15, 30), "15:00", hol) == date(2026, 10, 13)


def test_classify_events_and_unmatched(params, disclosures):
    events, unmatched = classify(disclosures, params.catalyst)
    types = {(e.code, e.type) for e in events}
    assert ("9991", CatalystType.UPWARD_REVISION) in types
    assert ("9991", CatalystType.DIVIDEND_INCREASE) in types
    buy = next(e for e in events if e.code == "9992")
    assert buy.effective_date == date(2026, 10, 5) and buy.method == "rule"
    assert [d.code for d in unmatched] == ["9993"]   # chỉ tiêu đề không khớp mới sang Jev
    up = next(e for e in events if e.type is CatalystType.UPWARD_REVISION)
    assert up.strength is CatalystStrength.HIGH


def test_event_from_jev_choice(params, disclosures):
    d = disclosures[2]
    assert event_from_jev_choice(d, "none_of_these", params.catalyst) is None
    assert event_from_jev_choice(d, None, params.catalyst) is None
    assert event_from_jev_choice(d, "not_a_type", params.catalyst) is None
    e = event_from_jev_choice(d, "mid_term_plan", params.catalyst)
    assert e.method == "jev" and e.effective_date == date(2026, 10, 5)


def test_write_read_day_idempotent(tmp_path, disclosures):
    p1 = write_day(DAY, disclosures, tmp_path)
    write_day(DAY, disclosures, tmp_path)
    assert read_day(p1) == disclosures
    assert len(list(tmp_path.iterdir())) == 1


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text
        self.encoding, self.apparent_encoding = None, "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Sess:
    def __init__(self, robots):
        self.robots, self.urls = robots, []

    def get(self, url, headers=None, timeout=None, params=None):
        assert headers and headers.get("User-Agent")
        self.urls.append(url)
        if url.endswith("robots.txt"):
            return self.robots
        if "I_list_001" in url:
            return _Resp(200, (FIX / "tdnet_list_sample.html").read_text(encoding="utf-8"))
        return _Resp(404)


def test_fetch_day_refuses_when_robots_disallow(params):
    s = _Sess(_Resp(200, "User-agent: *\nDisallow: /inbs/\n"))
    with pytest.raises(PermissionError):
        fetch_day(DAY, params.catalyst, session=s)
    assert len(s.urls) == 1


def test_fetch_day_refuses_when_robots_unreadable(params):
    with pytest.raises(PermissionError):
        fetch_day(DAY, params.catalyst, session=_Sess(_Resp(503)))


def test_fetch_day_paginates_until_404(params, monkeypatch):
    monkeypatch.setattr("src.catalyst.tdnet.time.sleep", lambda s: None)
    s = _Sess(_Resp(404))
    rows = fetch_day(DAY, params.catalyst, session=s)
    assert len(rows) == 4
    assert s.urls[-1].endswith("I_list_002_20261002.html")


# ---------------------------------------------------------------- code-catalyst
def _q(fp, q, cum, fc=None):
    return QuarterResult(fiscal_period=fp, quarter=q, cumulative_operating_profit=cum,
                         full_year_op_forecast=fc, source="fixture", as_of=DAY)


def test_upgrade_likelihood(params):
    hist = [_q("2023.03", 2, 40), _q("2024.03", 2, 45), _q("2025.03", 2, 50)]
    annual = {"2023.03": 100.0, "2024.03": 100.0, "2025.03": 100.0}  # TB lịch sử 45%
    ok, det = upgrade_likelihood(hist + [_q("2026.03", 2, 60, 120)], annual, params.catalyst)
    assert det["history_avg"] == 0.45 and det["progress"] == 0.5
    assert ok is True                                  # 50% − 45% = 5 điểm = margin
    ok, _ = upgrade_likelihood(hist + [_q("2026.03", 2, 55, 120)], annual, params.catalyst)
    assert ok is False


def test_upgrade_likelihood_needs_history_and_no_lookahead(params):
    cur = _q("2025.03", 2, 60, 120)
    future = _q("2026.03", 2, 99)   # năm SAU năm hiện tại — không được dùng
    ok, det = upgrade_likelihood([_q("2024.03", 2, 45), future, cur],
                                 {"2024.03": 100.0, "2026.03": 100.0}, params.catalyst)
    assert ok is None and det["history_n"] == 1
    assert upgrade_likelihood([], {}, params.catalyst)[0] is None


def test_prime_eligibility(params):
    pp = params.catalyst.prime
    good = dict(shareholders=2000, tradable_units=50000, tradable_market_cap=2e10,
                tradable_ratio=0.5, market_cap=4e10, net_assets=1e10, profit_2y_sum=3e9)
    assert prime_eligibility(pp, **good)[0] is True
    assert prime_eligibility(pp, **{**good, "tradable_ratio": 0.3})[0] is False
    assert prime_eligibility(pp, **{**good, "shareholders": None})[0] is None


# ================================================================ gainers
def test_parse_chart_json_drops_null_sessions():
    df = parse_chart_json(json.loads((FIX / "chart_v8_sample.json").read_text()))
    assert len(df) == 3
    assert df["date"].is_monotonic_increasing
    assert df["close"].iloc[-1] == 105.06


def test_parse_chart_json_error():
    with pytest.raises(ValueError):
        parse_chart_json({"chart": {"result": None, "error": {"code": "Not Found"}}})


def _frame(closes, volumes=None, highs=None, lows=None):
    n = len(closes)
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=n).date,
        "open": c,
        "high": c * 1.01 if highs is None else np.asarray(highs, dtype=float),
        "low": c * 0.99 if lows is None else np.asarray(lows, dtype=float),
        "close": c,
        "volume": np.full(n, 1000.0) if volumes is None else np.asarray(volumes, dtype=float),
    })


def test_gainer_rounding_and_volume(params):
    p = params.signals
    closes = [100.0] * 300 + [103.0]
    vols = [1000.0] * 300 + [2000.0]
    r = evaluate("9999", _frame(closes, vols), p, None)
    assert r.change_1d == 0.03 and r.is_gainer is True
    r = evaluate("9999", _frame([100.0] * 300 + [102.99], vols), p, None)
    assert r.is_gainer is False
    r = evaluate("9999", _frame(closes, [1000.0] * 300 + [1999.0]), p, None)
    assert r.is_gainer is False


def test_volume_avg_excludes_today(params):
    vols = [1000.0] * 300 + [2000.0]
    r = evaluate("9999", _frame([100.0] * 300 + [104.0], vols), params.signals, None)
    assert r.volume_ratio == 2.0   # TB 20 phiên TRƯỚC = 1000, không gồm phiên hôm nay


def test_breakout(params):
    closes = list(np.linspace(80, 100, 300)) + [110.0]
    vols = [1000.0] * 300 + [5000.0]
    r = evaluate("9999", _frame(closes, vols), params.signals, None)
    assert r.is_breakout is True and r.signal is EntrySignal.BREAKOUT


def test_breakout_needs_52w_history(params):
    r = evaluate("9999", _frame([100.0] * 50 + [110.0], [1000.0] * 50 + [5000.0]),
                 params.signals, None)
    assert r.is_gainer is True and r.high_52w is None and r.is_breakout is None
    assert r.signal is EntrySignal.NONE


def _bottom_frame():
    # đỉnh ~206 → rơi về 95 (−50%) với biên độ ±3%/phiên, rồi 10 phiên biên độ
    # hẹp ±0,3% hồi dần lên 108: RSI chạm ≤30 khi rơi, rồi vượt 30 và đang tăng.
    up = list(np.linspace(150, 200, 200))
    down = list(np.linspace(200, 95, 50))
    narrow = list(np.linspace(96, 108, 10))
    closes = up + down + narrow
    highs = [c * 1.03 for c in up + down] + [c * 1.003 for c in narrow]
    lows = [c * 0.97 for c in up + down] + [c * 0.997 for c in narrow]
    return _frame(closes, highs=highs, lows=lows)


def test_bottom_signal(params):
    df = _bottom_frame()
    rsi = rsi_wilder(df["close"], 14)
    assert rsi.iloc[-21:-1].min() <= 30
    r = evaluate("9999", df, params.signals, True)
    assert r.drawdown_52w <= -0.40 and r.range_ratio <= 0.5
    assert r.is_bottom is True and r.signal is EntrySignal.BOTTOM


def test_bottom_requires_growth_gate(params):
    df = _bottom_frame()
    assert evaluate("9999", df, params.signals, False).signal is EntrySignal.NONE
    r = evaluate("9999", df, params.signals, None)
    assert r.is_bottom is None and r.signal is EntrySignal.NONE


def test_completed_sessions_drops_live_candle():
    df = _frame([100.0, 101.0, 102.0])
    last = df["date"].iloc[-1]
    assert len(completed_sessions(df, last, market_closed=False)) == 2
    assert len(completed_sessions(df, last, market_closed=True)) == 3


def test_disclosure_json_roundtrip(disclosures):
    d = disclosures[0]
    assert Disclosure.from_json(d.to_json()) == d
