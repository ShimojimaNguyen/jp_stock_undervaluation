"""Bước 5 — catalyst từ danh sách công bố theo ngày của TDnet.

Nguồn: https://www.release.tdnet.info/inbs/I_list_{page:03d}_{YYYYMMDD}.html
(trang công khai 適時開示情報閲覧サービス). CHỈ lưu metadata (giờ, mã, tên, tiêu
đề, URL PDF, sàn) — không tải PDF, không phát hành lại nội dung.

TRẠNG THÁI KIỂM CHỨNG (2026-10-03): proxy của môi trường dựng code chặn
www.release.tdnet.info, nên robots.txt và markup CHƯA đọc được thật. Parser
viết theo cấu trúc bảng `main-list-table` / class `kj*` đã biết; fixture test
là bản dựng tay theo cấu trúc đó. Lần chạy thật đầu tiên phải kiểm lại cả hai.
Vì vậy `fetch_day()` tự đọc robots.txt mỗi lần chạy và TỪ CHỐI khi bị cấm hoặc
không đọc được (trừ 404 = không tuyên bố hạn chế) — cơ chế thay cho lời hứa.

Phân loại theo thứ tự:
  1. rule trên tiêu đề (tất định) — có thể ra nhiều loại cho một tiêu đề;
  2. tiêu đề KHÔNG khớp rule nào → hàng đợi Jev `choice` có `none_of_these`
     (chạy batch ở src/jev, không ở đây).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from src.contracts import CatalystEvent, CatalystStrength, CatalystType, QuarterResult
from src.data.http import robots_policy
from src.params import CatalystParams, PrimeParams

SOURCE = "TDnet 適時開示情報閲覧サービス"

# Thứ tự quan trọng: loại cụ thể/âm trước. Một tiêu đề có thể khớp nhiều rule
# ("業績予想の上方修正及び増配に関するお知らせ" → upward_revision + dividend_increase).
TITLE_RULES: list[tuple[CatalystType, re.Pattern]] = [
    (CatalystType.UPWARD_REVISION, re.compile(r"上方修正")),
    (CatalystType.DOWNWARD_REVISION, re.compile(r"下方修正")),
    (CatalystType.DIVIDEND_INCREASE, re.compile(r"増配")),
    (CatalystType.DIVIDEND_CUT, re.compile(r"減配|無配")),
    (CatalystType.TENDER_OFFER, re.compile(r"公開買付")),
    (CatalystType.BUYBACK, re.compile(r"自己株式の?取得")),
    (CatalystType.MID_TERM_PLAN, re.compile(r"中期経営計画")),
    (CatalystType.MARKET_CHANGE, re.compile(r"市場区分.{0,4}変更")),
    (CatalystType.STOCK_SPLIT, re.compile(r"株式分割")),
    (CatalystType.EXTRAORDINARY_LOSS, re.compile(r"特別損失")),
]
# 業績予想の修正 mà tiêu đề không nói hướng: hướng là SỐ → không hỏi Jev,
# phải đọc từ 決算短信/PDF bằng code (chưa cài) → giữ loại riêng, bậc LOW.
REVISION_NO_DIRECTION = re.compile(r"予想.{0,6}修正")


@dataclass(frozen=True)
class Disclosure:
    disclosed_at: datetime
    code: str          # 4 ký tự (mã 5 ký tự của TDnet bỏ số kiểm tra cuối)
    name: str
    title: str
    url: str | None
    exchange: str | None

    def to_json(self) -> dict:
        return {"disclosed_at": self.disclosed_at.isoformat(), "code": self.code,
                "name": self.name, "title": self.title, "url": self.url,
                "exchange": self.exchange}

    @classmethod
    def from_json(cls, d: dict) -> Disclosure:
        return cls(datetime.fromisoformat(d["disclosed_at"]), d["code"], d["name"],
                   d["title"], d.get("url"), d.get("exchange"))


# --------------------------------------------------------------- parse
class _ListParser(HTMLParser):
    """Đọc các <tr> có <td class="... kjTime|kjCode|kjName|kjTitle|kjPlace">."""

    FIELDS = ("kjTime", "kjCode", "kjName", "kjTitle", "kjPlace")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._field: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row = {}
        elif tag == "td" and self._row is not None:
            cls = (a.get("class") or "").split()
            self._field = next((f for f in self.FIELDS if f in cls), None)
            if self._field:
                self._row.setdefault(self._field, "")
        elif tag == "a" and self._row is not None and self._field == "kjTitle":
            self._row["href"] = a.get("href")

    def handle_endtag(self, tag):
        if tag == "td":
            self._field = None
        elif tag == "tr" and self._row is not None:
            if "kjCode" in self._row and "kjTitle" in self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._row is not None and self._field:
            self._row[self._field] += data


def parse_list_html(html: str, day: date, base_url: str) -> list[Disclosure]:
    p = _ListParser()
    p.feed(html)
    out = []
    for r in p.rows:
        raw_code = r["kjCode"].strip()
        t = r.get("kjTime", "").strip()
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
        if not raw_code or not m:
            continue   # dòng hỏng: bỏ, KHÔNG đoán giờ
        code = raw_code[:4] if len(raw_code) == 5 else raw_code
        href = r.get("href")
        out.append(Disclosure(
            disclosed_at=datetime(day.year, day.month, day.day, int(m.group(1)), int(m.group(2))),
            code=code,
            name=r.get("kjName", "").strip(),
            title=re.sub(r"\s+", " ", r["kjTitle"]).strip(),
            url=urljoin(base_url, href) if href else None,
            exchange=(r.get("kjPlace") or "").strip() or None,
        ))
    return out


# --------------------------------------------------------------- lịch phiên
def is_trading_day(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def next_trading_day(d: date, holidays: set[date]) -> date:
    n = d + timedelta(days=1)
    while not is_trading_day(n, holidays):
        n += timedelta(days=1)
    return n


def effective_date(disclosed_at: datetime, cutoff_hhmm: str, holidays: set[date]) -> date:
    """Công bố từ cutoff trở đi, hoặc vào ngày nghỉ → phiên giao dịch kế tiếp."""
    hh, mm = (int(x) for x in cutoff_hhmm.split(":"))
    d = disclosed_at.date()
    if not is_trading_day(d, holidays):
        return next_trading_day(d, holidays)
    if (disclosed_at.hour, disclosed_at.minute) >= (hh, mm):
        return next_trading_day(d, holidays)
    return d


def holidays_of(p: CatalystParams) -> set[date]:
    return {date.fromisoformat(s) for s in p.market_holidays}


# --------------------------------------------------------------- phân loại
def classify_title(title: str) -> list[CatalystType]:
    hits = [t for t, rx in TITLE_RULES if rx.search(title)]
    if not hits and REVISION_NO_DIRECTION.search(title):
        hits = [CatalystType.FORECAST_REVISION]
    return hits


def _strength(t: CatalystType, p: CatalystParams) -> CatalystStrength:
    return p.strength.get(t.value, CatalystStrength.LOW)


def classify(disclosures: list[Disclosure], p: CatalystParams
             ) -> tuple[list[CatalystEvent], list[Disclosure]]:
    """→ (sự kiện theo rule, tiêu đề không khớp rule nào — chờ Jev)."""
    hol = holidays_of(p)
    events, unmatched = [], []
    for d in disclosures:
        types = classify_title(d.title)
        if not types:
            unmatched.append(d)
            continue
        for t in types:
            events.append(CatalystEvent(
                code=d.code, type=t, strength=_strength(t, p), title=d.title,
                disclosed_at=d.disclosed_at,
                effective_date=effective_date(d.disclosed_at, p.cutoff_hhmm, hol),
                method="rule", source=SOURCE, url=d.url,
            ))
    return events, unmatched


def event_from_jev_choice(d: Disclosure, choice: str | None, p: CatalystParams
                          ) -> CatalystEvent | None:
    """Kết quả Jev (đã qua ngưỡng tin cậy) → sự kiện. none_of_these/None → không có sự kiện."""
    if choice is None or choice == "none_of_these":
        return None
    try:
        t = CatalystType(choice)
    except ValueError:
        return None
    return CatalystEvent(
        code=d.code, type=t, strength=_strength(t, p), title=d.title,
        disclosed_at=d.disclosed_at,
        effective_date=effective_date(d.disclosed_at, p.cutoff_hhmm, holidays_of(p)),
        method="jev", source=SOURCE, url=d.url,
    )


# --------------------------------------------------------------- code-catalyst
def upgrade_likelihood(quarters: list[QuarterResult], annual_op: dict[str, float | None],
                       p: CatalystParams, ndigits: int = 4
                       ) -> tuple[bool | None, dict]:
    """"Có khả năng nâng dự báo" — tính bằng code, không hỏi Jev.

    進捗率 hiện tại = OP luỹ kế quý q / dự báo OP năm.
    Chuẩn lịch sử   = TB (OP luỹ kế quý q / OP THỰC HIỆN cả năm) của các năm
                      ĐÃ KẾT THÚC trước năm hiện tại (không look-ahead).
    True khi hiện tại ≥ chuẩn + margin. Thiếu lịch sử → None.
    """
    if not quarters:
        return None, {"reason": "không có quý"}
    cur = quarters[-1]
    if cur.quarter == 4:
        return None, {"reason": "Q4 = cả năm, không còn dự báo để nâng"}
    if cur.cumulative_operating_profit is None or not cur.full_year_op_forecast \
            or cur.full_year_op_forecast <= 0:
        return None, {"reason": "thiếu OP luỹ kế hoặc dự báo năm"}
    progress = cur.cumulative_operating_profit / cur.full_year_op_forecast
    hist = []
    for q in quarters[:-1]:
        if q.quarter != cur.quarter or q.fiscal_period >= cur.fiscal_period:
            continue
        actual = annual_op.get(q.fiscal_period)
        if q.cumulative_operating_profit is None or actual is None or actual <= 0:
            continue
        hist.append(q.cumulative_operating_profit / actual)
    detail = {"progress": round(progress, ndigits), "history_n": len(hist)}
    if len(hist) < p.upgrade_min_history_years:
        detail["reason"] = f"cần ≥{p.upgrade_min_history_years} năm lịch sử cùng quý"
        return None, detail
    avg = sum(hist) / len(hist)
    detail["history_avg"] = round(avg, ndigits)
    return round(progress - avg, ndigits) >= round(p.upgrade_progress_margin, ndigits), detail


def prime_eligibility(pp: PrimeParams, *, shareholders: int | None, tradable_units: int | None,
                      tradable_market_cap: float | None, tradable_ratio: float | None,
                      market_cap: float | None, net_assets: float | None,
                      profit_2y_sum: float | None) -> tuple[bool | None, dict[str, bool | None]]:
    """Kiểm tiêu chí lên Prime bằng code. Thiếu tiêu chí nào → kết luận None."""
    def chk(v, th):
        return None if v is None else v >= th

    checks = {
        "shareholders": chk(shareholders, pp.shareholders_min),
        "tradable_units": chk(tradable_units, pp.tradable_units_min),
        "tradable_market_cap": chk(tradable_market_cap, pp.tradable_market_cap_min_jpy),
        "tradable_ratio": chk(None if tradable_ratio is None else round(tradable_ratio, 4),
                              pp.tradable_ratio_min),
        "market_cap": chk(market_cap, pp.market_cap_min_jpy),
        "net_assets": chk(net_assets, pp.net_assets_min_jpy),
        "profit_2y_sum": chk(profit_2y_sum, pp.profit_2y_sum_min_jpy),
    }
    if any(v is False for v in checks.values()):
        return False, checks
    if any(v is None for v in checks.values()):
        return None, checks
    return True, checks


# --------------------------------------------------------------- fetch (mạng)
def fetch_day(day: date, p: CatalystParams, max_pages: int = 30, session=None
              ) -> list[Disclosure]:
    """Tải mọi trang danh sách của một ngày. Giãn request_delay_s giữa các trang."""
    import requests

    s = session or requests.Session()
    ok, _, why = robots_policy(urljoin(p.tdnet_base_url, f"I_list_001_{day:%Y%m%d}.html"),
                               p.tdnet_user_agent, s)
    if not ok:
        raise PermissionError(f"TDnet robots: {why} — dừng")
    out: list[Disclosure] = []
    for page in range(1, max_pages + 1):
        url = urljoin(p.tdnet_base_url, f"I_list_{page:03d}_{day:%Y%m%d}.html")
        r = s.get(url, headers={"User-Agent": p.tdnet_user_agent}, timeout=30)
        if r.status_code == 404:
            break
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        rows = parse_list_html(r.text, day, url)
        if not rows:
            break
        out.extend(rows)
        time.sleep(p.request_delay_s)
    return out


def write_day(day: date, rows: list[Disclosure], base: str | Path) -> Path:
    """Idempotent theo ngày: ghi đè đúng file của ngày đó (metadata, không PDF)."""
    d = Path(base)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{day:%Y-%m-%d}.jsonl"
    path.write_text("".join(json.dumps(r.to_json(), ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")
    return path


def read_day(path: str | Path) -> list[Disclosure]:
    return [Disclosure.from_json(json.loads(line))
            for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """uv run python -m src.catalyst.tdnet --days 5 — tải N ngày gần nhất (idempotent theo ngày)."""
    import argparse
    from datetime import timedelta as _td

    from src.params import default_params

    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--out", default="data/tdnet")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD, mặc định hôm nay")
    a = ap.parse_args(argv)
    p = default_params().catalyst
    end = date.fromisoformat(a.end) if a.end else date.today()
    total, failed = 0, []
    for k in range(a.days):
        d = end - _td(days=k)
        if d.weekday() >= 5:
            continue
        try:
            rows = fetch_day(d, p)
        except PermissionError:
            raise
        except Exception as e:  # noqa: BLE001 — một ngày lỗi không xoá ngày khác
            failed.append(f"{d}: {type(e).__name__}")
            continue
        write_day(d, rows, a.out)
        total += len(rows)
    print(f"tdnet: {total} công bố, lỗi {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
