"""Client Jev (TypeSafe System One) + chính sách ngưỡng + cache + chạy batch.

Chạy THEO LÔ lúc build (`python -m src.jev.client ...` hoặc pipeline), KHÔNG
trong đường xử lý request. Mọi con số do code tính; Jev chỉ trả lời câu ngữ nghĩa
trên văn bản được cung cấp.

  · Khoá chỉ từ env TYPESAFE_API_KEY — không bao giờ vào file.
  · Header User-Agent BẮT BUỘC: thiếu là 403 `error code: 1010` (Cloudflare),
    trông như khoá hỏng.
  · Cache khoá theo (code, question_id@version, evidence_hash): đổi câu hỏi
    (tăng version) hoặc đổi bằng chứng → hỏi lại; còn lại dùng kết quả cũ.
  · Văn bản nguồn là DỮ LIỆU: chỉ đọc câu trả lời có kiểu, không render state.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.contracts import Evidence, Judgment, evidence_hash, evidence_label
from src.jev.registry import Question
from src.params import JevParams


class JevUnavailable(RuntimeError):
    pass


# --------------------------------------------------------------- chính sách
def decide(q: Question, answer: dict | None, p: JevParams) -> bool | str | None:
    """Xác suất → kết luận. Làm tròn TRƯỚC khi so; vùng giữa → None (luật 2–4)."""
    if not answer:
        return None
    if q.type == "noul":
        v = answer.get("noul")
        if v is None:
            return None
        v = round(float(v), 4)
        if v >= round(p.noul_accept_min, 4):
            return True
        if v <= round(p.noul_reject_max, 4):
            return False
        return None
    if q.type == "choice":
        c, conf = answer.get("choice"), answer.get("confidence")
        if c is None or conf is None or c not in q.criteria:
            return None
        return c if round(float(conf), 4) >= round(p.choice_confidence_min, 4) else None
    return None   # score: chưa có câu nào dùng — không đoán chính sách


def build_state(code: str, name: str | None, evidence: list[Evidence]) -> dict:
    s: dict = {"ticker": code}
    if name:
        s["company_name_ja"] = name
    if evidence:
        s["evidence_ja"] = [e.text for e in evidence]
    return s


# --------------------------------------------------------------- HTTP
class JevClient:
    def __init__(self, p: JevParams, api_key: str | None = None, session=None):
        self.p = p
        self.key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.key:
            raise JevUnavailable("thiếu TYPESAFE_API_KEY trong env — không gọi Jev")
        if session is None:
            import requests

            session = requests.Session()
        self.s = session

    def ask(self, state: dict, questions: list[Question]) -> dict[str, dict]:
        body = {"state": state, "model": self.p.model,
                "questions": {q.id: q.payload() for q in questions}}
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                   "User-Agent": self.p.user_agent}
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = self.s.post(self.p.endpoint, data=json.dumps(body), headers=headers,
                                timeout=self.p.timeout_s)
                if r.status_code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if r.status_code == 403 and "1010" in (r.text or ""):
                    raise JevUnavailable("403/1010 — Cloudflare chặn: kiểm User-Agent")
                r.raise_for_status()
                return r.json().get("answers", {})
            except JevUnavailable:
                raise
            except Exception as e:  # noqa: BLE001 — retry rồi ném lại
                last = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Jev thất bại sau 3 lần: {last}")


# --------------------------------------------------------------- cache
class JudgmentCache:
    """JSONL, một dòng một Judgment, khoá (code, id@ver, evidence_hash). Ghi lại idempotent."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._d: dict[tuple[str, str, str], Judgment] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    j = Judgment.model_validate_json(line)
                    self._d[self._k(j.code, f"{j.question_id}@{j.question_version}",
                                    j.evidence_hash)] = j

    @staticmethod
    def _k(code: str, qkey: str, ev_hash: str) -> tuple[str, str, str]:
        return (code, qkey, ev_hash)

    def get(self, code: str, q: Question, ev_hash: str) -> Judgment | None:
        return self._d.get(self._k(code, q.key, ev_hash))

    def put(self, j: Judgment) -> None:
        self._d[self._k(j.code, f"{j.question_id}@{j.question_version}", j.evidence_hash)] = j

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(self._d.values(), key=lambda j: (j.code, j.question_id, j.question_version))
        self.path.write_text("".join(j.model_dump_json() + "\n" for j in rows), encoding="utf-8")


# --------------------------------------------------------------- batch
@dataclass
class JevItem:
    code: str
    state: dict
    evidence: list[Evidence]
    questions: list[Question]


def to_judgment(code: str, q: Question, answer: dict | None, ev: list[Evidence],
                p: JevParams, ev_hash: str | None = None) -> Judgment:
    a = answer or {}
    return Judgment(
        code=code, question_id=q.id, question_version=q.version, primitive=q.type,
        raw_noul=a.get("noul"), raw_choice=a.get("choice"), raw_confidence=a.get("confidence"),
        probabilities=a.get("probabilities"), value=decide(q, answer, p),
        evidence_hash=ev_hash or evidence_hash(ev),
        evidence_label=evidence_label(ev) if ev else "name_only",
        model=p.model, judged_at=datetime.now(timezone.utc),
    )


def judge_batch(items: Iterable[JevItem], ask: Callable[[dict, list[Question]], dict],
                cache: JudgmentCache, p: JevParams, workers: int = 8
                ) -> tuple[list[Judgment], list[dict]]:
    """Hỏi những (mã, câu) chưa có trong cache; gom mọi câu của một mã vào MỘT request.

    → (judgments — gồm cả từ cache, failures). Lỗi một mã không làm hỏng cả lô;
    mã lỗi được đếm vào failures, KHÔNG thành judgment rỗng trông như thật.
    """
    out: list[Judgment] = []
    todo: list[tuple[JevItem, list[Question], str]] = []
    for it in items:
        h = evidence_hash(it.evidence) if it.evidence else f"name:{it.code}"
        missing = []
        for q in it.questions:
            hit = cache.get(it.code, q, h)
            if hit is not None:
                out.append(hit)
            else:
                missing.append(q)
        if missing:
            todo.append((it, missing, h))

    def work(t):
        it, qs, h = t
        try:
            return it, qs, h, ask(it.state, qs), None
        except Exception as e:  # noqa: BLE001
            return it, qs, h, None, f"{type(e).__name__}: {e}"

    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for it, qs, h, answers, err in pool.map(work, todo):
            if err:
                failures.append({"code": it.code, "reason": err})
                continue
            for q in qs:
                j = to_judgment(it.code, q, answers.get(q.id), it.evidence, p, h)
                cache.put(j)
                out.append(j)
    return out, failures
