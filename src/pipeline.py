"""Ghép 8 bước thành một lần chạy → data/tenbagger-candidates.json (bàn giao Stock JP Bot).

Mọi số do code tính. Jev chỉ được ĐỌC từ cache (đã chạy batch trước bằng
`python -m src.jev.run`) — pipeline không gọi Jev, không gọi LLM.

  uv run python -m src.pipeline --fundamentals-source edinet [--fetch-ohlcv] [--limit N]

`--limit` ghi ra file `.sample.json` riêng — không bao giờ đè artifact production
(quét 20 mã vẫn cho độ phủ 20/20 = 100%, lọt mọi cổng).
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.catalyst.tdnet import (
    SOURCE as TDNET_SOURCE,
)
from src.catalyst.tdnet import (
    Disclosure,
    classify,
    effective_date,
    event_from_jev_choice,
    holidays_of,
    read_day,
    upgrade_likelihood,
)
from src.contracts import (
    CandidateExport,
    CatalystEvent,
    CatalystType,
    Evidence,
    Fundamentals,
    Judgment,
    PriceSnapshot,
    Quality,
    ScoreCard,
    Sourced,
    TenBaggerCandidate,
    Tier,
    evidence_hash,
)
from src.jev.client import JudgmentCache
from src.jev.registry import Registry
from src.params import Params
from src.screen.checklist import build_checklist
from src.screen.growth import growth_gate
from src.screen.universe import adtv, market_cap, universe_gate
from src.screen.valuation import valuation
from src.signals.gainers import SOURCE as OHLCV_SOURCE
from src.signals.gainers import evaluate as evaluate_signal
from src.tiering import assign_tier
from src.tracking.thesis import thesis_check

ROOT = Path(__file__).resolve().parent.parent
EXPORT_PATH = ROOT / "data" / "tenbagger-candidates.json"


# --------------------------------------------------------------- Jev (chỉ đọc cache)
def evidence_key(code: str, evidence: list[Evidence]) -> str:
    return evidence_hash(evidence) if evidence else f"name:{code}"


def judgments_for(code: str, evidence: list[Evidence], reg: Registry, cache: JudgmentCache,
                  prefix_ids: list[str]) -> dict[str, Judgment]:
    h = evidence_key(code, evidence)
    out = {}
    for qid in prefix_ids:
        if qid in reg:
            j = cache.get(code, reg[qid], h)
            if j is not None:
                out[qid] = j
    return out


def checklist_question_ids(p: Params) -> list[str]:
    return ["niche_share", "recurring_revenue", "record_backlog_text"] + [
        f"theme_{t}" for t in p.checklist.themes]


def title_evidence(d: Disclosure) -> list[Evidence]:
    return [Evidence(text=d.title, source=TDNET_SOURCE, kind="tdnet", url=d.url,
                     as_of=d.disclosed_at.date())]


# --------------------------------------------------------------- catalyst
def load_catalysts(tdnet_dir: Path, as_of: date, p: Params, reg: Registry | None,
                   cache: JudgmentCache | None) -> tuple[dict[str, list[CatalystEvent]], int]:
    """Đọc metadata TDnet đã lưu (≤ as_of), rule trước, Jev (cache) cho tiêu đề không khớp.

    → (sự kiện theo mã, số tiêu đề không khớp CHƯA có phán đoán Jev)."""
    by_code: dict[str, list[CatalystEvent]] = {}
    pending = 0
    if not tdnet_dir.exists():
        return by_code, 0
    for f in sorted(tdnet_dir.glob("*.jsonl")):
        if date.fromisoformat(f.stem) > as_of:
            continue
        events, unmatched = classify(read_day(f), p.catalyst)
        for d in unmatched:
            j = None
            if reg is not None and cache is not None and "tdnet_title_kind" in reg:
                ev = title_evidence(d)
                j = cache.get(d.code, reg["tdnet_title_kind"], evidence_key(d.code, ev))
            if j is None:
                pending += 1
                continue
            e = event_from_jev_choice(d, j.value if isinstance(j.value, str) else None, p.catalyst)
            if e is not None:
                events.append(e)
        for e in events:
            if e.effective_date <= as_of:
                by_code.setdefault(e.code, []).append(e)
    return by_code, pending


def code_catalysts(f: Fundamentals, as_of: date, p: Params) -> list[CatalystEvent]:
    annual_op = {a.fiscal_period: a.operating_profit for a in f.annual}
    ok, det = upgrade_likelihood(f.quarters, annual_op, p.catalyst)
    if not ok:
        return []
    q = f.quarters[-1]
    ann = q.announced or q.as_of
    eff = effective_date(datetime(ann.year, ann.month, ann.day, 15, 0), p.catalyst.cutoff_hhmm,
                         holidays_of(p.catalyst))
    if eff > as_of:
        return []
    return [CatalystEvent(code=f.code, type=CatalystType.UPGRADE_LIKELY,
                          strength=p.catalyst.strength[CatalystType.UPGRADE_LIKELY.value],
                          effective_date=eff, method="code", source=q.source,
                          detail=json.dumps(det, ensure_ascii=False))]


# --------------------------------------------------------------- một mã
def evaluate_code(code: str, f: Fundamentals | None, snap: PriceSnapshot | None,
                  ohlcv: pd.DataFrame | None, judgments: dict[str, Judgment],
                  catalysts: list[CatalystEvent], as_of: date, p: Params) -> TenBaggerCandidate:
    price = snap.close if snap else Sourced.missing()
    if f is None:
        f = Fundamentals(code=code)

    adtv_s = Sourced.missing()
    if ohlcv is not None and len(ohlcv):
        v = adtv(list(ohlcv["close"]), list(ohlcv["volume"]), p.universe.adtv_window_days)
        adtv_s = Sourced.of(v, ohlcv["date"].iat[-1], OHLCV_SOURCE, Quality.LIVE)

    mcap = market_cap(price, f.shares_issued, f.treasury_shares)
    # Bước 1 được dùng 時価総額 nguồn in sẵn làm PROXY khi chưa có 発行済/自己株;
    # bước 3 (net cash ratio) thì KHÔNG — chỉ công thức 清原.
    uni_mcap = mcap if mcap.value is not None else f.market_cap_reported
    uni = universe_gate(code, f.market, uni_mcap, adtv_s, p.universe, as_of)
    grw = growth_gate(f, p.growth)
    val = valuation(f, price, mcap, p.valuation)
    chk = build_checklist(code, judgments, f.backlog, f.holders, p.checklist)
    cats = sorted(catalysts + code_catalysts(f, as_of, p), key=lambda e: e.effective_date)
    sc = ScoreCard(universe=uni, growth=grw, valuation=val, checklist=chk, catalysts=cats)
    tier, labels, reasons = assign_tier(sc, as_of, p)

    sig = None
    if ohlcv is not None and len(ohlcv):
        gok = None if grw.insufficient_data else grw.passed
        sig = evaluate_signal(code, ohlcv, p.signals, gok)
    th = thesis_check(code, as_of, f.quarters, cats, grw, p.thesis) if tier is not Tier.NONE else None
    return TenBaggerCandidate(code=code, name=f.name, market=f.market, tier=tier, labels=labels,
                              tier_reasons=reasons, scorecard=sc, entry_signal=sig, thesis=th)


# --------------------------------------------------------------- export
def build_export(cands: list[TenBaggerCandidate], as_of: date, p: Params, failures: list[str],
                 notes: list[str]) -> CandidateExport:
    counts = {t.value: sum(1 for c in cands if c.tier is t) for t in Tier}
    counts["insufficient_growth_data"] = sum(
        1 for c in cands if c.scorecard.growth and c.scorecard.growth.insufficient_data)
    kept = sorted((c for c in cands if c.tier is not Tier.NONE),
                  key=lambda c: (c.tier.value, c.code))
    return CandidateExport(generated_at=datetime.now(timezone.utc), as_of=as_of,
                           params_version=p.version, universe_count=len(cands), counts=counts,
                           candidates=kept, failures=failures, notes=notes)


def write_export(exp: CandidateExport, sample: bool, path: Path = EXPORT_PATH) -> Path:
    out = path.with_suffix(".sample.json") if sample else path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(exp.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return out


# --------------------------------------------------------------- CLI
def _session_closed(as_of: date) -> bool:
    """Phiên as_of đã đóng chưa (TSE đóng 15:30 JST từ 2024-11)."""
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    return as_of < now.date() or (now.hour, now.minute) >= (15, 30)


class PriceChain:
    """Giá: snapshot kiyohara trước (ưu tiên, không fetch trùng), rồi trang 株探 đã lưu."""

    def __init__(self, sources: list):
        self.sources = sources
        self.name = " → ".join(x.name for x in sources) or "không có"

    def snapshot(self, code: str) -> PriceSnapshot | None:
        for src in self.sources:
            try:
                s = src.snapshot(code)
            except FileNotFoundError:
                continue
            if s is not None and s.close.value is not None:
                return s
        return None


def fundamentals_coverage(codes: list[str], fs) -> float:
    if not codes:
        return 0.0
    have = 0
    for c in codes:
        f = fs.get(c)
        if f is not None and f.annual:
            have += 1
    return have / len(codes)


def main(argv: list[str] | None = None) -> int:
    from src.data.adapters import JsonFundamentalsSource, KiyoharaSnapshotSource
    from src.data.kabutan_finance import KabutanPriceSource
    from src.jev.registry import default_registry
    from src.params import default_params
    from src.signals.gainers import completed_sessions, fetch_chart

    ap = argparse.ArgumentParser()
    ap.add_argument("--fundamentals-source", required=True)
    ap.add_argument("--universe", default=None, help="data/universe.json (JPX)")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--tdnet-dir", default=str(ROOT / "data" / "tdnet"))
    ap.add_argument("--fetch-ohlcv", action="store_true",
                    help="tải OHLCV cho mã QUA bước 2 (mã khác là NONE, không cần)")
    ap.add_argument("--min-coverage", type=float, default=0.8)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(EXPORT_PATH))
    a = ap.parse_args(argv)

    p = default_params()
    reg = default_registry()
    cache = JudgmentCache(ROOT / p.jev.cache_path)
    as_of = date.fromisoformat(a.as_of) if a.as_of else date.today()
    fs = JsonFundamentalsSource(a.fundamentals_source, base=Path(a.data_dir) / "fundamentals")
    prices = PriceChain([KiyoharaSnapshotSource(a.snapshot), KabutanPriceSource(a.data_dir)])
    markets: dict[str, str] = {}
    if a.universe:
        uni = json.loads(Path(a.universe).read_text(encoding="utf-8"))
        codes = [u["code"] for u in uni["codes"]]
        markets = {u["code"]: u["market"] for u in uni["codes"]}
    else:
        codes = fs.codes()
    if a.limit:
        codes = codes[:a.limit]
    cov = fundamentals_coverage(codes, fs)
    cats, pending = load_catalysts(Path(a.tdnet_dir), as_of, p, reg, cache)

    cands, failures = [], []
    for code in codes:
        f = fs.get(code)
        if f is not None and f.market is None and code in markets:
            f = f.model_copy(update={"market": markets[code]})
        js = judgments_for(code, f.text_evidence if f else [], reg, cache,
                           checklist_question_ids(p))
        snap = prices.snapshot(code)
        c = evaluate_code(code, f, snap, None, js, cats.get(code, []), as_of, p)
        if a.fetch_ohlcv and c.scorecard.growth and c.scorecard.growth.passed:
            try:
                ohlcv = completed_sessions(fetch_chart(code, p.signals.user_agent), as_of,
                                           market_closed=_session_closed(as_of))
                time.sleep(p.signals.request_delay_s)
                c = evaluate_code(code, f, snap, ohlcv, js, cats.get(code, []), as_of, p)
            except Exception as e:  # noqa: BLE001 — đếm, không lấp
                failures.append(f"{code}: ohlcv {type(e).__name__}")
        cands.append(c)
    notes = [f"nguồn cơ bản: {fs.name} (phủ {cov:.1%} universe)", f"nguồn giá: {prices.name}",
             f"tiêu đề TDnet chưa có phán đoán Jev: {pending}",
             "net cash 清原 cần EDINET (流動資産/投資有価証券/負債合計/発行済/自己株) — thiếu thì null"]
    exp = build_export(cands, as_of, p, failures, notes)
    if not a.limit and cov < a.min_coverage:
        print(f"độ phủ cơ bản {cov:.1%} < {a.min_coverage:.0%} — KHÔNG ghi đè artifact production")
        write_export(exp, sample=True, path=Path(a.out))
        return 0
    print(write_export(exp, sample=bool(a.limit), path=Path(a.out)))
    print(json.dumps(exp.counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
