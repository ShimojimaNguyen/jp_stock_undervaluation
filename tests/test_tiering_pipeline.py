import json
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from src.contracts import (
    CandidateExport,
    CatalystEvent,
    CatalystStrength,
    CatalystType,
    Holder,
    PriceSnapshot,
    QuarterResult,
    Sourced,
    ThesisStatus,
    Tier,
)
from src.jev.client import JudgmentCache, to_judgment
from src.jev.registry import load_registry
from src.pipeline import (
    build_export,
    evaluate_code,
    judgments_for,
    load_catalysts,
    write_export,
)
from src.screen.growth import growth_gate
from src.tracking.thesis import thesis_check
from tests.conftest import SRC, D, make_fundamentals

AS_OF = date(2026, 10, 2)


def _cat(t, s, eff, code="9999"):
    return CatalystEvent(code=code, type=t, strength=s, effective_date=eff, method="rule",
                         source=SRC)


def _ohlcv(n=300, close=2000.0, vol=50_000.0):
    return pd.DataFrame({
        "date": pd.bdate_range(end="2026-10-02", periods=n).date,
        "open": np.full(n, close), "high": np.full(n, close * 1.01),
        "low": np.full(n, close * 0.99), "close": np.full(n, close), "volume": np.full(n, vol),
    })


def _judgments(params, noul=0.9):
    reg = load_registry()
    return {q: to_judgment("9999", reg[q], {"noul": noul}, [], params.jev)
            for q in ["niche_share", "theme_defense", "recurring_revenue"]}


def _snap(px=2000.0):
    return PriceSnapshot(code="9999", close=Sourced.of(px, D, "kiyohara"))


HOLDERS = [Holder(name="創業者", ratio=0.3, kind="founder_entity")]


# ---------------------------------------------------------------- tầng
def test_tier_a_with_10x_label(params):
    f = make_fundamentals(holders=HOLDERS)
    cats = [_cat(CatalystType.UPWARD_REVISION, CatalystStrength.HIGH, date(2026, 9, 1))]
    c = evaluate_code("9999", f, _snap(), _ohlcv(), _judgments(params), cats, AS_OF, params)
    assert c.tier is Tier.A and c.labels == ["10x"], c.tier_reasons
    assert c.scorecard.valuation.peg <= 1 and c.scorecard.valuation.net_cash_ratio >= 0.3
    assert c.entry_signal is not None and c.thesis is not None


def test_entry_signal_does_not_change_tier(params):
    f = make_fundamentals(holders=HOLDERS)
    cats = [_cat(CatalystType.UPWARD_REVISION, CatalystStrength.HIGH, date(2026, 9, 1))]
    a = evaluate_code("9999", f, _snap(), _ohlcv(), _judgments(params), cats, AS_OF, params)
    b = evaluate_code("9999", f, _snap(), None, _judgments(params), cats, AS_OF, params)
    # không OHLCV → không ADTV → không qua bước 1 → không còn A; nhưng không phải do signal
    assert a.tier is Tier.A and b.entry_signal is None and b.tier is not Tier.A


def test_future_catalyst_is_ignored(params):
    f = make_fundamentals(holders=HOLDERS)
    cats = [_cat(CatalystType.UPWARD_REVISION, CatalystStrength.HIGH, date(2026, 10, 5))]
    c = evaluate_code("9999", f, _snap(), _ohlcv(), _judgments(params), cats, AS_OF, params)
    assert c.tier is not Tier.A          # catalyst có hiệu lực SAU as_of → không tính


def test_tier_b_and_c(params):
    f = make_fundamentals()
    # giá cao hơn → PEG ≈ 1,33 (≤1,5), net cash ratio thấp; checklist 3 (Jev) → B
    c = evaluate_code("9999", f, _snap(3500.0), _ohlcv(close=3500.0), _judgments(params), [],
                      AS_OF, params)
    assert c.tier is Tier.B, c.tier_reasons
    # PEG > 1,5 → C
    c = evaluate_code("9999", f, _snap(5000.0), _ohlcv(close=5000.0), _judgments(params), [],
                      AS_OF, params)
    assert c.tier is Tier.C


def test_tier_none_on_missing_fundamentals(params):
    c = evaluate_code("9999", None, _snap(), _ohlcv(), {}, [], AS_OF, params)
    assert c.tier is Tier.NONE and "growth:insufficient_data" in c.tier_reasons
    assert c.scorecard.valuation.peg is None and c.scorecard.valuation.net_cash is None


def test_negative_catalyst_does_not_count(params):
    f = make_fundamentals(holders=HOLDERS)
    cats = [_cat(CatalystType.DOWNWARD_REVISION, CatalystStrength.NEGATIVE, date(2026, 9, 1))]
    c = evaluate_code("9999", f, _snap(), _ohlcv(), _judgments(params), cats, AS_OF, params)
    assert c.tier is not Tier.A
    assert c.thesis.status is ThesisStatus.BROKEN


# ---------------------------------------------------------------- thesis
def _q(fp, q, yoy, opm=None, opm_prev=None):
    return QuarterResult(fiscal_period=fp, quarter=q, revenue_yoy=yoy, opm=opm,
                         opm_prev_year=opm_prev, source=SRC, as_of=D)


def test_thesis_states(params):
    g = growth_gate(make_fundamentals(), params.growth)
    tp = params.thesis
    ok = thesis_check("9999", AS_OF, [_q("2027.03", 1, 0.20), _q("2027.03", 2, 0.19, 0.11, 0.10)],
                      [], g, tp)
    assert ok.status is ThesisStatus.INTACT and not ok.insufficient_data
    slow = thesis_check("9999", AS_OF, [_q("2027.03", 1, 0.25), _q("2027.03", 2, 0.15, 0.11, 0.10)],
                        [], g, tp)
    assert slow.status is ThesisStatus.WEAKENING
    neg = thesis_check("9999", AS_OF, [_q("2027.03", 2, -0.01, 0.11, 0.10)], [], g, tp)
    assert neg.status is ThesisStatus.BROKEN
    opm = thesis_check("9999", AS_OF, [_q("2027.03", 2, 0.2, 0.08, 0.10)], [], g, tp)
    assert opm.status is ThesisStatus.WEAKENING


def test_thesis_catalyst_lost(params):
    g = growth_gate(make_fundamentals(), params.growth)
    old = _cat(CatalystType.BUYBACK, CatalystStrength.MEDIUM, date(2026, 1, 15))
    t = thesis_check("9999", AS_OF, [_q("2027.03", 2, 0.2, 0.11, 0.10)], [old], g, params.thesis)
    assert t.status is ThesisStatus.WEAKENING and "catalyst_lost" in t.reasons


def test_thesis_never_reads_rsi(params):
    import inspect

    import src.tracking.thesis as m

    assert "rsi" not in inspect.getsource(m.thesis_check).lower()
    assert params.thesis.rsi_high_is_sell_signal_for_10x is False


# ---------------------------------------------------------------- catalyst/jev wiring
def test_load_catalysts_rule_and_jev_cache(tmp_path, params):
    from src.catalyst.tdnet import Disclosure, write_day

    rows = [
        Disclosure(datetime(2026, 9, 1, 15, 30), "9999", "テスト", "自己株式取得に関するお知らせ",
                   None, "東"),
        Disclosure(datetime(2026, 9, 2, 10, 0), "9999", "テスト", "新中期ビジョン策定のお知らせ",
                   None, "東"),
        Disclosure(datetime(2026, 10, 9, 10, 0), "9999", "テスト", "株式分割に関するお知らせ",
                   None, "東"),
    ]
    tdir = tmp_path / "tdnet"
    write_day(date(2026, 9, 1), rows[:1], tdir)
    write_day(date(2026, 9, 2), rows[1:2], tdir)
    write_day(date(2026, 10, 9), rows[2:], tdir)       # sau as_of → bỏ
    reg = load_registry()
    cache = JudgmentCache(tmp_path / "c.jsonl")
    by, pending = load_catalysts(tdir, AS_OF, params, reg, cache)
    assert [e.type for e in by["9999"]] == [CatalystType.BUYBACK] and pending == 1
    assert by["9999"][0].effective_date == date(2026, 9, 2)

    from src.pipeline import evidence_key, title_evidence

    ev = title_evidence(rows[1])
    j = to_judgment("9999", reg["tdnet_title_kind"], {"choice": "mid_term_plan", "confidence": 0.9},
                    ev, params.jev, evidence_key("9999", ev))
    cache.put(j)
    by, pending = load_catalysts(tdir, AS_OF, params, reg, cache)
    assert pending == 0
    assert {e.type for e in by["9999"]} == {CatalystType.BUYBACK, CatalystType.MID_TERM_PLAN}


def test_judgments_for_matches_evidence(tmp_path, params):
    reg = load_registry()
    cache = JudgmentCache(tmp_path / "c.jsonl")
    cache.put(to_judgment("9999", reg["niche_share"], {"noul": 0.9}, [], params.jev, "name:9999"))
    got = judgments_for("9999", [], reg, cache, ["niche_share", "recurring_revenue"])
    assert list(got) == ["niche_share"]


# ---------------------------------------------------------------- export
def test_export_schema_and_sample_path(tmp_path, params):
    f = make_fundamentals(holders=HOLDERS)
    cands = [
        evaluate_code("9999", f, _snap(), _ohlcv(), _judgments(params), [], AS_OF, params),
        evaluate_code("9998", None, None, None, {}, [], AS_OF, params),
    ]
    exp = build_export(cands, AS_OF, params, failures=[], notes=["test"])
    assert exp.universe_count == 2 and exp.counts["NONE"] == 1
    assert [c.code for c in exp.candidates] == ["9999"]         # NONE không xuất
    target = tmp_path / "tenbagger-candidates.json"
    p = write_export(exp, sample=True, path=target)
    assert p.name == "tenbagger-candidates.sample.json" and not target.exists()
    p = write_export(exp, sample=False, path=target)
    back = CandidateExport.model_validate(json.loads(p.read_text()))
    assert back.candidates[0].scorecard.valuation.peg == exp.candidates[0].scorecard.valuation.peg


@pytest.mark.parametrize("field", ["peg", "net_cash", "net_cash_ratio", "per_forecast"])
def test_export_missing_numbers_are_null_not_zero(params, field):
    c = evaluate_code("9998", None, None, None, {}, [], AS_OF, params)
    dumped = json.loads(c.model_dump_json())
    assert dumped["scorecard"]["valuation"][field] is None
