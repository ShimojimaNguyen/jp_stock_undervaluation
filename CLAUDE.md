# CLAUDE.md — jp_stock_undervaluation

Flow 10-bagger (@shikiho_10 + 清原). Kiến trúc: `docs/architecture.md`.

## Luật chung (đọc trước)

Lớp chung ở `../stock-shared` (sync: `bash ../stock-shared/scripts/sync.sh`).
Bắt buộc: `data-integrity-pillars`, `jev-judgments`, `market-data-sources`.
Tóm tắt những điều repo này cưỡng chế bằng code:

- Thiếu số → `null`/`—`, **không bao giờ 0**. `Sourced` từ chối số không có `as_of` + `source`.
- Cổng thiếu dữ liệu **không bao giờ qua** (`insufficient_data`).
- Làm tròn trước khi so ngưỡng (`src/screen/numeric.py`). So sánh trên numpy
  scalar phải qua `rnd()`/`bool()` — `np.False_ is False` là `False`.
- Không look-ahead: TB/đỉnh/RSI tham chiếu chỉ dùng phiên **trước** phiên xét;
  catalyst chỉ tính khi `effective_date ≤ as_of`.
- Mỗi nguồn ghi file riêng; ghi idempotent theo kỳ; `--limit` ghi `.sample.json`.
- Mọi ngưỡng ở `config/params.yaml`. Mọi hợp đồng ở `src/contracts.py`; đổi
  contract → chạy `uv run python -m src.contracts --out schemas` (test chặn nếu quên).
- Không nội dung khuyến nghị mua/bán.

## Code vs Jev vs LLM

- **Code** tính mọi con số.
- **Jev** chỉ cho phán đoán ngữ nghĩa trên văn bản; câu hỏi chỉ ở `questions/*.yaml`;
  `choice` phải có `none_of_these`; chạy batch (`python -m src.jev.run`), không
  trong request path; header `User-Agent` bắt buộc; key chỉ từ env `TYPESAFE_API_KEY`.
- **LLM crew** chỉ Arbiter + Writer.

## Quy tắc chọn model LLM: rẻ nhất trước, fail 2 lần thì lên bậc

Thang cố định (`config/params.yaml: llm.ladder`):

1. `anthropic/claude-haiku-4-5-20251001`
2. `anthropic/claude-sonnet-5-5`
3. `anthropic/claude-opus-5-5`

Luôn bắt đầu ở bậc rẻ nhất. Mỗi bậc **fail 2 lần** (lỗi hoặc guardrail từ chối)
thì lên bậc kế. Task mới bắt đầu lại từ bậc 1. Cài đặt: `EscalatingAgent`
(`src/crew/escalating.py`), `guardrail_max_retries=5`, log `model_used`.
Không agent nào được hardcode model cao hơn bậc 1.

## Lệnh

```bash
uv sync --group dev
uv run pytest -q                 # golden Jev tự skip khi thiếu TYPESAFE_API_KEY
uv run ruff check src tests
TYPESAFE_API_KEY=... uv run pytest -m golden
```

Chạy test + lint trước mỗi push. Nối lệnh commit sau test bằng `&&`, không `;`.

## Lưu trữ

`runs/2026-08-23/`, `crew.jsonc`, `agents/` (crew 9 agent cũ) giữ nguyên làm lưu trữ.
