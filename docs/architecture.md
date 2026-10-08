# Kiến trúc — flow 10-bagger (@shikiho_10 + 清原)

> Nguyên tắc: **code tính mọi con số**; **Jev** chỉ trả lời câu hỏi ngữ nghĩa trên
> văn bản được cung cấp; **LLM crew** chỉ còn Arbiter + Writer, không tính, không
> tra nguồn. Mọi ngưỡng ở `config/params.yaml`. Mọi hợp đồng dữ liệu ở
> `src/contracts.py` (JSON Schema xuất ra `schemas/`).

Luật chung áp dụng (repo `stock-shared`): `data-integrity-pillars`,
`jev-judgments`, `market-data-sources`. Khi mâu thuẫn: `CLAUDE.md` > pillars > file này.

---

## Bảy tầng L0–L6

```
L0 Nguồn ──► L1 Chuẩn hoá ──► L2 Tính (code) ──► L4 Tổng hợp ──► L5 Export ──► L6 Crew LLM
                    │                                ▲
                    └──────► L3 Jev (batch, cache) ──┘
```

| tầng | làm gì | ở đâu | trạng thái |
|---|---|---|---|
| **L0 Nguồn** | giá ngày (snapshot kiyohara), OHLCV (Yahoo chart v8), công bố (TDnet), cơ bản (**chưa có**) | `src/data/adapters.py`, `src/signals/gainers.py: fetch_chart`, `src/catalyst/tdnet.py: fetch_day` | xem §Nguồn |
| **L1 Chuẩn hoá** | ép vào `Fundamentals`, `PriceSnapshot`, `Disclosure`; **mỗi nguồn một file/thư mục** | `data/fundamentals/<source>/<code>.json`, `data/tdnet/YYYY-MM-DD.jsonl` | gitignore (bản sao vendor) |
| **L2 Tính** | bước 1–3, ADTV, chỉ báo kỹ thuật, 進捗率, tiêu chí Prime | `src/screen/*`, `src/signals/gainers.py`, `src/catalyst/tdnet.py` | xong + test |
| **L3 Jev** | checklist ngữ nghĩa + tiêu đề TDnet không khớp rule | `questions/*.yaml`, `src/jev/*` | xong; golden test chờ key |
| **L4 Tổng hợp** | checklist, catalyst, tầng A/B/C, ThesisCheck, entry signal | `src/screen/checklist.py`, `src/tiering.py`, `src/tracking/thesis.py` | xong + test |
| **L5 Export** | `data/tenbagger-candidates.json` (+ `.sample.json` khi `--limit`) | `src/pipeline.py` | chờ nguồn cơ bản |
| **L6 Crew** | Arbiter (mâu thuẫn) + Writer (mô tả) — `EscalatingAgent` | `src/crew/*` | xong; chưa nối vào pipeline |

**Chạy ở đâu**: GitHub Actions (`.github/workflows/tenbagger-daily.yml`), vì môi
trường dựng code (Claude Code cloud) chặn mọi host dữ liệu. Lần đầu: Actions →
tenbagger-daily → Run workflow với `shard=all` (~3,4 giờ). Sau đó tự chạy 16:45 JST
thứ Hai–Sáu, mỗi ngày làm mới 1/5 universe.

Thứ tự chạy (batch, không có request path):

```bash
uv run python -m src.data.jpx_universe --out data/universe.json               # L0 universe
uv run python -m src.data.kabutan_finance --universe data/universe.json --shard 0/5   # L0 株探
uv run python -m src.catalyst.tdnet --days 5                                      # L0 TDnet
uv run python -m src.jev.run --fundamentals-source kabutan                        # L3 (mã qua bước 2)
uv run python -m src.pipeline --fundamentals-source kabutan --universe data/universe.json --fetch-ohlcv
```

---

## Tám bước

| # | bước | ai làm | quy tắc chốt |
|---|---|---|---|
| 1 | **Universe** TSE Prime/Standard/Growth, vốn hoá 50–1000億円, ADTV 20 phiên ≥ 3000万円 | code | 時価総額 = 株価 × (発行済 − 自己株); thiếu 自己株 → null. ADTV cần đủ 20 phiên đã đóng |
| 2 | **Tăng trưởng** (bắt buộc): CAGR doanh thu 3 năm ≥15%, dự báo OP công ty ≥+20%, OPM cải thiện, CFO>0, 自己資本比率 ≥40% | code | thiếu dữ liệu = **không qua** (`insufficient_data`); kỳ 変 (≠12 tháng) chặn CAGR; dự báo phải cho kỳ SAU năm thực hiện gần nhất; tăng trưởng từ gốc ≤0 → null |
| 3 | **Định giá**: PEG = PER dự phóng / (tăng trưởng EPS × 100) ≤1; net cash 清原 | code | growth ≤0 → PEG null, cap 50%; **ネットキャッシュ = 流動資産 + 投資有価証券×0.7 − 負債合計**, 比率 = / 時価総額; thiếu thành phần → null. PER tính từ CÙNG nguồn EPS với tăng trưởng |
| 4 | **Checklist** 5 mục: niche share, theme, doanh thu lặp lại, backlog kỷ lục, sở hữu founder/ban lãnh đạo | Jev + code | theme: mỗi theme một câu noul (防衛/宇宙/AIデータセンター/半導体/防災); backlog: code nếu có số, Jev nếu chỉ văn bản; sở hữu: code từ 大株主/役員持株. Mục null không cộng không trừ |
| 5 | **Catalyst** TDnet | rule → Jev → code | rule tiêu đề trước; chỉ tiêu đề KHÔNG khớp mới sang Jev `choice` (có `none_of_these`); 業績予想の修正 không rõ hướng = loại riêng (hướng là số); công bố ≥15:00 / ngày nghỉ → phiên kế tiếp; 進捗率 vs TB lịch sử và tiêu chí Prime bằng code |
| 6 | **Thời điểm mua** | code | +3% (làm tròn trước so), vol ≥2× TB20 phiên **trước**; + close ≥ đỉnh 252 phiên **trước** → BREAKOUT. BOTTOM: sụt ≥40% từ đỉnh 52w, biên độ 10/60 ≤0,5, RSI14 từng ≤30 trong 20 phiên và giờ >30 + đang tăng, quý gần nhất qua bước 2 |
| 7 | **Theo dõi** | code | technical hằng ngày (bước 6); ThesisCheck mỗi quý INTACT/WEAKENING/BROKEN. **RSI cao KHÔNG là điều kiện bán với nhãn 10x** — `thesis.py` không đọc RSI (có test) |
| 8 | **Phân tầng** | code | A = 1+2, PEG≤1, net cash ratio≥0,3, checklist≥3/5, ≥1 catalyst ≥中 → nhãn **10x**; B = PEG≤1,5 và (checklist≥2/5 hoặc catalyst dương); C = chỉ qua 2. `entry_signal` tách riêng, không đổi tầng. Catalyst chỉ tính trong [as_of−180 ngày, as_of] |

**Diễn giải cần user xác nhận**: B có bắt buộc qua bước 1 không (đề bài chỉ ghi
cho A). Hiện `tiers.b_requires_universe: true`.

---

## Nguồn dữ liệu (đo thật trên GitHub Actions, 2026-10-07/08)

| dữ liệu | nguồn | trạng thái từ Actions |
|---|---|---|
| danh sách mã + thị trường toàn TSE | JPX `data_j` — `src/data/jpx_universe.py` | ✅ 3.702 mã (as_of 2026-09-30) |
| 4–5 năm doanh thu/OP/EPS/CFO; 流動資産, 投資有価証券, 負債合計, 自己資本, 総資産, 発行済, 自己株; giá | yfinance — `src/data/yf_fundamentals.py` | ✅ 186/186; phủ 4 năm 96%, CFO 99%, 発行済/自己株 96%, đủ thành phần net cash 84% |
| **会社予想** (売上高/営業利益/純利益) + lịch sử sửa dự báo + năm thực hiện JGAAP | Yahoo!ファイナンス `/quote/{code}.T/performance` — `src/data/yahoojp_forecast.py` | ✅ HTTP 200; **chặn sau ~85 mã** → chỉ hỏi mã qua mọi check khác của bước 2, ≤60/ngày, giãn 3s |
| OHLCV ngày | Yahoo chart v8 | ✅ HTTP 200 |
| 株探 `/stock/finance` | `src/data/kabutan_finance.py` | ❌ AWS WAF "Human Verification" (HTTP 405) với IP Actions. Không né bot protection. Chạy được từ máy cá nhân (như kiyohara). |
| TDnet danh sách công bố | `src/catalyst/tdnet.py` | ❌ robots.txt `User-agent: * / Disallow: /` — cấm crawl. Code tự dừng. Catalyst 上方/下方修正 thay bằng `forecastRevisionList` của Yahoo JP (tính bằng code). |
| EDINET API v2 | — | trả lời từ Actions; cần `EDINET_API_KEY` (大株主/役員持株, 事業の内容 cho Jev) — chưa nối |
| J-Quants | — | HTTP 403 không auth — cần tài khoản |
| snapshot kiyohara | `KIYOHARA_SNAPSHOT` | chỉ TOPIX500; không dùng khi nguồn cơ bản là yfinance (giá phải cùng nguồn với 発行済/自己株) |
| số cổ đông, 流通株式 (tiêu chí Prime) | chưa có nguồn | `prime_eligibility` trả null |

Quy ước khi ghép nguồn:
- Yahoo JP `/performance` có HAI khối dự báo: `forecast` (会社予想, yên) và
  `performanceForecastList` (analyst, 百万円, có `totalSampleCount`). Chỉ dùng khối đầu.
- EPS dự phóng không có ở nguồn → `純利益予想 × EPS/純利益 năm gần nhất` (cùng cơ sở cổ phiếu).
- So dự báo với năm thực hiện của CÙNG trang Yahoo JP; OP lệch yfinance >5% ghi vào `notes`.
- yfinance `Investmentin Financial Assets = 0.0` coi là không công bố → net cash null.

Không có nguồn = `null` xuyên suốt, không bao giờ giá trị mặc định.

---

## Jev (L3)

- Registry: `questions/*.yaml`, mỗi câu một bản, có `version`. Đổi chữ → tăng version.
- Chính sách (`config/params.yaml: jev`): noul ≥0,70 đúng, ≤0,30 sai, giữa → null;
  choice cần confidence ≥0,85. **Số lấy từ đo đạc của kiyohara trên câu fx — chưa
  đo trên câu của repo này.** Làm tròn 4 chữ số trước khi so.
- Cache `data/jev-cache.jsonl` khoá (code, id@version, evidence_hash).
- Nhãn bằng chứng (`filing`/`tdnet`/…/`name_only`) đi cùng mỗi Judgment.
- Golden test `tests/test_jev_golden.py` (skip khi thiếu `TYPESAFE_API_KEY`); ca
  `fabricated_name_only` đỏ → dừng dùng Jev, không nới ngưỡng.

## Crew LLM (L6) — model rẻ nhất trước

`EscalatingAgent`: `anthropic/claude-haiku-4-5-20251001` → `anthropic/claude-sonnet-5-5`
→ `anthropic/claude-opus-5-5`. Mỗi bậc fail 2 lần (lỗi, hoặc guardrail từ chối) thì
lên bậc; Task mới bắt đầu lại từ haiku; `guardrail_max_retries=5`; `model_log` ghi
`model_used`. Đầu ra `output_pydantic` (`ArbiterVerdict`, `WriterReport`).

Crew cũ 9 agent (`crew.jsonc`, `agents/`) và `runs/2026-08-23/` giữ nguyên làm lưu trữ.

## Bàn giao Stock JP Bot (Kiyohara + DCF)

`data/tenbagger-candidates.json` theo `schemas/candidate-export.schema.json`:
chỉ tầng A/B/C trong `candidates`; `counts` có cả NONE và số mã thiếu dữ liệu;
mỗi số trong scorecard đi kèm nguồn ở `valuation.sources` / `Sourced`.
