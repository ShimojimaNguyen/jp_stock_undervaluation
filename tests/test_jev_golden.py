"""Golden test Jev — GỌI MẠNG thật, skip khi thiếu TYPESAFE_API_KEY.

Chốt hành vi của các ca trong questions/*.yaml. Model là phụ thuộc bên ngoài có
thể đổi dưới chân (`jev-latest`) mà không có dòng diff nào.

Ca quan trọng nhất là `fabricated_name_only`: công ty không tồn tại thì KHÔNG
được có khẳng định mạnh. Đỏ ở đó → dừng dùng Jev cho checklist, ĐỪNG nới ngưỡng.

Chạy:  TYPESAFE_API_KEY=... uv run pytest -m golden
"""
import os

import pytest

from src.jev.client import JevClient, decide
from src.jev.registry import load_registry
from src.params import load_params

pytestmark = [
    pytest.mark.golden,
    pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="thiếu TYPESAFE_API_KEY"),
]

_REG = load_registry()
CASES = [(q, c) for q in _REG.all() for c in q.golden]


@pytest.mark.parametrize("q,case", CASES, ids=[f"{q.id}:{c.name}" for q, c in CASES])
def test_golden(q, case):
    p = load_params().jev
    answers = JevClient(p).ask(case.state, [q])
    got = decide(q, answers.get(q.id), p)
    if case.expect is not None:
        assert got == case.expect, f"{q.key} {case.name}: raw={answers.get(q.id)}"
    if case.expect_not is not None:
        assert got != case.expect_not, f"{q.key} {case.name}: raw={answers.get(q.id)}"
