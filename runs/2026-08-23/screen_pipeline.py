# -*- coding: utf-8 -*-
"""Prime Large/Mid relative-value screen vs JPX July-2026 sector averages."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUT = ROOT
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def load_listed() -> pd.DataFrame:
    df = pd.read_excel(RAW / "data_j.xlsx")
    df.columns = [
        "date",
        "code",
        "name",
        "market",
        "ind33_code",
        "ind33",
        "ind17_code",
        "ind17",
        "scale_code",
        "scale",
    ]
    def norm_code(x):
        s = str(x).strip()
        if s.endswith(".0"):
            s = s[:-2]
        if s.isdigit() and len(s) < 4:
            s = s.zfill(4)
        return s

    df["code"] = df["code"].map(norm_code)
    return df


def load_benchmarks() -> dict:
    data = json.loads((OUT / "benchmark_perpbr_202607.json").read_text(encoding="utf-8"))
    prime = {}
    for row in data["rows"]:
        if row["market_jp"] != "プライム市場":
            continue
        key = row["industry_jp"]
        # "7 化学" -> "化学"
        name = key
        if key and key[0].isdigit():
            name = key.split(" ", 1)[-1]
        prime[name] = row
        prime[key] = row
    return prime


def yahoo_quotes(symbols: list[str], workers: int = 8) -> list[dict]:
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache_path = OUT / "yahoo_info_cache.json"
    cache = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    keys = [
        "symbol",
        "shortName",
        "currency",
        "quoteType",
        "currentPrice",
        "regularMarketPrice",
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "marketCap",
        "trailingEps",
        "forwardEps",
        "bookValue",
        "dividendYield",
        "trailingAnnualDividendYield",
        "averageVolume",
        "averageDailyVolume3Month",
        "returnOnEquity",
        "debtToEquity",
        "totalCash",
        "totalDebt",
        "operatingCashflow",
        "freeCashflow",
        "profitMargins",
        "earningsGrowth",
        "revenueGrowth",
        "payoutRatio",
        "sharesOutstanding",
        "floatShares",
        "heldPercentInsiders",
        "mostRecentQuarter",
        "exDividendDate",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
    ]

    def fetch_one(sym: str) -> tuple[str, dict]:
        if sym in cache and cache[sym]:
            return sym, cache[sym]
        time.sleep(0.12)
        t = yf.Ticker(sym)
        info = t.info or {}
        slim = {k: info.get(k) for k in keys}
        slim["symbol"] = sym
        return sym, slim

    missing = [
        s
        for s in symbols
        if not cache.get(s) or (isinstance(cache.get(s), dict) and cache[s].get("error"))
    ]
    print(f"yfinance cache {len(cache)} missing {len(missing)}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, s): s for s in missing}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                _, slim = fut.result()
                cache[sym] = slim
            except Exception as e:
                print(f"yf FAIL {sym} {type(e).__name__}: {e}", flush=True)
                cache[sym] = {"symbol": sym, "error": str(e)}
            done += 1
            if done % 25 == 0 or done == len(missing):
                cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                print(f"yf {done}/{len(missing)}", flush=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return [cache.get(s, {"symbol": s}) for s in symbols]


def fnum(x):
    try:
        if x is None:
            return None
        v = float(x)
        if v != v:
            return None
        return v
    except (TypeError, ValueError):
        return None


def main():
    listed = load_listed()
    benches = load_benchmarks()
    prime = listed[listed["market"].astype(str).str.contains("プライム（内国株式）", na=False)].copy()
    universe = prime[
        prime["scale"].isin(["TOPIX Core30", "TOPIX Large70", "TOPIX Mid400"])
    ].copy()
    print("listed", len(listed), "prime", len(prime), "large+mid", len(universe))

    universe["yf"] = universe["code"].map(lambda c: f"{c}.T")
    quotes = yahoo_quotes(universe["yf"].tolist())
    qmap = {q.get("symbol"): q for q in quotes if q.get("symbol")}
    print("quote map", len(qmap))

    rows = []
    for rec in universe.to_dict("records"):
        q = qmap.get(rec["yf"], {})
        ind = rec["ind33"]
        bench = benches.get(ind) or benches.get(str(ind).strip())
        per = fnum(q.get("trailingPE"))
        fper = fnum(q.get("forwardPE"))
        pbr = fnum(q.get("priceToBook"))
        mcap = fnum(q.get("marketCap"))
        price = fnum(q.get("currentPrice") or q.get("regularMarketPrice"))
        vol = fnum(q.get("averageDailyVolume3Month") or q.get("averageVolume"))
        eps = fnum(q.get("trailingEps") or q.get("epsTrailingTwelveMonths"))
        divy = fnum(q.get("dividendYield") or q.get("trailingAnnualDividendYield"))
        # If Yahoo omitted multiples, reconstruct from price/eps/book.
        if per is None and price and eps and eps > 0:
            per = price / eps
        if pbr is None and price and fnum(q.get("bookValue")) and fnum(q.get("bookValue")) > 0:
            pbr = price / fnum(q.get("bookValue"))
        b_per = fnum(bench["simple_per"]) if bench else None
        b_pbr = fnum(bench["simple_pbr"]) if bench else None
        w_per = fnum(bench["w_per"]) if bench else None
        w_pbr = fnum(bench["w_pbr"]) if bench else None
        per_disc = (per / b_per - 1) if (per and b_per and b_per > 0) else None
        pbr_disc = (pbr / b_pbr - 1) if (pbr and b_pbr and b_pbr > 0) else None
        rows.append(
            {
                "code": rec["code"],
                "name": rec["name"],
                "industry": ind,
                "scale": rec["scale"],
                "price": price,
                "mcap_yen": mcap,
                "adv_shares": vol,
                "trailing_pe": per,
                "forward_pe": fper,
                "pbr": pbr,
                "eps_ttm": eps,
                "div_yield": divy,
                "sector_simple_per": b_per,
                "sector_w_per": w_per,
                "sector_simple_pbr": b_pbr,
                "sector_w_pbr": w_pbr,
                "per_vs_sector": per_disc,
                "pbr_vs_sector": pbr_disc,
                "roe": fnum(q.get("returnOnEquity")),
                "debt_to_equity": fnum(q.get("debtToEquity")),
                "total_cash": fnum(q.get("totalCash")),
                "total_debt": fnum(q.get("totalDebt")),
                "payout_ratio": fnum(q.get("payoutRatio")),
                "profit_margin": fnum(q.get("profitMargins")),
                "insider_pct": fnum(q.get("heldPercentInsiders")),
                "currency": q.get("currency"),
                "quote_type": q.get("quoteType"),
                "short_name": q.get("shortName"),
                "error": q.get("error"),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "universe_quotes.csv", index=False, encoding="utf-8-sig")
    print("universe with quotes", len(df), "pe", df["trailing_pe"].notna().sum(), "pbr", df["pbr"].notna().sum())

    # Hard filters. Do not guess missing multiples.
    liq = df[
        df["mcap_yen"].notna()
        & (df["mcap_yen"] >= 80_000_000_000)  # >= 800億円
        & df["trailing_pe"].notna()
        & (df["trailing_pe"] > 3)
        & (df["trailing_pe"] < 60)
        & df["pbr"].notna()
        & (df["pbr"] > 0.15)
        & (df["pbr"] < 8)
        & df["per_vs_sector"].notna()
        & df["pbr_vs_sector"].notna()
    ].copy()

    # Relative cheap: PER at least 20% below sector simple avg AND
    # (PBR at least 15% below sector simple avg OR PBR < 1.0)
    screen = liq[
        (liq["per_vs_sector"] <= -0.20)
        & ((liq["pbr_vs_sector"] <= -0.15) | (liq["pbr"] < 1.0))
    ].copy()
    screen["cheap_score"] = (-screen["per_vs_sector"] * 50) + (-screen["pbr_vs_sector"].clip(lower=-1.5) * 50)
    screen = screen.sort_values(["cheap_score", "mcap_yen"], ascending=[False, False])
    screen.to_csv(OUT / "primary_screen.csv", index=False, encoding="utf-8-sig")
    print("PRIMARY", len(screen))
    cols = [
        "code",
        "name",
        "industry",
        "scale",
        "price",
        "mcap_yen",
        "trailing_pe",
        "sector_simple_per",
        "per_vs_sector",
        "pbr",
        "sector_simple_pbr",
        "pbr_vs_sector",
        "div_yield",
        "cheap_score",
    ]
    print(screen[cols].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
