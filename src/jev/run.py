"""Chạy batch Jev (build-time, KHÔNG trong request path) → cập nhật cache.

  uv run python -m src.jev.run --fundamentals-source edinet [--tdnet-dir data/tdnet]

Hỏi: câu checklist cho mỗi mã có Fundamentals (bằng chứng = text_evidence; không
có thì chỉ tên — nhãn name_only sẽ đi kèm phán đoán), và câu tdnet_title_kind
cho tiêu đề TDnet KHÔNG khớp rule. Phần đã có trong cache không hỏi lại.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.catalyst.tdnet import classify, read_day
from src.data.adapters import JsonFundamentalsSource
from src.jev.client import JevClient, JevItem, JudgmentCache, build_state, judge_batch
from src.jev.registry import default_registry
from src.params import default_params
from src.pipeline import ROOT, checklist_question_ids, title_evidence
from src.screen.growth import growth_gate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fundamentals-source", default=None)
    ap.add_argument("--tdnet-dir", default=str(ROOT / "data" / "tdnet"))
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--all", action="store_true",
                    help="hỏi mọi mã; mặc định chỉ mã QUA bước 2 (mã khác là NONE, checklist vô dụng)")
    a = ap.parse_args(argv)

    p = default_params()
    reg = default_registry()
    cache = JudgmentCache(ROOT / p.jev.cache_path)
    items: list[JevItem] = []
    if a.fundamentals_source:
        fs = JsonFundamentalsSource(a.fundamentals_source, base=Path(a.data_dir) / "fundamentals")
        qs = [reg[q] for q in checklist_question_ids(p) if q in reg]
        for code in fs.codes():
            f = fs.get(code)
            if not a.all and not growth_gate(f, p.growth).passed:
                continue
            items.append(JevItem(code, build_state(code, f.name, f.text_evidence),
                                 f.text_evidence, qs))
    tdir = Path(a.tdnet_dir)
    if tdir.exists():
        q = reg["tdnet_title_kind"]
        for path in sorted(tdir.glob("*.jsonl")):
            _, unmatched = classify(read_day(path), p.catalyst)
            for d in unmatched:
                items.append(JevItem(d.code, {"title_ja": d.title}, title_evidence(d), [q]))

    client = JevClient(p.jev)
    js, failures = judge_batch(items, client.ask, cache, p.jev)
    cache.save()
    print(f"judgments={len(js)} failures={len(failures)} cache={cache.path}")
    for fl in failures:
        print(f"  {fl['code']}: {fl['reason']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
