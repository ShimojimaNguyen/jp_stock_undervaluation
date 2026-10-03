"""EscalatingAgent — model rẻ nhất trước, mỗi bậc fail 2 lần thì lên bậc.

Thang (config/params.yaml `llm.ladder`):
  anthropic/claude-haiku-4-5-20251001 → anthropic/claude-sonnet-5-5 → anthropic/claude-opus-5-5

"Fail" = (a) execute_task ném lỗi, hoặc (b) guardrail của Task từ chối kết quả.
(b) nhận ra được vì crewai gọi lại `agent.execute_task` với `context` bắt đầu bằng
template `validation_error` của nó — không đoán theo số lần gọi (một Task có thể
được chạy lại hợp lệ ở lần kickoff sau).

Mỗi Task mới bắt đầu lại từ bậc rẻ nhất. `model_log` ghi model đã dùng cho mỗi
lần thử (model_used) để biết chi phí thật đi về đâu.

Đặt `max_retry_limit=0` để vòng retry nội bộ của crewai không nuốt lỗi trước khi
lớp này kịp đếm. Guardrail của Task nên đặt `guardrail_max_retries=5`
(= 2 + 2 + 1 lần thử trên thang 3 bậc).
"""
from __future__ import annotations

from typing import Any

from crewai import Agent
from crewai.utilities.i18n import I18N_DEFAULT
from crewai.utilities.llm_utils import create_llm
from pydantic import Field, PrivateAttr

_VALIDATION_PREFIX = I18N_DEFAULT.errors("validation_error").split("{", 1)[0]


class LadderExhausted(RuntimeError):
    pass


class EscalatingAgent(Agent):
    ladder: list[str] = Field(default_factory=list)
    failures_before_escalate: int = 2
    max_retry_limit: int = 0

    _tier: int = PrivateAttr(default=0)
    _fails_at_tier: int = PrivateAttr(default=0)
    _task_key: int | None = PrivateAttr(default=None)
    _model_log: list[dict] = PrivateAttr(default_factory=list)

    @property
    def model_log(self) -> list[dict]:
        return list(self._model_log)

    @property
    def current_model(self) -> str:
        return self.ladder[self._tier]

    # ------------------------------------------------------------ bậc thang
    def _use(self, model: str) -> None:
        cur = getattr(self.llm, "model", None)
        if cur != model and cur != model.split("/", 1)[-1]:
            self.llm = create_llm(model)
            self.agent_executor = None   # executor giữ tham chiếu llm cũ → dựng lại

    def _fail(self, reason: str) -> None:
        self._model_log.append({"model_used": self.current_model, "outcome": reason})
        self._fails_at_tier += 1
        if self._fails_at_tier >= self.failures_before_escalate:
            if self._tier + 1 >= len(self.ladder):
                raise LadderExhausted(
                    f"đã fail {self._fails_at_tier} lần ở bậc cao nhất {self.current_model}")
            self._tier += 1
            self._fails_at_tier = 0

    def _start(self, task: Any) -> None:
        self._task_key = id(task)
        self._tier = 0
        self._fails_at_tier = 0

    # ------------------------------------------------------------ crewai hook
    def execute_task(self, task: Any, context: str | None = None, tools: list | None = None) -> Any:
        if not self.ladder:
            raise ValueError("EscalatingAgent cần ladder ≥ 1 model")
        retry_after_guardrail = bool(context and context.startswith(_VALIDATION_PREFIX)) \
            and self._task_key == id(task)
        if retry_after_guardrail:
            self._fail("guardrail_rejected")
        else:
            self._start(task)
        while True:
            self._use(self.current_model)
            try:
                result = super().execute_task(task, context, tools)
            except LadderExhausted:
                raise
            except Exception as e:  # noqa: BLE001 — đếm rồi thử lại / lên bậc
                self._fail(f"error:{type(e).__name__}")
                continue
            self._model_log.append({"model_used": self.current_model, "outcome": "ok"})
            return result


def make_escalating_agent(role: str, goal: str, backstory: str, ladder: list[str],
                          failures_before_escalate: int = 2, **kw: Any) -> EscalatingAgent:
    return EscalatingAgent(role=role, goal=goal, backstory=backstory, llm=ladder[0],
                           ladder=ladder, failures_before_escalate=failures_before_escalate,
                           **kw)
