"""Nạp config/params.yaml thành model có kiểu — sai tên khoá là lỗi ngay khi nạp."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from src.contracts import CatalystStrength, Market

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config" / "params.yaml"


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UniverseParams(_P):
    markets: list[Market]
    market_cap_min_jpy: float
    market_cap_max_jpy: float
    adtv_window_days: int
    adtv_min_jpy: float


class GrowthParams(_P):
    revenue_cagr_years: int
    revenue_cagr_min: float
    op_forecast_growth_min: float
    opm_improving: bool
    cfo_min_jpy: float
    equity_ratio_min: float
    round_ndigits: int


class ValuationParams(_P):
    peg_max_tier_a: float
    peg_max_tier_b: float
    eps_growth_cap: float
    investment_securities_haircut: float
    net_cash_ratio_min_tier_a: float
    round_ndigits: int


class ChecklistParams(_P):
    items: list[str]
    themes: list[str]
    insider_ownership_min: float
    backlog_record_lookback_years: int


class PrimeParams(_P):
    shareholders_min: int
    tradable_units_min: int
    tradable_market_cap_min_jpy: float
    tradable_ratio_min: float
    market_cap_min_jpy: float
    net_assets_min_jpy: float
    profit_2y_sum_min_jpy: float


class CatalystParams(_P):
    tdnet_base_url: str
    tdnet_user_agent: str
    request_delay_s: float
    cutoff_hhmm: str
    market_holidays: list[str]
    upgrade_progress_margin: float
    upgrade_min_history_years: int
    prime: PrimeParams
    strength: dict[str, CatalystStrength]


class SignalParams(_P):
    gainer_min_change: float
    volume_mult_min: float
    volume_avg_window: int
    high_window_days: int
    bottom_drawdown_min: float
    range_short_window: int
    range_long_window: int
    range_contraction_max: float
    rsi_period: int
    rsi_oversold: float
    rsi_lookback_days: int
    round_ndigits: int


class ThesisParams(_P):
    weakening_revenue_yoy_drop: float
    broken_revenue_yoy_max: float
    opm_drop_weakening: float
    rsi_high_is_sell_signal_for_10x: bool


class TierParams(_P):
    a_checklist_min: int
    a_catalyst_min_strength: CatalystStrength
    b_checklist_min: int
    checklist_total: int


class JevParams(_P):
    endpoint: str
    model: str
    user_agent: str
    noul_accept_min: float
    noul_reject_max: float
    choice_confidence_min: float
    timeout_s: float
    cache_path: str


class LLMParams(_P):
    ladder: list[str]
    failures_before_escalate: int
    guardrail_max_retries: int


class Params(_P):
    version: str
    universe: UniverseParams
    growth: GrowthParams
    valuation: ValuationParams
    checklist: ChecklistParams
    catalyst: CatalystParams
    signals: SignalParams
    thesis: ThesisParams
    tiers: TierParams
    jev: JevParams
    llm: LLMParams


def load_params(path: str | Path | None = None) -> Params:
    p = Path(path) if path else DEFAULT_PATH
    return Params.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def default_params() -> Params:
    return load_params()
