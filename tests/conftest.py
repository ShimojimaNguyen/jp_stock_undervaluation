"""Dữ liệu GIẢ cho test — mã 9999 không tồn tại. Không bao giờ dùng ngoài tests/."""
from datetime import date

import pytest

from src.contracts import (
    AnnualResult,
    BalanceSheet,
    Forecast,
    Fundamentals,
    Market,
    Sourced,
)
from src.params import load_params

D = date(2026, 9, 29)
SRC = "fixture"


@pytest.fixture
def params():
    return load_params()


def make_fundamentals(**over) -> Fundamentals:
    """Một công ty giả qua mọi cổng bước 2: revenue 100→152.1 (CAGR 15%), OP +25%."""
    annual = [
        AnnualResult(fiscal_period=f"{y}.03", revenue=r, operating_profit=op, eps=eps, cfo=cfo,
                     source=SRC, as_of=D)
        for y, r, op, eps, cfo in [
            (2023, 100e8, 8e8, 50.0, 5e8),
            (2024, 115e8, 10e8, 60.0, 6e8),
            (2025, 132.25e8, 12e8, 72.0, 7e8),
            (2026, 152.0875e8, 14e8, 84.0, 8e8),
        ]
    ]
    base = dict(
        code="9999", name="テスト株式会社", market=Market.STANDARD,
        annual=annual,
        forecast=Forecast(fiscal_period="2027.03", revenue=175e8, operating_profit=17.5e8,
                          eps=105.0, source=SRC, as_of=D),
        balance_sheet=BalanceSheet(period_end=date(2026, 3, 31), current_assets=120e8,
                                   investment_securities=10e8, total_liabilities=60e8,
                                   total_assets=150e8, equity=90e8, net_assets=90e8,
                                   source=SRC, as_of=D),
        shares_issued=Sourced.of(10_000_000, D, SRC),
        treasury_shares=Sourced.of(500_000, D, SRC),
    )
    base.update(over)
    return Fundamentals(**base)


@pytest.fixture
def fundamentals():
    return make_fundamentals()
