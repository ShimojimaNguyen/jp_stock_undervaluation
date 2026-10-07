"""yfinance → `Fundamentals` + giá — nguồn cơ bản CHẠY ĐƯỢC từ GitHub Actions.

Đo 2026-10-07 trên Actions (src/data/probe.py): 株探 bị AWS WAF chặn IP Actions,
TDnet robots `Disallow: /`; yfinance trả đủ:
  income_stmt   Total Revenue / Operating Income / Diluted EPS (4–5 năm, cột cuối hay NaN)
  cashflow      Operating Cash Flow
  balance_sheet Current Assets / Total Liabilities Net Minority Interest /
                Investmentin Financial Assets (≈投資有価証券) / Stockholders Equity /
                Total Assets / Share Issued / Treasury Shares Number

KHÔNG có: 会社予想 (dự báo CÔNG TY). yfinance chỉ có dự báo của analyst — KHÁC định
nghĩa nên KHÔNG được dùng thay. Forecast để None → cổng bước 2 'thiếu dữ liệu'
cho tới khi có nguồn 会社予想 (株探 chạy local, hoặc J-Quants).

Quy ước dữ liệu:
  · NaN → None (không bao giờ 0).
  · `Investmentin Financial Assets` = 0.0 đúng bằng không: Yahoo hay in 0 cho dòng
    công ty không công bố → coi là KHÔNG BIẾT (None) → net cash null. Thận trọng:
    một mã bị loại oan khỏi tầng A còn hơn một net cash bịa.
  · Kỳ năm: chênh giữa hai kỳ liền nhau không ≈ 12 tháng → months=None (変).
"""
from __future__ import annotations

import json
import math
import time
from datetime import date
from pathlib import Path

from src.contracts import (
    AnnualResult,
    BalanceSheet,
    Fundamentals,
    Market,
    PriceSnapshot,
    Quality,
    Sourced,
)

SOURCE = "Yahoo Finance (yfinance)"
INVEST_KEYS = ("Investmentin Financial Assets", "Available For Sale Securities")


def _v(df, key: str, col) -> float | None:
    if df is None or key not in df.index:
        return None
    x = df.loc[key, col]
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _period(col) -> str:
    return f"{col.year:04d}.{col.month:02d}"


def build_fundamentals(code: str, income, balance, cashflow, market: Market | None,
                       name: str | None, fetched: date) -> Fundamentals:
    annual: list[AnnualResult] = []
    if income is not None and not income.empty:
        cols = sorted(income.columns)          # cũ → mới
        prev = None
        for c in cols:
            rev = _v(income, "Total Revenue", c)
            if rev is None:
                prev = c
                continue
            months = 12
            if prev is not None and abs((c - prev).days - 365) > 20:
                months = None                   # kỳ không dài ~12 tháng
            eps = _v(income, "Diluted EPS", c)
            if eps is None:
                eps = _v(income, "Basic EPS", c)
            cfo = _v(cashflow, "Operating Cash Flow", c) if cashflow is not None and \
                c in getattr(cashflow, "columns", []) else None
            annual.append(AnnualResult(
                fiscal_period=_period(c), months=months, revenue=rev,
                operating_profit=_v(income, "Operating Income", c), eps=eps, cfo=cfo,
                net_income=_v(income, "Net Income Common Stockholders", c)
                if _v(income, "Net Income Common Stockholders", c) is not None
                else _v(income, "Net Income", c),
                source=SOURCE, as_of=c.date()))
            prev = c

    bs = None
    shares = treasury = Sourced.missing()
    if balance is not None and not balance.empty:
        c = max(balance.columns)
        inv = None
        for k in INVEST_KEYS:
            x = _v(balance, k, c)
            if x is not None and x != 0.0:      # 0.0 = không công bố, không phải 0 yên
                inv = x
                break
        bs = BalanceSheet(
            period_end=c.date(),
            current_assets=_v(balance, "Current Assets", c),
            investment_securities=inv,
            total_liabilities=_v(balance, "Total Liabilities Net Minority Interest", c),
            total_assets=_v(balance, "Total Assets", c),
            equity=_v(balance, "Stockholders Equity", c),
            source=SOURCE, as_of=c.date())
        shares = Sourced.of(_v(balance, "Share Issued", c), c.date(), SOURCE)
        treasury = Sourced.of(_v(balance, "Treasury Shares Number", c), c.date(), SOURCE)
    return Fundamentals(code=code, name=name, market=market, annual=annual, forecast=None,
                        balance_sheet=bs, shares_issued=shares, treasury_shares=treasury)


def fetch(code: str, market: Market | None, name: str | None
          ) -> tuple[Fundamentals, PriceSnapshot]:
    import yfinance as yf

    t = yf.Ticker(f"{code}.T")
    f = build_fundamentals(code, t.income_stmt, t.balance_sheet, t.cashflow, market, name,
                           date.today())
    px = None
    try:
        h = t.history(period="5d", interval="1d", auto_adjust=False)
        if not h.empty and math.isfinite(float(h["Close"].iloc[-1])):
            px = (float(h["Close"].iloc[-1]), h.index[-1].date())
    except Exception:  # noqa: BLE001 — giá thiếu = None, không lấp
        px = None
    snap = PriceSnapshot(code=code, close=Sourced.of(px[0] if px else None,
                                                     px[1] if px else None, SOURCE,
                                                     Quality.LIVE))
    return f, snap


class YFPriceSource:
    name = "prices:yfinance"

    def __init__(self, base_dir: str | Path):
        self.dir = Path(base_dir) / "prices" / "yfinance"

    def snapshot(self, code: str) -> PriceSnapshot | None:
        p = self.dir / f"{code}.json"
        return PriceSnapshot.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


def main(argv: list[str] | None = None) -> int:
    """uv run python -m src.data.yf_fundamentals --universe data/universe.json --shard 0/5"""
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.5)
    a = ap.parse_args(argv)
    i, n = (int(x) for x in a.shard.split("/"))
    uni = json.loads(Path(a.universe).read_text(encoding="utf-8"))["codes"]
    rows = [u for k, u in enumerate(sorted(uni, key=lambda u: u["code"])) if k % n == i]
    if a.limit:
        rows = rows[:a.limit]
    base = Path(a.data_dir)
    ok, failures = 0, []
    for u in rows:
        try:
            f, snap = fetch(u["code"], Market(u["market"]), u.get("name"))
        except Exception as e:  # noqa: BLE001 — đếm, không lấp
            failures.append(f"{u['code']}: {type(e).__name__}")
            continue
        for sub, obj in (("fundamentals", f), ("prices", snap)):
            d = base / sub / "yfinance"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{u['code']}.json").write_text(obj.model_dump_json(indent=1) + "\n",
                                                 encoding="utf-8")
        ok += 1
        time.sleep(a.delay)
    print(f"yfinance shard {a.shard}: {ok}/{len(rows)} lưu, {len(failures)} lỗi")
    for fl in failures[:30]:
        print("  " + fl)
    return 0 if ok >= 0.8 * max(len(rows), 1) else 1


if __name__ == "__main__":
    raise SystemExit(main())
