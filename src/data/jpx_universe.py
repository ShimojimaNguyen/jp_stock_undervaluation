"""Danh sách mã toàn TSE (Prime/Standard/Growth, 内国株式) từ JPX 東証上場銘柄一覧.

Nguồn: https://www.jpx.co.jp/markets/statistics-equities/misc/01.html → link data_j.xls(x)
robots.txt jpx.co.jp: `User-Agent:* Disallow:` — cho phép toàn bộ (market-data-sources §2.4).
Cột dùng: 日付, コード, 銘柄名, 市場・商品区分 (kiyohara/build_universe.py dùng 4/5 cột này;
`市場・商品区分` CHƯA kiểm trên file thật — thiếu cột thì DỪNG, không đoán vị trí).

Cổng: < min_codes mã (mặc định 3000) → không ghi. TSE nội địa ~3.800 mã.
"""
from __future__ import annotations

import io
import json
import re
from datetime import date
from pathlib import Path

from src.contracts import Market

INDEX = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
BASE = "https://www.jpx.co.jp"
SOURCE = "JPX 東証上場銘柄一覧 (data_j)"
SEGMENTS = {"プライム": Market.PRIME, "スタンダード": Market.STANDARD, "グロース": Market.GROWTH}
REQUIRED = ("日付", "コード", "銘柄名", "市場・商品区分")


def segment_of(label: str) -> Market | None:
    """'プライム（内国株式）' → PRIME. ETF/REIT/外国株式/PRO Market → None."""
    if "内国株式" not in label:
        return None
    return next((m for k, m in SEGMENTS.items() if k in label), None)


def parse_rows(rows: list[dict]) -> tuple[list[dict], date | None, int]:
    """→ (mã hợp lệ, ngày ảnh chụp, số dòng bị bỏ)."""
    out, snap, skipped = [], None, 0
    for r in rows:
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            raise ValueError(f"thiếu cột {missing} — JPX đổi header, KHÔNG đoán")
        m = segment_of(str(r["市場・商品区分"] or ""))
        raw = r["コード"]
        if m is None or raw is None or str(raw).strip() in ("", "nan"):
            skipped += 1
            continue
        code = str(raw).strip()
        if code.endswith(".0"):
            code = code[:-2]
        if snap is None and r["日付"] not in (None, ""):
            v = r["日付"]
            d = str(int(v)) if isinstance(v, float | int) else re.sub(r"\D", "", str(v))
            if len(d) == 8:
                snap = date(int(d[:4]), int(d[4:6]), int(d[6:]))
        out.append({"code": code.zfill(4), "name": str(r["銘柄名"]).strip(), "market": m.value})
    out.sort(key=lambda x: x["code"])
    return out, snap, skipped


def fetch(user_agent: str, session=None) -> tuple[list[dict], date | None, int]:
    import pandas as pd
    import requests

    from src.data.http import robots_policy

    s = session or requests.Session()
    if not robots_policy(INDEX, user_agent, s)[0]:
        raise PermissionError("robots.txt của jpx.co.jp không cho phép")
    page = s.get(INDEX, headers={"User-Agent": user_agent}, timeout=60)
    page.raise_for_status()
    m = re.search(r'href="([^"]*data_j\.xlsx?)"', page.text)
    if not m:
        raise ValueError("không thấy link data_j trên trang JPX — bố cục đã đổi")
    raw = s.get(BASE + m.group(1), headers={"User-Agent": user_agent}, timeout=120)
    raw.raise_for_status()
    df = pd.read_excel(io.BytesIO(raw.content), dtype={"コード": str})
    return parse_rows(df.to_dict("records"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    from src.params import default_params

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/universe.json")
    ap.add_argument("--min-codes", type=int, default=3000)
    a = ap.parse_args(argv)
    codes, snap, skipped = fetch(default_params().signals.user_agent)
    if len(codes) < a.min_codes:
        print(f"chỉ {len(codes)} mã (< {a.min_codes}) — KHÔNG ghi đè")
        return 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({
        "as_of": snap.isoformat() if snap else None, "source": SOURCE,
        "count": len(codes), "skipped": skipped, "codes": codes,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"universe {len(codes)} mã (bỏ {skipped}) as_of={snap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
