"""Thăm dò nguồn — chạy ở CI để biết nguồn nào DÙNG ĐƯỢC từ IP đó, trường nào có.

  uv run python -m src.data.probe --codes 7203 6861 3436

Không ghi dữ liệu; chỉ in trạng thái + tên trường + vài giá trị để mắt người soát.
"""
from __future__ import annotations

import argparse
import json

UA = "jp-stock-undervaluation/0.1 (research)"

HOSTS = {
    "yahoo_jp_quote": "https://finance.yahoo.co.jp/quote/7203.T",
    "yahoo_jp_robots": "https://finance.yahoo.co.jp/robots.txt",
    "edinet_api": "https://api.edinet-fsa.go.jp/api/v2/documents.json?date=2026-09-30&type=1",
    "jquants_api": "https://api.jquants.com/v1/listed/info",
    "kabutan_robots": "https://kabutan.jp/robots.txt",
}

BS_KEYS = ["Current Assets", "Total Liabilities Net Minority Interest",
           "Investmentin Financial Assets", "Long Term Equity Investment",
           "Available For Sale Securities", "Other Investments",
           "Stockholders Equity", "Total Assets", "Share Issued", "Treasury Shares Number",
           "Ordinary Shares Number"]
IS_KEYS = ["Total Revenue", "Operating Income", "Diluted EPS", "Basic EPS"]
CF_KEYS = ["Operating Cash Flow"]


def http_status() -> dict:
    import requests

    out = {}
    for k, u in HOSTS.items():
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=20)
            out[k] = f"HTTP {r.status_code} {len(r.content)}B"
        except Exception as e:  # noqa: BLE001
            out[k] = f"{type(e).__name__}"
    return out


def _frame(df, keys):
    if df is None or getattr(df, "empty", True):
        return {"_empty": True}
    cols = [str(c)[:10] for c in df.columns]
    rows = {}
    for k in keys:
        if k in df.index:
            rows[k] = [None if v != v else float(v) for v in df.loc[k].tolist()]
    return {"periods": cols, "rows": rows, "missing": [k for k in keys if k not in df.index]}


def yf_probe(code: str) -> dict:
    import yfinance as yf

    t = yf.Ticker(f"{code}.T")
    out: dict = {}
    for name, attr, keys in (("income", "income_stmt", IS_KEYS),
                             ("balance", "balance_sheet", BS_KEYS),
                             ("cashflow", "cashflow", CF_KEYS)):
        try:
            out[name] = _frame(getattr(t, attr), keys)
        except Exception as e:  # noqa: BLE001
            out[name] = {"error": f"{type(e).__name__}: {e}"[:200]}
    try:
        fi = t.fast_info
        out["fast_info"] = {"last_price": fi.get("lastPrice"), "shares": fi.get("shares"),
                            "market_cap": fi.get("marketCap"), "currency": fi.get("currency")}
    except Exception as e:  # noqa: BLE001
        out["fast_info"] = {"error": f"{type(e).__name__}"}
    return out


def yahoo_jp_probe(code: str) -> dict:
    """Tìm khối 会社予想 trên trang Yahoo JP — CHỈ 2 request (nguồn chặn sau ~85 mã)."""
    import re

    import requests

    out = {}
    for suffix in ("", "/performance"):
        url = f"https://finance.yahoo.co.jp/quote/{code}.T{suffix}"
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        except Exception as e:  # noqa: BLE001
            out[suffix or "/"] = f"{type(e).__name__}"
            continue
        t = r.text.replace('\\"', '"')
        info = {"status": r.status_code, "bytes": len(r.content),
                "counts": {k: t.count(k) for k in ("会社予想", "予想", "営業利益", "売上高",
                                                    "forecast", "Forecast", "isLock")}}
        keys = sorted(set(re.findall(r'"([a-zA-Z]*(?:[Ff]orecast|[Ss]ales|[Oo]perating)[a-zA-Z]*)"', t)))
        info["json_keys"] = keys[:60]
        i = t.find("営業利益")
        info["around_op"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[max(0, i - 300):i + 500]))[:600] if i >= 0 else None
        out[suffix or "/"] = info
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", nargs="+", default=["7203", "6861", "3436"])
    ap.add_argument("--yahoo-jp", default=None, help="thăm dò trang Yahoo JP của MỘT mã")
    a = ap.parse_args(argv)
    if a.yahoo_jp:
        print(json.dumps({"yahoo_jp": yahoo_jp_probe(a.yahoo_jp)}, ensure_ascii=False))
        return 0
    for c in a.codes:
        print(json.dumps({c: yf_probe(c)}, ensure_ascii=False))
    print(json.dumps({"http": http_status()}, ensure_ascii=False))   # in cuối = nằm ở đuôi log
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
