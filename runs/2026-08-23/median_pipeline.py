# -*- coding: utf-8 -*-
"""Prime-all industry median PER/PBR from name-level quotes.

JPX publishes simple/weighted *averages*, not medians. This script builds
medians from individual stocks so relative-value screens are not pulled by
semiconductor mega-caps (電気機器) or NTT-class names (情報・通信).

Definition (disclosed, not guessed):
- Population: TSE Prime domestic ordinary shares in JPX listed-companies
  file as of 2026-07 (data_j.xls).
- PER: trailing PE (Yahoo TTM). Exclude <=0 and >=1000 (JPX '*' rule).
- PBR: price/book. Exclude <=0.
- Timing: quotes as of fetch date (~2026-08-21/23), NOT JPX July-end prices
  and NOT JPX fiscal-year NI window (May2025-Apr2026). Do not treat as a
  restatement of JPX averages.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from screen_pipeline import (  # noqa: E402
    OUT,
    fnum,
    load_benchmarks,
    load_listed,
    yahoo_quotes,
)


def build_frame(listed: pd.DataFrame, quotes: list[dict]) -> pd.DataFrame:
    qmap = {q.get("symbol"): q for q in quotes if q.get("symbol")}
    rows = []
    for rec in listed.to_dict("records"):
        q = qmap.get(rec["yf"], {})
        price = fnum(q.get("currentPrice") or q.get("regularMarketPrice"))
        eps = fnum(q.get("trailingEps") or q.get("epsTrailingTwelveMonths"))
        book = fnum(q.get("bookValue"))
        per = fnum(q.get("trailingPE"))
        pbr = fnum(q.get("priceToBook"))
        if per is None and price and eps and eps > 0:
            per = price / eps
        if pbr is None and price and book and book > 0:
            pbr = price / book
        rows.append(
            {
                "code": rec["code"],
                "name": rec["name"],
                "industry": rec["ind33"],
                "scale": rec["scale"],
                "price": price,
                "mcap_yen": fnum(q.get("marketCap")),
                "trailing_pe": per,
                "forward_pe": fnum(q.get("forwardPE")),
                "pbr": pbr,
                "eps_ttm": eps,
                "roe": fnum(q.get("returnOnEquity")),
                "div_yield": fnum(q.get("dividendYield") or q.get("trailingAnnualDividendYield")),
                "debt_to_equity": fnum(q.get("debtToEquity")),
                "error": q.get("error"),
            }
        )
    return pd.DataFrame(rows)


def valid_pe(s: pd.Series) -> pd.Series:
    return s[(s.notna()) & (s > 0) & (s < 1000)]


def valid_pbr(s: pd.Series) -> pd.Series:
    return s[(s.notna()) & (s > 0)]


def quality(n_valid: int, n_pop: int, n_jpx: int | None) -> str:
    if n_pop <= 0:
        return "低"
    cov = n_valid / n_pop
    if n_valid < 5:
        return "低"
    if cov < 0.50:
        return "低"
    if cov < 0.80 or n_valid < 10:
        return "中"
    if n_jpx and n_pop < 0.85 * n_jpx:
        return "中"
    return "高"


def industry_stats(df: pd.DataFrame, benches: dict) -> pd.DataFrame:
    out = []
    for ind, g in df.groupby("industry"):
        pe = valid_pe(g["trailing_pe"])
        pb = valid_pbr(g["pbr"])
        bench = benches.get(ind) or {}
        n_jpx = fnum(bench.get("n_cos"))
        n_jpx_i = int(n_jpx) if n_jpx else None
        rec = {
            "industry": ind,
            "n_listed": int(len(g)),
            "n_jpx_jul": n_jpx_i,
            "n_pe": int(len(pe)),
            "n_pbr": int(len(pb)),
            "pe_median": round(float(pe.median()), 2) if len(pe) else None,
            "pe_p25": round(float(pe.quantile(0.25)), 2) if len(pe) else None,
            "pe_p75": round(float(pe.quantile(0.75)), 2) if len(pe) else None,
            "pe_mean": round(float(pe.mean()), 2) if len(pe) else None,
            "jpx_simple_per": fnum(bench.get("simple_per")),
            "jpx_w_per": fnum(bench.get("w_per")),
            "pbr_median": round(float(pb.median()), 3) if len(pb) else None,
            "pbr_p25": round(float(pb.quantile(0.25)), 3) if len(pb) else None,
            "pbr_p75": round(float(pb.quantile(0.75)), 3) if len(pb) else None,
            "pbr_mean": round(float(pb.mean()), 3) if len(pb) else None,
            "jpx_simple_pbr": fnum(bench.get("simple_pbr")),
            "jpx_w_pbr": fnum(bench.get("w_pbr")),
        }
        rec["pe_median_vs_jpx_simple"] = (
            round(rec["pe_median"] / rec["jpx_simple_per"] - 1, 3)
            if rec["pe_median"] and rec["jpx_simple_per"]
            else None
        )
        rec["pbr_median_vs_jpx_simple"] = (
            round(rec["pbr_median"] / rec["jpx_simple_pbr"] - 1, 3)
            if rec["pbr_median"] and rec["jpx_simple_pbr"]
            else None
        )
        rec["quality"] = quality(min(rec["n_pe"], rec["n_pbr"]), rec["n_listed"], n_jpx_i)
        if rec["n_listed"] < 8:
            rec["quality"] = "低"
            rec["sample_note"] = "業種n<8。中央値は参考値"
        else:
            rec["sample_note"] = ""
        out.append(rec)
    return pd.DataFrame(out).sort_values("industry")


def screen_vs_median(df: pd.DataFrame, med: pd.DataFrame) -> pd.DataFrame:
    m = med.set_index("industry")
    x = df.copy()
    x["sector_med_pe"] = x["industry"].map(m["pe_median"])
    x["sector_med_pbr"] = x["industry"].map(m["pbr_median"])
    x["per_vs_med"] = x["trailing_pe"] / x["sector_med_pe"] - 1
    x["pbr_vs_med"] = x["pbr"] / x["sector_med_pbr"] - 1
    liq = x[
        x["mcap_yen"].notna()
        & (x["mcap_yen"] >= 80_000_000_000)
        & x["trailing_pe"].notna()
        & (x["trailing_pe"] > 3)
        & (x["trailing_pe"] < 60)
        & x["pbr"].notna()
        & (x["pbr"] > 0.15)
        & (x["pbr"] < 8)
        & x["per_vs_med"].notna()
        & x["pbr_vs_med"].notna()
        & x["scale"].isin(["TOPIX Core30", "TOPIX Large70", "TOPIX Mid400"])
    ]
    hit = liq[
        (liq["per_vs_med"] <= -0.20)
        & ((liq["pbr_vs_med"] <= -0.15) | (liq["pbr"] < 1.0))
    ].copy()
    hit["cheap_score"] = (-hit["per_vs_med"] * 50) + (
        -hit["pbr_vs_med"].clip(lower=-1.5) * 50
    )
    return hit.sort_values(["cheap_score", "mcap_yen"], ascending=[False, False])


def main():
    listed = load_listed()
    benches = load_benchmarks()
    prime = listed[
        listed["market"].astype(str).str.contains("プライム（内国株式）", na=False)
    ].copy()
    prime["yf"] = prime["code"].map(lambda c: f"{c}.T")
    print("prime listed", len(prime), flush=True)

    quotes = yahoo_quotes(prime["yf"].tolist(), workers=4)
    df = build_frame(prime, quotes)
    df.to_csv(OUT / "prime_all_quotes.csv", index=False, encoding="utf-8-sig")
    pe_ok = valid_pe(df["trailing_pe"])
    pb_ok = valid_pbr(df["pbr"])
    print(
        f"quotes {len(df)} pe_valid {len(pe_ok)} pbr_valid {len(pb_ok)}",
        flush=True,
    )

    med_all = industry_stats(df, benches)
    med_all.to_csv(OUT / "industry_median_prime_all.csv", index=False, encoding="utf-8-sig")
    med_all.to_json(
        OUT / "industry_median_prime_all.json",
        orient="records",
        force_ascii=False,
        indent=2,
    )

    lm = df[df["scale"].isin(["TOPIX Core30", "TOPIX Large70", "TOPIX Mid400"])]
    med_lm = industry_stats(lm, benches)
    med_lm.to_csv(OUT / "industry_median_large_mid.csv", index=False, encoding="utf-8-sig")

    # Screen using ALL-PRIME medians (the intended benchmark).
    hit = screen_vs_median(df, med_all)
    hit.to_csv(OUT / "primary_screen_vs_median.csv", index=False, encoding="utf-8-sig")
    print("PRIMARY vs median", len(hit), flush=True)

    old = pd.read_csv(OUT / "primary_screen.csv") if (OUT / "primary_screen.csv").exists() else None
    old_codes = set(old["code"].astype(str)) if old is not None else set()
    new_codes = set(hit["code"].astype(str))
    print("overlap", len(old_codes & new_codes), "dropped", len(old_codes - new_codes), "added", len(new_codes - old_codes))

    final_prev = ["7751", "4118", "6326", "7240", "4540", "4631", "1928"]
    print("\n=== previous final 7 vs median rule ===")
    chk = df[df["code"].isin(final_prev)].merge(
        med_all[["industry", "pe_median", "pbr_median", "quality"]],
        on="industry",
        how="left",
    )
    chk["per_vs_med"] = chk["trailing_pe"] / chk["pe_median"] - 1
    chk["pbr_vs_med"] = chk["pbr"] / chk["pbr_median"] - 1
    chk["pass"] = (chk["per_vs_med"] <= -0.20) & (
        (chk["pbr_vs_med"] <= -0.15) | (chk["pbr"] < 1.0)
    )
    cols = [
        "code",
        "name",
        "industry",
        "trailing_pe",
        "pe_median",
        "per_vs_med",
        "pbr",
        "pbr_median",
        "pbr_vs_med",
        "pass",
    ]
    print(chk[cols].to_string(index=False))

    print("\n=== median table (priority industries) ===")
    pri = [
        "機械",
        "化学",
        "電気機器",
        "輸送用機器",
        "銀行業",
        "建設業",
        "医薬品",
        "保険業",
        "情報・通信業",
        "鉄鋼",
        "卸売業",
        "小売業",
        "食料品",
        "不動産業",
        "サービス業",
        "電気・ガス業",
        "陸運業",
        "ガラス・土石製品",
    ]
    show = med_all[med_all["industry"].isin(pri)].copy()
    show = show.set_index("industry").reindex([i for i in pri if i in set(show["industry"])]).reset_index()
    print(
        show[
            [
                "industry",
                "n_listed",
                "n_jpx_jul",
                "n_pe",
                "pe_median",
                "pe_p25",
                "pe_p75",
                "jpx_simple_per",
                "jpx_w_per",
                "pbr_median",
                "pbr_p25",
                "pbr_p75",
                "jpx_simple_pbr",
                "jpx_w_pbr",
                "quality",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
