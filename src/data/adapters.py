"""Adapter nguồn dữ liệu — interface + bản cài đặt đã có nguồn thật.

Ranh giới:
  · Giá hằng ngày: TIÊU THỤ snapshot của repo kiyohara
    (`data/snapshots-kabutan-latest.json`), không viết fetcher trùng.
    Lưu ý đã đo: snapshot đó chỉ phủ TOPIX Core30/Large70/Mid400 (~492 mã),
    KHÔNG phải toàn TSE → phần lớn mã vốn hoá 50–1000億円 sẽ thiếu giá.
  · Cơ bản (4 năm doanh thu, dự báo, BS, CFO, 大株主): CHƯA CÓ NGUỒN.
    `JsonFundamentalsSource` đọc file đã chuẩn hoá theo `Fundamentals`
    (data/fundamentals/<source>/<code>.json — mỗi nguồn một thư mục riêng);
    fetcher thật (EDINET API cần key, hay 株探 finance) là quyết định của user.
    Hai lớp stub bên dưới từ chối chạy thay vì trả dữ liệu rỗng trông như thật.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from src.contracts import Fundamentals, PriceSnapshot, Sourced

ROOT = Path(__file__).resolve().parent.parent.parent


class PriceSource(Protocol):
    name: str

    def snapshot(self, code: str) -> PriceSnapshot | None: ...


class FundamentalsSource(Protocol):
    name: str

    def get(self, code: str) -> Fundamentals | None: ...


# ----------------------------------------------------------------- giá
def _default_kiyohara_path() -> Path:
    env = os.environ.get("KIYOHARA_SNAPSHOT")
    if env:
        return Path(env)
    return ROOT.parent / "kiyohara" / "data" / "snapshots-kabutan-latest.json"


class KiyoharaSnapshotSource:
    """Đọc snapshot giá/PER của kiyohara. Không ghi gì, không gọi mạng."""

    name = "kiyohara:snapshots-kabutan-latest"

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else _default_kiyohara_path()
        self._rows: dict[str, dict] | None = None
        self.meta: dict = {}

    def _load(self) -> dict[str, dict]:
        if self._rows is None:
            if not self.path.exists():
                raise FileNotFoundError(
                    f"không thấy snapshot kiyohara tại {self.path} — đặt KIYOHARA_SNAPSHOT")
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.meta = {k: v for k, v in d.items() if k != "snapshots"}
            self._rows = {str(r["code"]): r for r in d.get("snapshots", [])}
        return self._rows

    def codes(self) -> list[str]:
        return sorted(self._load())

    def snapshot(self, code: str) -> PriceSnapshot | None:
        r = self._load().get(code)
        if r is None:
            return None
        as_of = _parse_date(r.get("updatedAt")) or _parse_date(self.meta.get("fetchedAt"))
        src = f"{self.name}:{r.get('source') or self.meta.get('sourceId') or '?'}"
        per = r.get("per") if r.get("perBasis") == "予想" else None
        return PriceSnapshot(
            code=code,
            close=Sourced.of(r.get("price"), as_of, src),
            per_forecast=Sourced.of(per, as_of, src),
        )


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


# ----------------------------------------------------------------- cơ bản
class JsonFundamentalsSource:
    """data/fundamentals/<source>/<code>.json, đã validate theo `Fundamentals`."""

    def __init__(self, source: str, base: str | Path | None = None):
        self.name = f"fundamentals:{source}"
        self.dir = Path(base or ROOT / "data" / "fundamentals") / source

    def get(self, code: str) -> Fundamentals | None:
        p = self.dir / f"{code}.json"
        if not p.exists():
            return None
        return Fundamentals.model_validate_json(p.read_text(encoding="utf-8"))

    def codes(self) -> list[str]:
        if not self.dir.exists():
            return []
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def write(self, f: Fundamentals) -> Path:
        """Idempotent: ghi đè đúng file của mã đó."""
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / f"{f.code}.json"
        p.write_text(f.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return p


class EdinetFundamentalsSource:
    """EDINET API v2 (有価証券報告書/四半期 XBRL) — CẦN `EDINET_API_KEY`.

    Cho: BS (流動資産/投資有価証券/負債合計/自己資本), CFO, 発行済/自己株,
    大株主 (大株主の状況), 役員持株 (役員の状況). KHÔNG cho dự báo công ty
    (đó là 決算短信 trên TDnet). Chưa cài đặt — chờ user cấp key và chốt nguồn.
    """

    name = "fundamentals:edinet"

    def get(self, code: str) -> Fundamentals | None:  # pragma: no cover - stub
        raise NotImplementedError("EDINET adapter chưa cài đặt — cần EDINET_API_KEY + quyết định của user")


class KabutanFinanceSource:
    """株探 /stock/finance — doanh thu/OP/EPS nhiều năm + dự báo (Crawl-delay 3s).

    Cho: 通期業績 (売上高/営業益/修正1株益, hàng 予 = dự báo công ty). KHÔNG
    cho BS chi tiết / 投資有価証券 / 大株主 → vẫn cần EDINET cho net cash 清原.
    Chưa cài đặt — kiyohara đã có parser trang này (fetch_snapshots.ts); nên
    mở rộng ở ĐÓ thay vì viết parser thứ hai (một bộ luật, một bản).
    """

    name = "fundamentals:kabutan"

    def get(self, code: str) -> Fundamentals | None:  # pragma: no cover - stub
        raise NotImplementedError("Kabutan finance adapter chưa cài đặt — xem docstring")

