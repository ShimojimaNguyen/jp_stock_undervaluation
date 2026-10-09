"""Kiểm chứng ĐỘC LẬP từng mã A/B/C — mỗi con số đối chiếu với một đường tính thứ hai
cùng bậc độ lớn (pillar §8). Test xanh chỉ chứng minh code làm đúng điều nó định làm;
file này hỏi: số ra có khớp thực tế từ một đường khác không.

  uv run python -m src.verify --export smoke-out/tenbagger-candidates.json --data-dir data

Mỗi check trả ok / mismatch / unchecked (thiếu đường đối chiếu — KHÔNG coi là ok).
Kết quả gắn vào labels của từng mã: "verify:ok" hoặc "verify:mismatch:<check>"; ghi đè
file export (idempotent: nhãn verify cũ bị xoá trước khi gắn lại).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TOL = {
    "market_cap": 0.10,      # 発行済−自己株 kỳ BS vs số cổ phiếu yfinance hiện tại: lệch vài %
    "revenue": 0.05,
    "operating_profit": 0.05,
    "cfo": 0.10,
    "equity_ratio_pt": 0.02,  # điểm % tuyệt đối
    "cagr": 0.01,             # chênh tuyệt đối của CAGR
}


def _rel(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return abs(a / b - 1)


def _status(diff: float | None, tol: float) -> str:
    if diff is None:
        return "unchecked"
    return "ok" if round(diff, 4) <= tol else "mismatch"


def verify_candidate(c: dict, yf_f: dict | None, yj: dict | None,
                     reported_mcap: float | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    sc = c["scorecard"]
    mcap = (sc.get("universe") or {}).get("market_cap", {}).get("value")
    d = _rel(mcap, reported_mcap)
    out["market_cap"] = {"ours": mcap, "other": reported_mcap, "diff": d,
                         "status": _status(d, TOL["market_cap"])}

    yj_rows = sorted((yj or {}).get("actuals") or [], key=lambda r: r["endDate"])
    yf_annual = (yf_f or {}).get("annual") or []
    if yj_rows and yf_annual:
        last = yj_rows[-1]
        period = last["endDate"][:4] + "." + last["endDate"][5:7]
        yf_last = next((a for a in yf_annual if a["fiscal_period"] == period), None)
        for key, yj_key, tol in (("revenue", "netSales", TOL["revenue"]),
                                 ("operating_profit", "operatingIncome", TOL["operating_profit"]),
                                 ("cfo", "operatingCashFlow", TOL["cfo"])):
            a = yf_last.get(key) if yf_last else None
            b = last.get(yj_key)
            dd = _rel(a, b)
            out[key] = {"period": period, "yfinance": a, "yahoo_jp": b, "diff": dd,
                        "status": _status(dd, tol)}
        bs = (yf_f or {}).get("balance_sheet") or {}
        ours = (bs.get("equity") / bs["total_assets"]) if bs.get("equity") and bs.get(
            "total_assets") else None
        theirs = last.get("equityRatio") / 100 if last.get("equityRatio") is not None else None
        dd = abs(ours - theirs) if ours is not None and theirs is not None else None
        out["equity_ratio"] = {"ours": ours, "yahoo_jp": theirs, "diff": dd,
                               "status": _status(dd, TOL["equity_ratio_pt"])}
        # Chuỗi doanh thu: MỌI năm trùng giữa hai nguồn phải khớp — CAGR tính trên chuỗi
        # này nên khớp chuỗi = CAGR có đường đối chiếu. Cần ≥2 năm trùng mới kết luận.
        yf_by = {a["fiscal_period"]: a.get("revenue") for a in yf_annual}
        diffs = []
        for r in yj_rows:
            per = r["endDate"][:4] + "." + r["endDate"][5:7]
            dd = _rel(yf_by.get(per), r.get("netSales"))
            if dd is not None:
                diffs.append((per, round(dd, 4)))
        if len(diffs) >= 2:
            worst = max(d for _, d in diffs)
            out["revenue_series"] = {"years": diffs, "diff": worst,
                                     "status": _status(worst, TOL["revenue"])}
        else:
            out["revenue_series"] = {"status": "unchecked", "years": diffs,
                                     "why": "ít hơn 2 năm trùng giữa hai nguồn"}
    else:
        for k in ("revenue", "operating_profit", "cfo", "equity_ratio", "revenue_series"):
            out[k] = {"status": "unchecked", "why": "thiếu dữ liệu Yahoo JP hoặc yfinance"}
    return out


def label_of(checks: dict[str, dict]) -> str:
    bad = [k for k, v in checks.items() if v["status"] == "mismatch"]
    if bad:
        return "verify:mismatch:" + ",".join(bad)
    if any(v["status"] == "unchecked" for v in checks.values()):
        return "verify:partial"
    return "verify:ok"


def reported_market_cap(code: str) -> float | None:
    """Đường độc lập: vốn hoá yfinance tự công bố (fast_info) — 1 request/mã."""
    try:
        import yfinance as yf

        v = yf.Ticker(f"{code}.T").fast_info.get("marketCap")
        return float(v) if v else None
    except Exception:  # noqa: BLE001 — không có đường đối chiếu = unchecked
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--offline", action="store_true", help="không gọi yfinance fast_info")
    a = ap.parse_args(argv)
    path = Path(a.export)
    exp = json.loads(path.read_text(encoding="utf-8"))
    base = Path(a.data_dir)
    summary = {"ok": 0, "partial": 0, "mismatch": 0}
    report = {}
    for c in exp.get("candidates", []):
        code = c["code"]
        yf_p = base / "fundamentals" / "yfinance" / f"{code}.json"
        yj_p = base / "forecasts" / "yahoojp" / f"{code}.json"
        yf_f = json.loads(yf_p.read_text(encoding="utf-8")) if yf_p.exists() else None
        yj = json.loads(yj_p.read_text(encoding="utf-8")) if yj_p.exists() else None
        mcap = None if a.offline else reported_market_cap(code)
        checks = verify_candidate(c, yf_f, yj, mcap)
        lab = label_of(checks)
        c["labels"] = [x for x in c.get("labels", []) if not x.startswith("verify:")] + [lab]
        summary[lab.split(":")[1]] += 1
        report[code] = checks
        print(f"VERIFY {code} {c.get('name')} {lab}")
        for k, v in checks.items():
            if v["status"] != "ok":
                print(f"   {k}: {json.dumps(v, ensure_ascii=False)}")
    exp.setdefault("notes", []).append(
        f"kiểm chứng độc lập: ok={summary['ok']} partial={summary['partial']} "
        f"mismatch={summary['mismatch']}")
    from src.contracts import CandidateExport

    CandidateExport.model_validate(exp)   # vẫn đúng schema bàn giao sau khi gắn nhãn
    path.write_text(json.dumps(exp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".verify.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("VERIFY SUMMARY", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
