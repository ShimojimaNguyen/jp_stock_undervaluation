`kabutan-{7203,6861,7240,2871}.html`: trang 株探 `/stock/finance` THẬT (2026-09-29),
đã lược phần giữa — chép nguyên từ `kiyohara/src/lib/screen/__fixtures__/`.
Chỉ dùng cho test parser. Có header (sàn/giá/時価総額) và bảng 通期業績;
KHÔNG có bảng 財務 / キャッシュフロー.

`kabutan-synthetic-bs-cf.html`: DỰNG TAY, mã giả 9999 — bảng 財務/CF theo nhãn cột
đã biết, CHƯA đối chiếu trang thật. Lần chạy CI đầu tiên phải kiểm độ phủ hai bảng này.
