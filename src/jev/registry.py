"""Registry câu hỏi Jev — nạp questions/*.yaml, mỗi câu đúng MỘT bản, có version.

Từ chối nạp (lỗi ngay, không cảnh báo) khi:
  · id trùng giữa các file;
  · câu `choice` thiếu `none_of_these`;
  · option của câu catalyst không phải giá trị CatalystType.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from src.contracts import CatalystType

ROOT = Path(__file__).resolve().parent.parent.parent


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    state: dict[str, Any]
    expect: bool | str | None = None
    expect_not: bool | str | None = None   # "không được là X" (ca đối chứng công ty bịa)
    measured: float | None = None


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: int
    type: Literal["noul", "choice", "score"]
    instructions: str
    criteria: dict[str, str]
    golden: list[GoldenCase] = []

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"

    @model_validator(mode="after")
    def _rules(self) -> Question:
        if self.type == "choice" and "none_of_these" not in self.criteria:
            raise ValueError(f"{self.id}: câu choice bắt buộc có none_of_these (jev-judgments luật 1)")
        if self.type == "noul" and set(self.criteria) != {"true", "false"}:
            raise ValueError(f"{self.id}: câu noul cần criteria đúng hai khoá true/false")
        return self

    def payload(self) -> dict:
        return {"type": self.type, "instructions": self.instructions.strip(),
                "criteria": self.criteria}


class Registry:
    def __init__(self, questions: list[Question]):
        self._q: dict[str, Question] = {}
        for q in questions:
            if q.id in self._q:
                raise ValueError(f"câu hỏi trùng id: {q.id} — mỗi câu chỉ được một bản")
            self._q[q.id] = q
        tk = self._q.get("tdnet_title_kind")
        if tk is not None:
            valid = {t.value for t in CatalystType} | {"none_of_these"}
            bad = set(tk.criteria) - valid
            if bad:
                raise ValueError(f"tdnet_title_kind có option không thuộc CatalystType: {bad}")

    def __getitem__(self, qid: str) -> Question:
        return self._q[qid]

    def __contains__(self, qid: str) -> bool:
        return qid in self._q

    def all(self) -> list[Question]:
        return list(self._q.values())


def load_registry(directory: str | Path | None = None) -> Registry:
    d = Path(directory) if directory else ROOT / "questions"
    qs: list[Question] = []
    for f in sorted(d.glob("*.yaml")):
        raw = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        qs.extend(Question.model_validate(q) for q in raw.get("questions", []))
    return Registry(qs)


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    return load_registry()
