"""Bước 6 — thời điểm mua: bộ lọc +3% / BREAKOUT / BOTTOM trên OHLCV ngày.

Nguồn OHLCV: Yahoo chart v8 `query1.finance.yahoo.com/v8/finance/chart/{code}.T`
(không key, BẮT BUỘC User-Agent — skill market-data-sources §2.2). `close` và
`volume` của chart v8 đã điều chỉnh chia tách; không dùng adjclose (có cả cổ tức).

Mọi phép so sánh dùng phiên `t` (phiên cuối, đã đóng) với tập tham chiếu CHỈ gồm
các phiên TRƯỚC `t` (không look-ahead, pillar §4):
  gainer   : round(close_t/close_{t-1} − 1) ≥ 3%  VÀ  vol_t ≥ 2 × TB vol 20 phiên trước
  BREAKOUT : gainer VÀ close_t ≥ max(high) 252 phiên trước
  BOTTOM   : close_t ≤ đỉnh 52w × (1 − 40%), biên độ 10 phiên / 60 phiên ≤ 0,5,
             RSI14 từng ≤30 trong 20 phiên trước và giờ >30 và đang tăng,
             VÀ quý gần nhất vẫn qua bước 2 (truyền vào — None = không kết luận)
Thiếu lịch sử cho một điều kiện → điều kiện đó None, không đoán.
Tín hiệu này TÁCH khỏi phân tầng — không đổi tầng A/B/C.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from src.contracts import EntrySignal, EntrySignalResult
from src.params import SignalParams
from src.screen.numeric import rnd

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SOURCE = "Yahoo chart v8"
COLUMNS = ["date", "open", "high", "low", "close", "volume"]


# --------------------------------------------------------------- nguồn
def parse_chart_json(payload: dict) -> pd.DataFrame:
    """JSON chart v8 → DataFrame tăng dần theo ngày. Phiên close=null bị bỏ (không lấp 0)."""
    err = (payload.get("chart") or {}).get("error")
    if err:
        raise ValueError(f"chart v8 lỗi: {err}")
    res = payload["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    tz_off = (res.get("meta") or {}).get("gmtoffset", 9 * 3600)
    rows = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        d = datetime.fromtimestamp(t + tz_off, tz=timezone.utc).date()
        rows.append((d, q["open"][i], q["high"][i], q["low"][i], c, q["volume"][i]))
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def fetch_chart(code: str, user_agent: str, range_: str = "2y", session=None) -> pd.DataFrame:
    import requests

    s = session or requests.Session()
    r = s.get(CHART_URL.format(symbol=f"{code}.T"),
              params={"range": range_, "interval": "1d"},
              headers={"User-Agent": user_agent}, timeout=30)
    r.raise_for_status()
    return parse_chart_json(r.json())


def completed_sessions(df: pd.DataFrame, today: date, market_closed: bool) -> pd.DataFrame:
    """Bỏ phiên hôm nay khi sàn chưa đóng — nến đang chạy không phải dữ liệu đóng phiên."""
    if market_closed:
        return df[df["date"] <= today].reset_index(drop=True)
    return df[df["date"] < today].reset_index(drop=True)


# --------------------------------------------------------------- chỉ báo
def rsi_wilder(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_g = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_l = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_g / avg_l
    rsi = 100 - 100 / (1 + rs)
    rsi[(avg_l == 0) & avg_g.notna()] = 100.0
    return rsi


def _f(x) -> float | None:
    return None if x is None or pd.isna(x) else float(x)


def _and(*xs) -> bool | None:
    # Chuẩn hoá numpy bool trước: `np.False_ is False` là False → cổng sẽ lọt.
    xs = tuple(None if x is None else bool(x) for x in xs)
    if any(x is False for x in xs):
        return False
    if any(x is None for x in xs):
        return None
    return True


def evaluate(code: str, df: pd.DataFrame, p: SignalParams,
             growth_ok_latest_quarter: bool | None, source: str = SOURCE) -> EntrySignalResult:
    nd = p.round_ndigits
    notes: list[str] = []
    if len(df) < 2:
        return EntrySignalResult(code=code, source=source, notes=["chưa đủ 2 phiên"])
    t = len(df) - 1
    close_t = float(df["close"].iat[t])
    prev = _f(df["close"].iat[t - 1])

    change = rnd(close_t / prev - 1, nd) if prev else None
    price_up = None if change is None else change >= round(p.gainer_min_change, nd)

    vol_ratio = None
    w = p.volume_avg_window
    if t >= w:
        prior = df["volume"].iloc[t - w:t]
        avg = prior.mean() if prior.notna().all() else None
        if avg and avg > 0 and pd.notna(df["volume"].iat[t]):
            vol_ratio = rnd(float(df["volume"].iat[t]) / avg, nd)
    else:
        notes.append(f"chưa đủ {w} phiên cho TB khối lượng")
    vol_up = None if vol_ratio is None else vol_ratio >= round(p.volume_mult_min, nd)
    is_gainer = _and(price_up, vol_up)

    high_52w = None
    hw = p.high_window_days
    if t >= hw:
        high_52w = _f(df["high"].iloc[t - hw:t].max())
    else:
        notes.append(f"chưa đủ {hw} phiên cho đỉnh 52 tuần")
    at_high = None if high_52w is None else close_t >= high_52w
    is_breakout = _and(is_gainer, at_high)

    drawdown = rnd(close_t / high_52w - 1, nd) if high_52w else None
    deep = None if drawdown is None else drawdown <= -round(p.bottom_drawdown_min, nd)

    rng = (df["high"] - df["low"]) / df["close"]
    range_ratio = None
    if len(df) >= p.range_long_window:
        short = rng.iloc[-p.range_short_window:].mean()
        long_ = rng.iloc[-p.range_long_window:].mean()
        if long_ and long_ > 0:
            range_ratio = rnd(short / long_, nd)
    contracting = None if range_ratio is None else range_ratio <= round(p.range_contraction_max, nd)

    rsi = rsi_wilder(df["close"].astype(float), p.rsi_period)
    rsi_t, rsi_prev = _f(rsi.iat[t]), _f(rsi.iat[t - 1])
    lb = rsi.iloc[max(0, t - p.rsi_lookback_days):t]
    rebound = None
    if rsi_t is not None and rsi_prev is not None and lb.notna().any():
        rebound = bool(lb.min() <= p.rsi_oversold) and rsi_t > p.rsi_oversold and rsi_t > rsi_prev
    is_bottom = _and(deep, contracting, rebound, growth_ok_latest_quarter)
    if growth_ok_latest_quarter is None:
        notes.append("chưa biết quý gần nhất có qua bước 2 — BOTTOM không kết luận")

    if is_breakout:
        signal = EntrySignal.BREAKOUT
    elif is_bottom:
        signal = EntrySignal.BOTTOM
    else:
        signal = EntrySignal.NONE
    return EntrySignalResult(
        code=code, as_of=df["date"].iat[t], signal=signal, close=close_t, change_1d=change,
        volume_ratio=vol_ratio, high_52w=high_52w, drawdown_52w=drawdown,
        range_ratio=range_ratio, rsi=rnd(rsi_t, 2), is_gainer=is_gainer,
        is_breakout=is_breakout, is_bottom=is_bottom, source=source, notes=notes,
    )
