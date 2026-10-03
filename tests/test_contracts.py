import json
from datetime import date

import pytest
from pydantic import ValidationError

from src.contracts import (
    CandidateExport,
    CatalystStrength,
    Evidence,
    GateCheck,
    GrowthGate,
    Quality,
    Sourced,
    evidence_hash,
    evidence_label,
    export_json_schemas,
)
from src.params import load_params


def test_sourced_value_requires_asof_and_source():
    with pytest.raises(ValidationError):
        Sourced(value=1.0, quality=Quality.LIVE)
    s = Sourced.of(1.0, date(2026, 9, 29), "kabutan")
    assert s.quality is Quality.LIVE


def test_sourced_missing_is_none_not_zero():
    s = Sourced.of(None, date(2026, 9, 29), "kabutan")
    assert s.value is None and s.quality is Quality.MISSING
    with pytest.raises(ValidationError):
        Sourced(value=None, quality=Quality.LIVE)


def test_gate_cannot_pass_with_missing_check():
    with pytest.raises(ValidationError):
        GrowthGate(code="1234", passed=True, insufficient_data=True,
                   checks=[GateCheck(name="cfo", passed=None)])


def test_evidence_hash_order_independent():
    a = Evidence(text="a", source="s", kind="filing")
    b = Evidence(text="b", source="s", kind="name_only")
    assert evidence_hash([a, b]) == evidence_hash([b, a])
    assert evidence_label([b, a]) == "filing"
    assert evidence_label([]) == "none"


def test_strength_rank_order():
    assert CatalystStrength.HIGH.rank > CatalystStrength.MEDIUM.rank > CatalystStrength.LOW.rank
    assert CatalystStrength.NEGATIVE.rank < CatalystStrength.LOW.rank


def test_params_load_and_units():
    p = load_params()
    assert p.universe.market_cap_min_jpy == 5_000_000_000
    assert p.universe.market_cap_max_jpy == 100_000_000_000
    assert p.valuation.investment_securities_haircut == 0.7
    assert p.thesis.rsi_high_is_sell_signal_for_10x is False
    assert p.llm.failures_before_escalate == 2
    assert p.llm.ladder[0].endswith("haiku-4-5-20251001")


def test_params_rejects_unknown_key(tmp_path):
    import yaml

    raw = yaml.safe_load(open("config/params.yaml", encoding="utf-8"))
    raw["growth"]["typo_key"] = 1
    f = tmp_path / "p.yaml"
    f.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_params(f)


def test_export_json_schemas(tmp_path):
    paths = export_json_schemas(tmp_path)
    names = {p.name for p in paths}
    assert "candidate-export.schema.json" in names
    schema = json.loads((tmp_path / "candidate-export.schema.json").read_text())
    assert schema["title"] == CandidateExport.__name__


def test_committed_schemas_are_current(tmp_path):
    """schemas/ là artifact sinh tự động và được commit — phải khớp contracts.py."""
    from pathlib import Path

    for p in export_json_schemas(tmp_path):
        committed = Path("schemas") / p.name
        assert committed.exists(), f"thiếu {committed} — chạy python -m src.contracts"
        assert committed.read_text() == p.read_text(), f"{committed} cũ — chạy python -m src.contracts"
