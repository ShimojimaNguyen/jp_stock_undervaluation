"""Chẩn đoán độ phủ TỪNG TRƯỜNG sau khi tải — chạy ở CI để biết parser nào hỏng.

  uv run python -m src.diagnostics --data-dir data --source kabutan

In tỷ lệ mã có từng trường (sàn, giá, 時価総額, đủ 4 năm, dự báo, CFO, BS) và
vài mã mẫu để mắt người soát. Một trường 0% trên hàng trăm mã = parser hỏng
hoặc nguồn không có — cả hai đều phải biết trước khi tin kết quả.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.data.adapters import JsonFundamentalsSource
from src.data.kabutan_finance import KabutanPriceSource
from src.params import default_params
from src.screen.growth import growth_gate


def report(data_dir: Path, source: str, sample: int = 5) -> dict:
    fs = JsonFundamentalsSource(source, base=data_dir / "fundamentals")
    px = KabutanPriceSource(data_dir)
    p = default_params()
    codes = fs.codes()
    n = len(codes)
    cnt = {k: 0 for k in ("market", "price", "mcap_reported", "annual4", "forecast_op",
                          "forecast_irregular", "cfo_last", "balance_sheet", "growth_pass",
                          "growth_insufficient")}
    fail_reasons: dict[str, int] = {}
    samples = []
    for c in codes:
        f = fs.get(c)
        s = px.snapshot(c)
        cnt["market"] += f.market is not None
        cnt["price"] += bool(s and s.close.value is not None)
        cnt["mcap_reported"] += f.market_cap_reported.value is not None
        cnt["annual4"] += len(f.annual) >= 4
        cnt["forecast_op"] += bool(f.forecast and f.forecast.operating_profit is not None)
        cnt["forecast_irregular"] += bool(f.forecast and f.forecast.irregular)
        cnt["cfo_last"] += bool(f.annual and f.annual[-1].cfo is not None)
        cnt["balance_sheet"] += f.balance_sheet is not None
        g = growth_gate(f, p.growth)
        cnt["growth_pass"] += g.passed
        cnt["growth_insufficient"] += g.insufficient_data
        for ch in g.checks:
            if ch.passed is None:
                fail_reasons[f"{ch.name}:none"] = fail_reasons.get(f"{ch.name}:none", 0) + 1
        if len(samples) < sample and f.annual:
            samples.append({
                "code": c, "name": f.name, "market": f.market and f.market.value,
                "price": s.close.value if s else None,
                "mcap": f.market_cap_reported.value,
                "last": f.annual[-1].model_dump(mode="json", include={
                    "fiscal_period", "revenue", "operating_profit", "eps", "cfo"}),
                "forecast": f.forecast and f.forecast.model_dump(mode="json", include={
                    "fiscal_period", "operating_profit", "eps", "irregular"}),
                "bs": f.balance_sheet and f.balance_sheet.model_dump(mode="json", include={
                    "total_assets", "equity"}),
            })
    out = {"n": n, "coverage": {k: (round(v / n, 4) if n else None) for k, v in cnt.items()},
           "counts": cnt, "none_reasons": dict(sorted(fail_reasons.items())), "samples": samples}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--source", default="kabutan")
    a = ap.parse_args(argv)
    print(json.dumps(report(Path(a.data_dir), a.source), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
