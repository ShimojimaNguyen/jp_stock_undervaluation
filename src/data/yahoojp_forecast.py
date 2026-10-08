"""会社予想 + lịch sử sửa dự báo từ Yahoo!ファイナンス `/quote/{code}.T/performance`.

Đo trên Actions 2026-10-07 (src/data/probe.py, mã 1870): trang nhúng JSON (dấu
nháy escape) với HAI khối dự báo KHÁC NHAU — phải phân biệt:
  "forecast":{yearEndDate, netSales, operatingIncome, ordinaryIncome, netProfit,
              updatedDate}                    ← 会社予想, đơn vị YÊN  ✅ dùng
  "performanceForecastList":[{totalSampleCount, netSales…}]
                                              ← dự báo ANALYST, 百万円  ❌ bỏ
  "forecastRevisionList":[{forecastRevision:[{quarterEndDate, operatingIncome…}]}]
                                              ← lịch sử SỬA dự báo công ty → catalyst

Không có EPS dự báo trong khối "forecast". EPS dự phóng được SUY bằng code:
  EPS_fc = 純利益予想 × (EPS / 純利益 của năm thực hiện gần nhất, cùng nguồn)
→ tăng trưởng EPS = tăng trưởng 純利益 với cùng cơ sở số cổ phiếu, PER nhất quán.
Nhãn nguồn của Forecast ghi rõ phép suy này.

⛔ Nguồn CHẶN sau ~85 mã nếu quét dày (skill market-data-sources §2.2b) → chỉ hỏi
mã đã qua mọi check khác của bước 2 (awaiting_forecast), trần mỗi lần chạy, giãn ≥3s.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from src.contracts import (
    AnnualResult,
    CatalystEvent,
    CatalystStrength,
    CatalystType,
    Forecast,
    Fundamentals,
)

URL = "https://finance.yahoo.co.jp/quote/{code}.T/performance"
SOURCE = "Yahoo!ファイナンス 業績 (会社予想)"


def _json_after(text: str, key: str) -> object | None:
    """Đọc giá trị JSON ngay sau `"key":` bằng cách đếm ngoặc (bỏ qua chuỗi)."""
    i = text.find(f'"{key}":')
    if i < 0:
        return None
    j = i + len(key) + 3
    if j >= len(text) or text[j] not in "[{":
        return None
    open_, close = text[j], "]" if text[j] == "[" else "}"
    depth, k, in_str = 0, j, False
    while k < len(text):
        ch = text[k]
        if in_str:
            if ch == "\\":
                k += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == open_:
            depth += 1
        elif ch == close:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[j:k + 1])
                except json.JSONDecodeError:
                    return None
        k += 1
    return None


def _unescape(page: str) -> str:
    return page.replace('\\"', '"')


def parse_actuals(page: str) -> list[dict]:
    """Khối "performance":{"performance":[…]} — số THỰC HIỆN theo năm (fiscalQuarter Q4)."""
    t = _unescape(page)
    blk = _json_after(t, "performance")
    rows = blk.get("performance") if isinstance(blk, dict) else None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("fiscalQuarter") == "Q4"
            and r.get("endDate")]


def to_annuals(rows: list[dict], fetched: date) -> list[AnnualResult]:
    """Năm thực hiện CÙNG NGUỒN với 会社予想 → so dự báo với thực hiện cùng định nghĩa."""
    out: list[AnnualResult] = []
    prev: date | None = None
    for r in sorted(rows, key=lambda r: r["endDate"]):
        end = date.fromisoformat(r["endDate"])
        months = 12
        if prev is not None and abs((end - prev).days - 365) > 20:
            months = None
        rep = r.get("reportedDate")
        out.append(AnnualResult(
            fiscal_period=f"{end.year:04d}.{end.month:02d}", months=months,
            revenue=_num(r, "netSales"), operating_profit=_num(r, "operatingIncome"),
            net_income=_num(r, "netIncome"), eps=_num(r, "epsActual"),
            cfo=_num(r, "operatingCashFlow"),
            announced=date.fromisoformat(rep) if rep else None,
            source="Yahoo!ファイナンス 業績 (実績)", as_of=fetched))
        prev = end
    return out


def parse_performance(page: str) -> tuple[dict | None, list[dict]]:
    """→ (khối 会社予想 thô, danh sách sửa dự báo thô — mới → cũ)."""
    t = _unescape(page)
    fc = _json_after(t, "forecast")
    if not isinstance(fc, dict) or "yearEndDate" not in fc:
        fc = None
    revs: list[dict] = []
    lst = _json_after(t, "forecastRevisionList")
    if isinstance(lst, list):
        for y in lst:
            revs.extend(r for r in (y.get("forecastRevision") or []) if isinstance(r, dict))
    return fc, revs


def _num(d: dict, k: str) -> float | None:
    v = d.get(k)
    return float(v) if isinstance(v, int | float) else None


def to_forecast(raw: dict, f: Fundamentals, as_of: date) -> Forecast | None:
    try:
        ye = date.fromisoformat(raw["yearEndDate"])
    except (KeyError, ValueError):
        return None
    period = f"{ye.year:04d}.{ye.month:02d}"
    irregular = False
    if f.annual:
        ly, lm = (int(x) for x in f.annual[-1].fiscal_period.split("."))
        months = (ye.year - ly) * 12 + (ye.month - lm)
        irregular = months != 12 and months > 0
    eps = None
    np_fc = _num(raw, "netProfit")
    if f.annual and np_fc is not None:
        last = f.annual[-1]
        if last.eps and last.net_income and last.net_income > 0:
            eps = np_fc * (last.eps / last.net_income)
    upd = raw.get("updatedDate")
    return Forecast(
        fiscal_period=period, irregular=irregular,
        revenue=_num(raw, "netSales"), operating_profit=_num(raw, "operatingIncome"),
        eps=eps, announced=date.fromisoformat(upd) if upd else None,
        source=SOURCE + " · EPS suy từ 純利益予想 × EPS/純利益 năm gần nhất", as_of=as_of)


def revision_events(code: str, revs: list[dict], updated: date | None, cutoff_eff,
                    strength: dict[str, CatalystStrength]) -> list[CatalystEvent]:
    """Hai bản dự báo liền nhau cùng yearEndDate: OP tăng → 上方修正, giảm → 下方修正.

    Ngày công bố: chỉ biết chắc cho bản MỚI NHẤT (updatedDate). Giờ không biết →
    coi như sau 15:00 (hiệu lực phiên kế tiếp) — thận trọng, không look-ahead.
    """
    if len(revs) < 2 or updated is None:
        return []
    new, old = revs[0], revs[1]
    if new.get("yearEndDate") != old.get("yearEndDate"):
        return []
    a, b = _num(new, "operatingIncome"), _num(old, "operatingIncome")
    if a is None or b is None or a == b:
        return []
    t = CatalystType.UPWARD_REVISION if a > b else CatalystType.DOWNWARD_REVISION
    eff = cutoff_eff(datetime.combine(updated, time(23, 59)))
    return [CatalystEvent(
        code=code, type=t, strength=strength[t.value], title=None,
        disclosed_at=None, effective_date=eff, method="code", source=SOURCE,
        detail=f"営業利益予想 {b:.0f} → {a:.0f} ({new.get('yearEndDate')})")]


# --------------------------------------------------------------- lưu / tải
class YahooJPForecastStore:
    """data/forecasts/yahoojp/<code>.json — thô từ nguồn, mỗi nguồn một thư mục."""

    def __init__(self, base_dir: str | Path):
        self.dir = Path(base_dir) / "forecasts" / "yahoojp"

    def get(self, code: str) -> dict | None:
        p = self.dir / f"{code}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, code: str, raw: dict | None, revs: list[dict], fetched: date,
            actuals: list[dict] | None = None) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{code}.json").write_text(json.dumps(
            {"fetched": fetched.isoformat(), "forecast": raw, "revisions": revs,
             "actuals": actuals or []},
            ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """uv run python -m src.data.yahoojp_forecast --from data/tenbagger-candidates.sample.json"""
    import argparse

    import requests

    from src.data.http import Throttle, robots_policy
    from src.params import default_params

    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True,
                    help="file export có awaiting_forecast (mã cần 会社予想)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--max", type=int, default=60, help="trần mỗi lần chạy (nguồn chặn ~85)")
    ap.add_argument("--refresh-days", type=int, default=7)
    ap.add_argument("--delay", type=float, default=3.0)
    a = ap.parse_args(argv)
    ua = default_params().signals.user_agent
    exp = json.loads(Path(a.src).read_text(encoding="utf-8"))
    codes = [c["code"] for c in exp.get("awaiting_forecast", [])] + \
            [c["code"] for c in exp.get("candidates", [])]
    store = YahooJPForecastStore(a.data_dir)
    today = date.today()
    todo = []
    for c in dict.fromkeys(codes):
        old = store.get(c)
        if old and (today - date.fromisoformat(old["fetched"])) < timedelta(days=a.refresh_days):
            continue
        todo.append(c)
    todo = todo[:a.max]
    s = requests.Session()
    ok, why = robots_policy(URL.format(code="7203"), ua, s)[0::2]
    print(f"yahoojp robots: {why}")
    if not ok:
        return 1
    th = Throttle(a.delay)
    got, failures = 0, []
    for c in todo:
        th.wait()
        try:
            r = s.get(URL.format(code=c), headers={"User-Agent": ua}, timeout=30)
        except Exception as e:  # noqa: BLE001
            failures.append(f"{c}: {type(e).__name__}")
            continue
        if r.status_code != 200:
            failures.append(f"{c}: HTTP {r.status_code}")
            if r.status_code >= 500 and len(failures) >= 3:
                print("nguồn trả 5xx liên tiếp — có thể đã bị chặn, DỪNG (không thử dồn)")
                break
            continue
        raw, revs = parse_performance(r.text)
        store.put(c, raw, revs, today, parse_actuals(r.text))
        got += 1
    print(f"yahoojp forecast: {got}/{len(todo)} (cần {len(codes)}, trần {a.max}), "
          f"lỗi {failures[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
