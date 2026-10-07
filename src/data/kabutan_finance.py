"""株探 `/stock/finance?code=` — một trang cho cả bước 1 (sàn, giá, 時価総額) và
phần lớn bước 2–3 (4 năm 売上高/営業益/修正1株益 + hàng 予 = dự báo công ty).

Nguồn đã kiểm chứng (skill market-data-sources §2.3b): robots chỉ chặn
`/94446337/` và `/search*`, `Crawl-delay: 3`; quét 492 mã hai lần không bị chặn.
Fetcher đọc robots.txt mỗi lần chạy và dùng max(crawl-delay nguồn, tham số).

Bẫy đã biết, đều được xử lý ở đây:
  · nhãn EPS là `修正1株益`, không có chữ "EPS";
  · ~26 <table> không id → nhận bảng theo NHÃN CỘT, không theo vị trí;
  · `<time>` đầu trang là của bảng chỉ số → lấy `<time>` cuối cùng TRƯỚC `前日比`;
  · ô `－` = không có dữ liệu → None, không bao giờ 0;
  · `変` = đổi niên độ → kỳ không dài 12 tháng (months=None / irregular);
  · header toàn `－` = nguồn không có dữ liệu, KHÁC với bố cục đổi.

Bảng 通期業績 + header đã kiểm trên HTML thật (tests/fixtures/kabutan).
Bảng 財務 (自己資本/総資産) và キャッシュフロー (営業CF): parser theo nhãn cột,
CHƯA có HTML thật để kiểm — thiếu bảng thì trường đó None (cổng → insufficient).

Đơn vị trang: 売上高/営業益/経常益/最終益/総資産/自己資本/CF = 百万円 → đổi ra yên.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from src.contracts import (
    AnnualResult,
    BalanceSheet,
    Forecast,
    Fundamentals,
    Market,
    PriceSnapshot,
    Quality,
    Sourced,
)

SOURCE = "株探 /stock/finance"
URL = "https://kabutan.jp/stock/finance?code={code}"
MILLION = 1_000_000
MARKETS = {"東証P": Market.PRIME, "東証S": Market.STANDARD, "東証G": Market.GROWTH}


class LayoutChanged(ValueError):
    """Trang tải được nhưng không nhận ra bố cục — KHÁC với 'nguồn không có dữ liệu'."""


# --------------------------------------------------------------- tiện ích
def _text(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "", fragment)
    t = re.sub(r"<[^>]+>", " ", t)
    t = htmllib.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip()


def num(s: str | None) -> float | None:
    """`"1,234.5"` → 1234.5 · `"－"`, `"-"`, `""`, rác → None (KHÔNG BAO GIỜ 0)."""
    if s is None:
        return None
    t = unicodedata.normalize("NFKC", s).replace(",", "").replace("+", "").strip()
    if t in ("", "-", "－", "—"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _yen(v: float | None) -> float | None:
    return None if v is None else v * MILLION


def _rows(table_html: str) -> list[list[str]]:
    out = []
    for tr in re.findall(r"<tr.*?</tr>", table_html, re.S):
        cells = [_text(c) for c in re.findall(r"<t[hd][^>]*>.*?</t[hd]>", tr, re.S)]
        if any(cells):
            out.append(cells)
    return out


def _find_table(page: str, required: tuple[str, ...]) -> list[list[str]] | None:
    """Bảng đầu tiên có hàng tiêu đề chứa ĐỦ mọi nhãn trong `required`."""
    for t in re.findall(r"<table.*?</table>", page, re.S):
        rows = _rows(t)
        if rows and all(any(r in h.replace(" ", "") for h in rows[0]) for r in required):
            return rows
    return None


def _col(header: list[str], label: str) -> int | None:
    for i, h in enumerate(header):
        if label in h.replace(" ", ""):
            return i
    return None


def _period(label: str) -> tuple[str | None, bool, bool]:
    """'I 予 変 2026.12' → ('2026.12', is_forecast, irregular)."""
    m = re.search(r"(\d{4})\.(\d{2})", label)
    return (m.group(0) if m else None), ("予" in label), ("変" in label)


def _announced(s: str | None) -> date | None:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2})", (s or "").strip())
    if not m:
        return None
    return date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _period_end(period: str) -> date:
    y, m = (int(x) for x in period.split("."))
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def market_cap_jpy(text: str) -> float | None:
    """'42兆555億円' → 42_0555_0000_0000. '－' → None."""
    t = text.replace(" ", "")
    if not re.search(r"\d", t):
        return None
    total, found = 0.0, False
    for amount, unit in re.findall(r"([\d,.]+)(兆|億|万)", t):
        v = num(amount)
        if v is None:
            return None
        total += v * {"兆": 1e12, "億": 1e8, "万": 1e4}[unit]
        found = True
    return total if found else None


# --------------------------------------------------------------- parse
def parse_finance_html(page: str, code: str, fetched: date | None = None
                       ) -> tuple[Fundamentals, PriceSnapshot]:
    if "決算期" not in page and "前日比" not in page:
        raise LayoutChanged(f"{code}: không thấy '決算期' lẫn '前日比'")

    # --- header: tên, sàn, giá, thời điểm, 時価総額
    name = None
    m = re.search(r"si_i1_1.*?<h2>.*?</span>(.*?)</h2>", page, re.S)
    if m:
        name = _text(m.group(1)) or None
    mk = re.search(r'<span class="market">(.*?)</span>', page, re.S)
    market = MARKETS.get(_text(mk.group(1)).replace(" ", "")) if mk else None

    i_price = page.find("前日比")
    as_of = None
    if i_price > 0:
        times = re.findall(r'<time[^>]*datetime="([^"]+)"', page[:i_price])
        if times:
            try:
                as_of = datetime.fromisoformat(times[-1]).date()
            except ValueError:
                as_of = None
    as_of = as_of or fetched   # header toàn － (nguồn trống) → kỳ = ngày tải
    if as_of is None:
        raise LayoutChanged(f"{code}: không xác định được kỳ dữ liệu (không <time>, không ngày tải)")

    pm = re.search(r'<span class="kabuka">(.*?)円?</span>', page, re.S)
    price = num(_text(pm.group(1)).replace("円", "")) if pm else None
    cm = re.search(r'class="v_zika2"[^>]*>(.*?)</td>', page, re.S)
    mcap = market_cap_jpy(_text(cm.group(1))) if cm else None

    # --- 通期業績 (đã kiểm trên HTML thật)
    annual: list[AnnualResult] = []
    forecast: Forecast | None = None
    rows = _find_table(page, ("決算期", "売上高", "営業益", "経常益", "修正1株益", "発表日"))
    if rows is not None:
        h = rows[0]
        ci = {k: _col(h, k) for k in ("売上高", "営業益", "最終益", "修正1株益", "発表日")}
        for r in rows[1:]:
            period, is_fc, irregular = _period(r[0])
            if period is None:
                continue

            def cell(k, r=r):
                i = ci[k]
                return r[i] if i is not None and i < len(r) else None

            rev, op = num(cell("売上高")), num(cell("営業益"))
            net, eps = num(cell("最終益")), num(cell("修正1株益"))
            ann = _announced(cell("発表日"))
            if is_fc:
                forecast = Forecast(fiscal_period=period, irregular=irregular,
                                    revenue=_yen(rev), operating_profit=_yen(op), eps=eps,
                                    announced=ann, source=SOURCE, as_of=as_of)
            else:
                annual.append(AnnualResult(
                    fiscal_period=period, months=None if irregular else 12,
                    revenue=_yen(rev), operating_profit=_yen(op), net_income=_yen(net),
                    eps=eps, announced=ann, source=SOURCE, as_of=as_of))
    annual.sort(key=lambda a: a.fiscal_period)

    # --- キャッシュフロー (CHƯA kiểm trên HTML thật)
    cf = _find_table(page, ("決算期", "営業CF"))
    if cf is not None:
        i_cfo = _col(cf[0], "営業CF")
        by_period = {}
        for r in cf[1:]:
            period, is_fc, _ = _period(r[0])
            if period and not is_fc and i_cfo is not None and i_cfo < len(r):
                by_period[period] = num(r[i_cfo])
        annual = [a.model_copy(update={"cfo": None if by_period.get(a.fiscal_period) is None
                                       else by_period[a.fiscal_period] * MILLION})
                  for a in annual]

    # --- 財務 (CHƯA kiểm trên HTML thật)
    bs = None
    fin = _find_table(page, ("決算期", "自己資本比率", "総資産", "自己資本"))
    if fin is not None:
        h = fin[0]
        i_ta = _col(h, "総資産")
        i_eq = next((i for i, x in enumerate(h) if x.replace(" ", "") == "自己資本"), None)
        last = None
        for r in fin[1:]:
            period, is_fc, _ = _period(r[0])
            if period and not is_fc:
                last = (period, r)
        if last and i_ta is not None and i_eq is not None:
            period, r = last
            ta = num(r[i_ta]) if i_ta < len(r) else None
            eq = num(r[i_eq]) if i_eq < len(r) else None
            bs = BalanceSheet(period_end=_period_end(period),
                              total_assets=None if ta is None else ta * MILLION,
                              equity=None if eq is None else eq * MILLION,
                              source=SOURCE, as_of=as_of)

    f = Fundamentals(
        code=code, name=name, market=market, annual=annual, forecast=forecast,
        balance_sheet=bs,
        market_cap_reported=Sourced.of(mcap, as_of, SOURCE, Quality.PROXY),
    )
    snap = PriceSnapshot(code=code, close=Sourced.of(price, as_of, SOURCE))
    return f, snap


# --------------------------------------------------------------- fetch + lưu
class KabutanFinanceFetcher:
    """Tải + parse + ghi data/fundamentals/kabutan/<code>.json và data/prices/kabutan/<code>.json."""

    def __init__(self, base_dir: str | Path, user_agent: str, min_delay_s: float = 3.2,
                 session=None):
        import requests

        from src.data.http import Throttle, robots_policy

        self.s = session or requests.Session()
        self.ua = user_agent
        ok, delay, why = robots_policy(URL.format(code="7203"), user_agent, self.s)
        print(f"kabutan robots: {why}")
        if not ok:
            raise PermissionError(f"kabutan robots: {why}")
        self.throttle = Throttle(max(min_delay_s, (delay or 0) + 0.2))
        self.base = Path(base_dir)

    def fetch(self, code: str) -> tuple[Fundamentals, PriceSnapshot]:
        self.throttle.wait()
        r = self.s.get(URL.format(code=code), headers={"User-Agent": self.ua}, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        return parse_finance_html(r.text, code, fetched=date.today())

    def save(self, f: Fundamentals, snap: PriceSnapshot) -> None:
        for sub, obj in (("fundamentals", f), ("prices", snap)):
            d = self.base / sub / "kabutan"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{f.code}.json").write_text(obj.model_dump_json(indent=2) + "\n",
                                              encoding="utf-8")


class KabutanPriceSource:
    """Giá từ trang 株探 đã lưu — dùng cho mã ngoài snapshot kiyohara (TOPIX500)."""

    name = "prices:kabutan"

    def __init__(self, base_dir: str | Path):
        self.dir = Path(base_dir) / "prices" / "kabutan"

    def snapshot(self, code: str) -> PriceSnapshot | None:
        p = self.dir / f"{code}.json"
        return PriceSnapshot.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


def main(argv: list[str] | None = None) -> int:
    """uv run python -m src.data.kabutan_finance --universe data/universe.json --shard 0/5"""
    import argparse

    from src.params import default_params

    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True)
    ap.add_argument("--shard", default="0/1", help="i/n: chỉ lấy mã có thứ tự % n == i")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    i, n = (int(x) for x in a.shard.split("/"))
    codes = [u["code"] for u in json.loads(Path(a.universe).read_text(encoding="utf-8"))["codes"]]
    codes = [c for k, c in enumerate(sorted(codes)) if k % n == i]
    if a.limit:
        codes = codes[:a.limit]
    p = default_params()
    fx = KabutanFinanceFetcher(a.data_dir, p.signals.user_agent)
    ok, empty, failures = 0, 0, []
    for c in codes:
        try:
            f, snap = fx.fetch(c)
        except LayoutChanged as e:
            failures.append(f"{c}: layout {e}")
            continue
        except Exception as e:  # noqa: BLE001 — đếm, không lấp
            failures.append(f"{c}: {type(e).__name__}")
            continue
        if not f.annual and snap.close.value is None:
            empty += 1        # nguồn không có dữ liệu cho mã này — không phải lỗi parser
        fx.save(f, snap)
        ok += 1
    print(f"kabutan shard {a.shard}: {ok}/{len(codes)} lưu, {empty} nguồn trống, "
          f"{len(failures)} lỗi")
    for fl in failures[:50]:
        print("  " + fl)
    return 0 if ok >= 0.8 * max(len(codes), 1) else 1


if __name__ == "__main__":
    raise SystemExit(main())
