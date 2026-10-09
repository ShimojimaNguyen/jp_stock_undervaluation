from datetime import date

import pytest
from pydantic import ValidationError

from src.contracts import BacklogPoint, CatalystType, Evidence, Holder
from src.jev.client import (
    JevClient,
    JevItem,
    JevUnavailable,
    JudgmentCache,
    build_state,
    decide,
    judge_batch,
    to_judgment,
)
from src.jev.registry import Question, Registry, load_registry
from src.screen.checklist import backlog_is_record, build_checklist, insider_ownership

D = date(2026, 9, 29)


@pytest.fixture
def reg():
    return load_registry()


# ---------------------------------------------------------------- registry
def test_registry_loads_all_questions(reg, params):
    ids = {q.id for q in reg.all()}
    assert {"niche_share", "recurring_revenue", "record_backlog_text", "tdnet_title_kind"} <= ids
    for t in params.checklist.themes:
        assert f"theme_{t}" in ids, f"thiếu câu hỏi cho theme {t}"


def test_tdnet_choice_options_are_catalyst_types(reg):
    opts = set(reg["tdnet_title_kind"].criteria) - {"none_of_these"}
    assert opts <= {t.value for t in CatalystType}


def test_choice_without_escape_rejected():
    with pytest.raises(ValidationError):
        Question(id="x", version=1, type="choice", instructions="?", criteria={"a": "A", "b": "B"})


def test_duplicate_id_rejected():
    q = Question(id="x", version=1, type="noul", instructions="?",
                 criteria={"true": "t", "false": "f"})
    with pytest.raises(ValueError):
        Registry([q, q.model_copy(update={"version": 2})])


# ---------------------------------------------------------------- policy
def test_decide_noul_bands(reg, params):
    q, p = reg["niche_share"], params.jev
    assert decide(q, {"noul": 0.70}, p) is True
    assert decide(q, {"noul": 0.69999999999}, p) is True     # làm tròn trước so
    assert decide(q, {"noul": 0.5}, p) is None                # vùng giữa → im lặng
    assert decide(q, {"noul": 0.30}, p) is False
    assert decide(q, {}, p) is None and decide(q, None, p) is None


def test_decide_choice_confidence(reg, params):
    q, p = reg["tdnet_title_kind"], params.jev
    assert decide(q, {"choice": "buyback", "confidence": 0.9}, p) == "buyback"
    assert decide(q, {"choice": "buyback", "confidence": 0.2}, p) is None
    assert decide(q, {"choice": "none_of_these", "confidence": 0.95}, p) == "none_of_these"
    assert decide(q, {"choice": "made_up", "confidence": 0.99}, p) is None


# ---------------------------------------------------------------- client
class _R:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._p, self.text = status, payload, text

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _S:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append((url, data, headers))
        return self.resp


def test_client_requires_key(params, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JevUnavailable):
        JevClient(params.jev, session=_S(None))


def test_client_sends_user_agent_and_parses(reg, params):
    s = _S(_R(200, {"answers": {"niche_share": {"noul": 0.9}}}))
    c = JevClient(params.jev, api_key="k", session=s)
    a = c.ask({"ticker": "9999"}, [reg["niche_share"]])
    assert a == {"niche_share": {"noul": 0.9}}
    _, _, headers = s.calls[0]
    assert headers["User-Agent"] and headers["Authorization"] == "Bearer k"


def test_client_cloudflare_1010_is_explicit(reg, params):
    c = JevClient(params.jev, api_key="k", session=_S(_R(403, text="error code: 1010")))
    with pytest.raises(JevUnavailable, match="User-Agent"):
        c.ask({}, [reg["niche_share"]])


# ---------------------------------------------------------------- cache + batch
def test_batch_uses_cache_and_one_request_per_code(tmp_path, reg, params):
    ev = [Evidence(text="国内シェア7割", source="有報", kind="filing")]
    qs = [reg["niche_share"], reg["recurring_revenue"]]
    calls = []

    def ask(state, questions):
        calls.append([q.id for q in questions])
        return {q.id: {"noul": 0.9} for q in questions}

    cache = JudgmentCache(tmp_path / "c.jsonl")
    js, fails = judge_batch([JevItem("9999", {"ticker": "9999"}, ev, qs)], ask, cache, params.jev)
    assert len(js) == 2 and not fails and calls == [["niche_share", "recurring_revenue"]]
    assert all(j.value is True and j.evidence_label == "filing" for j in js)
    cache.save()

    cache2 = JudgmentCache(tmp_path / "c.jsonl")
    js2, _ = judge_batch([JevItem("9999", {}, ev, qs)], ask, cache2, params.jev)
    assert len(js2) == 2 and len(calls) == 1               # không gọi lại

    # đổi bằng chứng → hỏi lại
    ev2 = [Evidence(text="国内シェア8割", source="有報", kind="filing")]
    judge_batch([JevItem("9999", {}, ev2, qs)], ask, cache2, params.jev)
    assert len(calls) == 2
    # tăng version → hỏi lại
    q2 = reg["niche_share"].model_copy(update={"version": 2})
    judge_batch([JevItem("9999", {}, ev, [q2])], ask, cache2, params.jev)
    assert calls[-1] == ["niche_share"] and len(calls) == 3


def test_batch_failure_counted_not_faked(tmp_path, reg, params):
    def ask(state, questions):
        raise RuntimeError("boom")

    js, fails = judge_batch([JevItem("9999", {}, [], [reg["niche_share"]])], ask,
                            JudgmentCache(tmp_path / "c.jsonl"), params.jev)
    assert js == [] and fails[0]["code"] == "9999"


def test_name_only_label(reg, params):
    j = to_judgment("9999", reg["niche_share"], {"noul": 0.5}, [], params.jev)
    assert j.evidence_label == "name_only" and j.value is None


def test_build_state_keeps_source_language():
    s = build_state("9999", "テスト", [Evidence(text="本文", source="s", kind="filing")])
    assert s == {"ticker": "9999", "company_name_ja": "テスト", "evidence_ja": ["本文"]}


# ---------------------------------------------------------------- checklist (bước 4)
def _jd(reg, params, qid, noul):
    return to_judgment("9999", reg[qid], {"noul": noul}, [], params.jev)


def test_backlog_record_code():
    pts = [BacklogPoint(period=str(y), value=v, source="s", as_of=D)
           for y, v in [(2022, 10), (2023, 12), (2024, 11), (2025, 13)]]
    assert backlog_is_record(pts, 5) is True
    assert backlog_is_record(pts[:-1], 5) is False
    assert backlog_is_record(pts[:2], 5) is None
    assert backlog_is_record(None, 5) is None


def test_insider_ownership():
    hs = [Holder(name="創業者", ratio=0.15, kind="founder_entity"),
          Holder(name="社長", ratio=0.06, kind="officer"),
          Holder(name="信託口", ratio=0.10, kind="other")]
    assert insider_ownership(hs, 0.20) == (True, 0.21)
    assert insider_ownership(hs[1:], 0.20) == (False, 0.06)
    hs2 = [Holder(name="?", ratio=0.3, kind=None), hs[1]]
    assert insider_ownership(hs2, 0.20)[0] is None
    assert insider_ownership(None, 0.20) == (None, None)


def test_build_checklist(reg, params):
    js = {
        "niche_share": _jd(reg, params, "niche_share", 0.9),
        "theme_defense": _jd(reg, params, "theme_defense", 0.85),
        "theme_space": _jd(reg, params, "theme_space", 0.1),
        "recurring_revenue": _jd(reg, params, "recurring_revenue", 0.5),   # vùng giữa
        "record_backlog_text": _jd(reg, params, "record_backlog_text", 0.9),
    }
    hs = [Holder(name="創業者", ratio=0.25, kind="founder_entity")]
    c = build_checklist("9999", js, None, hs, params.checklist)
    by = {i.key: i for i in c.items}
    assert by["niche_share"].value is True
    assert by["theme"].value is True and c.themes == ["defense"]
    assert by["recurring_revenue"].value is None
    assert by["record_backlog"].method == "jev" and by["record_backlog"].value is True
    assert by["insider_ownership"].method == "code" and by["insider_ownership"].value is True
    assert c.score == 4 and c.known == 4


def test_checklist_without_any_data_is_all_none(params):
    c = build_checklist("9999", {}, None, None, params.checklist)
    assert c.score == 0 and c.known == 0


def test_run_from_export_asks_only_listed_codes(tmp_path, monkeypatch, params):
    """Bug: jev.run tự tính lại cổng bước 2 trên dữ liệu yfinance CHƯA ghép 会社予想 → loại hết."""
    import json as _json

    import src.jev.run as run
    from src.data.adapters import JsonFundamentalsSource
    from tests.conftest import make_fundamentals

    fs = JsonFundamentalsSource("yfinance", base=tmp_path / "fundamentals")
    for c in ("9000", "9001"):
        fs.write(make_fundamentals(code=c, forecast=None))   # tự tính cổng sẽ trượt
    exp = tmp_path / "pass2.json"
    exp.write_text(_json.dumps({"candidates": [{"code": "9000"}], "awaiting_forecast": []}))
    asked = []

    class FakeClient:
        def __init__(self, p):
            pass

        def ask(self, state, questions):
            asked.append(state["ticker"])
            return {q.id: {"noul": 0.9} for q in questions}

    monkeypatch.setattr(run, "JevClient", FakeClient)
    monkeypatch.setattr(run, "ROOT", tmp_path)
    rc = run.main(["--fundamentals-source", "yfinance", "--from", str(exp),
                   "--data-dir", str(tmp_path), "--tdnet-dir", str(tmp_path / "none")])
    assert rc == 0 and asked == ["9000"]
