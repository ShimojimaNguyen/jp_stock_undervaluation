"""EscalatingAgent — giả lập lớp cha, KHÔNG gọi LLM thật."""
import pytest
from crewai import Agent, Task

from src.crew.escalating import _VALIDATION_PREFIX, EscalatingAgent, LadderExhausted
from src.crew.tenbagger_crew import no_recommendation

LADDER = ["anthropic/claude-haiku-4-5-20251001", "anthropic/claude-sonnet-5-5",
          "anthropic/claude-opus-5-5"]


@pytest.fixture
def script(monkeypatch):
    """Danh sách hành vi cho từng lần gọi lớp cha: 'ok' hoặc 'err'."""
    plan: list[str] = []
    seen: list[str] = []

    def fake(self, task, context=None, tools=None):
        seen.append(self.llm.model)
        step = plan.pop(0)
        if step == "err":
            raise RuntimeError("llm boom")
        return f"out:{self.llm.model}"

    monkeypatch.setattr(Agent, "execute_task", fake)
    return plan, seen


def _agent():
    return EscalatingAgent(role="r", goal="g", backstory="b", llm=LADDER[0], ladder=LADDER)


def _task(a):
    return Task(description="d", expected_output="e", agent=a)


def test_cheapest_first(script):
    plan, seen = script
    plan += ["ok"]
    a = _agent()
    assert a.execute_task(_task(a)).endswith("haiku-4-5-20251001")
    assert a.model_log == [{"model_used": LADDER[0], "outcome": "ok"}]


def test_two_errors_escalate_one_tier(script):
    plan, seen = script
    plan += ["err", "err", "ok"]
    a = _agent()
    out = a.execute_task(_task(a))
    assert [m.split("/")[-1] for m in seen] == ["claude-haiku-4-5-20251001"] * 2 + [
        "claude-sonnet-5-5"]
    assert "sonnet" in out
    assert [e["outcome"] for e in a.model_log] == ["error:RuntimeError"] * 2 + ["ok"]


def test_guardrail_rejections_count_as_failures(script):
    plan, seen = script
    plan += ["ok", "ok", "ok"]
    a = _agent()
    t = _task(a)
    a.execute_task(t)
    a.execute_task(t, context=_VALIDATION_PREFIX + "bad")     # haiku bị từ chối lần 1
    assert a.current_model == LADDER[0]
    a.execute_task(t, context=_VALIDATION_PREFIX + "bad")     # lần 2 → lên sonnet
    assert a.current_model == LADDER[1]
    assert "guardrail_rejected" in [e["outcome"] for e in a.model_log]


def test_new_task_restarts_at_cheapest(script):
    plan, seen = script
    plan += ["err", "err", "ok", "ok"]
    a = _agent()
    a.execute_task(_task(a))
    assert a.current_model == LADDER[1]
    a.execute_task(_task(a))
    assert a.current_model == LADDER[0]


def test_ladder_exhausted(script):
    plan, seen = script
    plan += ["err"] * 6
    a = _agent()
    with pytest.raises(LadderExhausted):
        a.execute_task(_task(a))
    assert len(seen) == 6


def test_unrelated_context_is_not_a_failure(script):
    plan, seen = script
    plan += ["ok", "ok"]
    a = _agent()
    t = _task(a)
    a.execute_task(t, context="kết quả task trước")
    a.execute_task(t, context="kết quả task trước")
    assert all(e["outcome"] == "ok" for e in a.model_log)


def test_no_recommendation_guardrail():
    ok, _ = no_recommendation("Doanh thu tăng 15% (CAGR 3 năm).")
    assert ok
    ok, msg = no_recommendation("Mã này nên mua ở vùng giá hiện tại.")
    assert not ok and "nên mua" in msg
    assert not no_recommendation("今が買い推奨")[0]


def test_build_crew_is_arbiter_and_writer_only(params):
    from src.contracts import ArbiterVerdict, ScoreCard, TenBaggerCandidate, Tier, WriterReport
    from src.crew.tenbagger_crew import build_crew

    cand = TenBaggerCandidate(code="9999", tier=Tier.C, scorecard=ScoreCard())
    crew = build_crew(cand, params)
    assert [a.role for a in crew.agents] == ["Arbiter", "Writer"]
    assert all(isinstance(a, EscalatingAgent) and a.ladder == params.llm.ladder for a in crew.agents)
    assert [t.output_pydantic for t in crew.tasks] == [ArbiterVerdict, WriterReport]
    assert all(t.guardrail_max_retries == 5 for t in crew.tasks)
