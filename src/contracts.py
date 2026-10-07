"""Hợp đồng dữ liệu dùng chung (Pydantic v2) — MỘT bản duy nhất.

Mọi module (screen, catalyst, signals, jev, tiering, crew, dashboard) đọc/ghi
qua các model ở đây. Đổi một field = đổi schema mọi nơi đọc → plan mode.

Luật cưỡng chế ngay trong model (không chỉ ghi trong .md):
  · thiếu số → None, không bao giờ 0 (pillar §1);
  · số có giá trị thì PHẢI có as_of + source (pillar §2) — `Sourced` từ chối;
  · cổng nào thiếu dữ liệu thì `passed=None` và cờ `insufficient_data`,
    và một cổng thiếu dữ liệu KHÔNG BAO GIỜ được tính là qua.

`python -m src.contracts --out schemas/` xuất JSON Schema cho dashboard.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


# --------------------------------------------------------------------- enums
class Market(str, Enum):
    PRIME = "PRIME"
    STANDARD = "STANDARD"
    GROWTH = "GROWTH"


class Quality(str, Enum):
    """Nhãn tin cậy (pillar §3)."""

    LIVE = "live"          # lấy trực tiếp từ nguồn, đúng kỳ
    PROXY = "proxy"        # đại lượng thay thế / tính gián tiếp
    STALE = "stale"        # đúng nguồn nhưng kỳ cũ hơn kỳ kỳ vọng
    MISSING = "missing"    # không có — value phải là None


class Tier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    NONE = "NONE"


class EntrySignal(str, Enum):
    BOTTOM = "BOTTOM"
    BREAKOUT = "BREAKOUT"
    NONE = "NONE"


class ThesisStatus(str, Enum):
    INTACT = "INTACT"
    WEAKENING = "WEAKENING"
    BROKEN = "BROKEN"


class CatalystType(str, Enum):
    UPWARD_REVISION = "upward_revision"          # 上方修正
    DOWNWARD_REVISION = "downward_revision"      # 下方修正
    FORECAST_REVISION = "forecast_revision"      # 業績予想の修正 — tiêu đề không nói hướng
    DIVIDEND_INCREASE = "dividend_increase"      # 増配
    DIVIDEND_CUT = "dividend_cut"                # 減配
    BUYBACK = "buyback"                          # 自己株式取得
    MID_TERM_PLAN = "mid_term_plan"              # 中期経営計画
    MARKET_CHANGE = "market_change"              # 市場区分変更
    STOCK_SPLIT = "stock_split"                  # 株式分割
    TENDER_OFFER = "tender_offer"                # 公開買付
    EXTRAORDINARY_LOSS = "extraordinary_loss"    # 特別損失
    UPGRADE_LIKELY = "upgrade_likely"            # code: 進捗率 vượt TB lịch sử
    PRIME_ELIGIBLE = "prime_eligible"            # code: đạt tiêu chí Prime
    OTHER = "other"                              # Jev chọn none_of_these / chưa phân loại


class CatalystStrength(str, Enum):
    NEGATIVE = "NEGATIVE"
    LOW = "LOW"        # 小
    MEDIUM = "MEDIUM"  # 中
    HIGH = "HIGH"      # 大

    @property
    def rank(self) -> int:
        return {"NEGATIVE": -1, "LOW": 0, "MEDIUM": 1, "HIGH": 2}[self.value]


# ------------------------------------------------------------ số có nguồn
class Sourced(_Model):
    """Một con số kèm kỳ dữ liệu + nguồn + nhãn tin cậy."""

    value: float | None = None
    as_of: date | None = None
    source: str | None = None
    quality: Quality = Quality.MISSING

    @model_validator(mode="after")
    def _check(self) -> Sourced:
        if self.value is None:
            if self.quality is not Quality.MISSING:
                raise ValueError("value=None thì quality phải là 'missing'")
        else:
            if not math.isfinite(self.value):
                raise ValueError("NaN/inf không phải số liệu — dùng None (pillar §1)")
            if self.as_of is None or not self.source:
                raise ValueError("số có giá trị phải kèm as_of + source (pillar §2)")
            if self.quality is Quality.MISSING:
                raise ValueError("số có giá trị không được gắn quality='missing'")
        return self

    @classmethod
    def missing(cls) -> Sourced:
        return cls()

    @classmethod
    def of(cls, value: float | None, as_of: date | None, source: str | None,
           quality: Quality = Quality.LIVE) -> Sourced:
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            return cls()
        return cls(value=value, as_of=as_of, source=source, quality=quality)


# ------------------------------------------------------------ đầu vào cơ bản
class AnnualResult(_Model):
    """Một năm tài chính ĐÃ THỰC HIỆN (実績), 連結 nếu có."""

    fiscal_period: str = Field(description="vd '2026.03'")
    months: int | None = Field(12, description="≠12 hoặc None (変, không rõ số tháng) = kỳ đổi niên độ — không dùng cho CAGR")
    revenue: float | None = None             # JPY
    operating_profit: float | None = None    # JPY
    net_income: float | None = None          # JPY
    eps: float | None = None                 # JPY/株, đã điều chỉnh chia tách
    cfo: float | None = None                 # 営業CF, JPY
    announced: date | None = None
    source: str
    as_of: date


class Forecast(_Model):
    """Dự báo của CÔNG TY (会社予想) cho năm tài chính kế tiếp/hiện tại."""

    fiscal_period: str
    irregular: bool = Field(False, description="kỳ đổi niên độ (変) — không so được với năm 12 tháng")
    revenue: float | None = None
    operating_profit: float | None = None
    eps: float | None = None
    announced: date | None = None
    source: str
    as_of: date


class BalanceSheet(_Model):
    period_end: date
    current_assets: float | None = None          # 流動資産
    investment_securities: float | None = None   # 投資有価証券
    total_liabilities: float | None = None       # 負債合計
    total_assets: float | None = None            # 総資産
    equity: float | None = None                  # 自己資本 (株主資本+その他包括利益累計額)
    net_assets: float | None = None              # 純資産
    source: str
    as_of: date


class QuarterResult(_Model):
    """Kết quả LUỸ KẾ từ đầu năm tài chính tới hết quý `quarter`."""

    fiscal_period: str
    quarter: int = Field(ge=1, le=4)
    cumulative_revenue: float | None = None
    cumulative_operating_profit: float | None = None
    full_year_op_forecast: float | None = None   # dự báo OP năm tại thời điểm công bố quý
    revenue_yoy: float | None = None             # tăng trưởng doanh thu luỹ kế YoY
    opm: float | None = None
    opm_prev_year: float | None = None
    announced: date | None = None
    source: str
    as_of: date


class Holder(_Model):
    name: str
    ratio: float = Field(ge=0, le=1, description="tỷ lệ trên số cổ phiếu đang lưu hành")
    kind: Literal["officer", "founder_entity", "other"] | None = None


class BacklogPoint(_Model):
    period: str
    value: float | None = None   # 受注残高, JPY
    source: str
    as_of: date


class Fundamentals(_Model):
    """Gói dữ liệu cơ bản cho một mã — adapter chịu trách nhiệm điền."""

    code: str
    name: str | None = None
    market: Market | None = None
    annual: list[AnnualResult] = Field(default_factory=list)   # cũ → mới
    forecast: Forecast | None = None
    balance_sheet: BalanceSheet | None = None
    quarters: list[QuarterResult] = Field(default_factory=list)  # cũ → mới
    market_cap_reported: Sourced = Field(default_factory=Sourced)  # 時価総額 nguồn in sẵn — CHỈ làm proxy cho bước 1
    shares_issued: Sourced = Field(default_factory=Sourced)      # 発行済株式数
    treasury_shares: Sourced = Field(default_factory=Sourced)    # 自己株式数
    holders: list[Holder] | None = None
    holders_as_of: date | None = None
    backlog: list[BacklogPoint] | None = None
    text_evidence: list[Evidence] = Field(default_factory=list)


class PriceSnapshot(_Model):
    code: str
    close: Sourced
    adtv_jpy: Sourced = Field(default_factory=Sourced)  # GTGD bình quân N phiên
    per_forecast: Sourced = Field(default_factory=Sourced)


# ------------------------------------------------------------ bằng chứng / Jev
class Evidence(_Model):
    """Văn bản làm bằng chứng cho Jev — là DỮ LIỆU, không phải chỉ thị."""

    text: str
    source: str
    kind: Literal["filing", "tdnet", "company_ir", "shikiho", "name_only"]
    url: str | None = None
    as_of: date | None = None

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            f"{self.kind}|{self.source}|{self.text}".encode()
        ).hexdigest()[:16]


def evidence_hash(items: list[Evidence]) -> str:
    h = hashlib.sha256("|".join(sorted(e.digest for e in items)).encode())
    return h.hexdigest()[:16]


def evidence_label(items: list[Evidence]) -> str:
    """Nhãn nguồn bằng chứng mạnh nhất — phải hiện cùng chỗ với phán đoán."""
    order = ["filing", "tdnet", "company_ir", "shikiho", "name_only"]
    kinds = {e.kind for e in items}
    for k in order:
        if k in kinds:
            return k
    return "none"


class Judgment(_Model):
    code: str
    question_id: str
    question_version: int
    primitive: Literal["noul", "choice", "score"]
    raw_noul: float | None = None
    raw_choice: str | None = None
    raw_confidence: float | None = None
    probabilities: dict[str, float] | None = None
    value: bool | str | None = None   # sau chính sách ngưỡng; None = chưa kết luận
    evidence_hash: str
    evidence_label: str
    model: str
    judged_at: datetime


# ------------------------------------------------------------ cổng / kết quả
class GateCheck(_Model):
    name: str
    value: float | None = None
    threshold: float | None = None
    passed: bool | None = None   # None = thiếu dữ liệu
    note: str | None = None


class _Gate(_Model):
    code: str
    checks: list[GateCheck]
    passed: bool                 # True chỉ khi MỌI check đều True
    insufficient_data: bool      # có ít nhất một check None
    as_of: date | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if self.passed and any(c.passed is not True for c in self.checks):
            raise ValueError("cổng không được qua khi có check chưa qua/thiếu dữ liệu")
        return self


class UniverseGate(_Gate):
    market: Market | None = None
    market_cap: Sourced = Field(default_factory=Sourced)
    adtv: Sourced = Field(default_factory=Sourced)


class GrowthGate(_Gate):
    pass


class Valuation(_Model):
    code: str
    per_forecast: float | None = None
    eps_growth: float | None = None          # tăng trưởng EPS dự phóng (tỷ lệ, 0.2 = 20%)
    eps_growth_capped: float | None = None
    peg: float | None = None                 # None khi growth ≤ 0 hoặc thiếu
    market_cap: float | None = None          # JPY = giá × (発行済 − 自己株)
    net_cash: float | None = None            # JPY, công thức 清原
    net_cash_ratio: float | None = None
    as_of: date | None = None
    sources: list[str] = Field(default_factory=list)


class ChecklistItem(_Model):
    key: str
    value: bool | None = None
    method: Literal["code", "jev", "none"]
    detail: str | None = None
    judgments: list[str] = Field(default_factory=list)   # question_id@ver


class Checklist(_Model):
    code: str
    items: list[ChecklistItem]
    themes: list[str] = Field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(1 for i in self.items if i.value is True)

    @property
    def known(self) -> int:
        return sum(1 for i in self.items if i.value is not None)


class CatalystEvent(_Model):
    code: str
    type: CatalystType
    strength: CatalystStrength
    title: str | None = None
    disclosed_at: datetime | None = None
    effective_date: date
    method: Literal["rule", "jev", "code"]
    source: str
    url: str | None = None
    detail: str | None = None


class EntrySignalResult(_Model):
    code: str
    as_of: date | None = None
    signal: EntrySignal = EntrySignal.NONE
    close: float | None = None
    change_1d: float | None = None
    volume_ratio: float | None = None
    high_52w: float | None = None
    drawdown_52w: float | None = None
    range_ratio: float | None = None
    rsi: float | None = None
    is_gainer: bool | None = None
    is_breakout: bool | None = None
    is_bottom: bool | None = None
    source: str | None = None
    notes: list[str] = Field(default_factory=list)


class ThesisCheck(_Model):
    code: str
    as_of: date
    status: ThesisStatus
    reasons: list[str] = Field(default_factory=list)
    insufficient_data: bool = False


class ScoreCard(_Model):
    universe: UniverseGate | None = None
    growth: GrowthGate | None = None
    valuation: Valuation | None = None
    checklist: Checklist | None = None
    catalysts: list[CatalystEvent] = Field(default_factory=list)


class TenBaggerCandidate(_Model):
    code: str
    name: str | None = None
    market: Market | None = None
    tier: Tier
    labels: list[str] = Field(default_factory=list)   # "10x" chỉ cho tầng A
    tier_reasons: list[str] = Field(default_factory=list)
    scorecard: ScoreCard
    entry_signal: EntrySignalResult | None = None     # tách riêng, không ảnh hưởng tầng
    thesis: ThesisCheck | None = None


class CandidateExport(_Model):
    """File bàn giao sang Stock JP Bot (Kiyohara + DCF)."""

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    as_of: date | None
    params_version: str
    universe_count: int
    counts: dict[str, int]
    candidates: list[TenBaggerCandidate]
    failures: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ------------------------------------------------------------ đầu ra crew
class ArbiterVerdict(_Model):
    """Arbiter chỉ PHÂN XỬ mâu thuẫn giữa các bằng chứng đã có — không tính số."""

    code: str
    conflicts: list[str]
    resolution: Literal["keep_tier", "flag_for_review", "insufficient_evidence"]
    rationale: str


class WriterReport(_Model):
    code: str
    summary: str = Field(description="mô tả dữ liệu, KHÔNG khuyến nghị mua/bán")
    cited_fields: list[str]


EXPORTED_MODELS: dict[str, type[BaseModel]] = {
    "candidate-export": CandidateExport,
    "tenbagger-candidate": TenBaggerCandidate,
    "catalyst-event": CatalystEvent,
    "entry-signal": EntrySignalResult,
    "thesis-check": ThesisCheck,
    "judgment": Judgment,
    "fundamentals": Fundamentals,
    "arbiter-verdict": ArbiterVerdict,
    "writer-report": WriterReport,
}

# Fundamentals tham chiếu Evidence (khai sau) → resolve forward ref.
Fundamentals.model_rebuild()


def export_json_schemas(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in EXPORTED_MODELS.items():
        p = out / f"{name}.schema.json"
        p.write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        written.append(p)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="schemas")
    for p in export_json_schemas(ap.parse_args().out):
        print(p)
