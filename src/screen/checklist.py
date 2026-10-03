"""Bước 4 — checklist @shikiho_10 (5 mục). Code khi có số, Jev khi chỉ có văn bản.

  niche_share        Jev noul `niche_share`
  theme              Jev noul mỗi theme một câu; True nếu ≥1 theme True
  recurring_revenue  Jev noul `recurring_revenue`
  record_backlog     CODE nếu có số 受注残 (kỳ mới nhất ≥ max các kỳ trước trong
                     N năm); chỉ có văn bản → Jev `record_backlog_text`
  insider_ownership  CODE từ 大株主/役員持株: tổng tỷ lệ officer + founder_entity

Mục None = chưa kết luận: KHÔNG cộng điểm, KHÔNG trừ điểm.
"""
from __future__ import annotations

from src.contracts import BacklogPoint, Checklist, ChecklistItem, Holder, Judgment
from src.params import ChecklistParams


def _jv(judgments: dict[str, Judgment], qid: str) -> tuple[bool | None, list[str]]:
    j = judgments.get(qid)
    if j is None:
        return None, []
    v = j.value if isinstance(j.value, bool) else None
    return v, [f"{j.question_id}@{j.question_version}:{j.evidence_label}"]


def backlog_is_record(points: list[BacklogPoint] | None, lookback: int) -> bool | None:
    if not points:
        return None
    vals = [p.value for p in points[-(lookback + 1):]]
    if vals[-1] is None:
        return None
    prior = [v for v in vals[:-1] if v is not None]
    if len(prior) < 2:
        return None   # 1 điểm so sánh không đủ gọi là "kỷ lục"
    return vals[-1] >= max(prior)


def insider_ownership(holders: list[Holder] | None, minimum: float) -> tuple[bool | None, float | None]:
    if holders is None:
        return None, None
    known = sum(h.ratio for h in holders if h.kind in ("officer", "founder_entity"))
    total = round(known, 4)
    if total >= round(minimum, 4):
        return True, total
    if any(h.kind is None for h in holders):
        return None, total   # còn cổ đông chưa phân loại → chưa kết luận được là "thấp"
    return False, total


def build_checklist(code: str, judgments: dict[str, Judgment], backlog: list[BacklogPoint] | None,
                    holders: list[Holder] | None, p: ChecklistParams) -> Checklist:
    items: list[ChecklistItem] = []

    v, refs = _jv(judgments, "niche_share")
    items.append(ChecklistItem(key="niche_share", value=v, method="jev" if refs else "none",
                               judgments=refs))

    theme_vals, theme_refs, themes = [], [], []
    for t in p.themes:
        tv, tr = _jv(judgments, f"theme_{t}")
        theme_vals.append(tv)
        theme_refs += tr
        if tv is True:
            themes.append(t)
    if any(x is True for x in theme_vals):
        tval = True
    elif theme_vals and all(x is False for x in theme_vals):
        tval = False
    else:
        tval = None
    items.append(ChecklistItem(key="theme", value=tval, method="jev" if theme_refs else "none",
                               detail=",".join(themes) or None, judgments=theme_refs))

    v, refs = _jv(judgments, "recurring_revenue")
    items.append(ChecklistItem(key="recurring_revenue", value=v,
                               method="jev" if refs else "none", judgments=refs))

    rec = backlog_is_record(backlog, p.backlog_record_lookback_years)
    if rec is not None:
        items.append(ChecklistItem(key="record_backlog", value=rec, method="code",
                                   detail=f"受注残 {backlog[-1].period}"))
    else:
        v, refs = _jv(judgments, "record_backlog_text")
        items.append(ChecklistItem(key="record_backlog", value=v,
                                   method="jev" if refs else "none", judgments=refs))

    ins, total = insider_ownership(holders, p.insider_ownership_min)
    items.append(ChecklistItem(key="insider_ownership", value=ins,
                               method="code" if holders is not None else "none",
                               detail=None if total is None else f"{total:.4f}"))
    return Checklist(code=code, items=items, themes=themes)
