# Điều phối alert Zalopay về phòng ban (tham khảo)

> Từ 2026-06-15, routing được thực hiện bằng MÃ (cấu trúc), KHÔNG còn parse file này.
> Tín hiệu điều phối là `bi_product_area` (taxonomy 10 mảng). Email phòng ban lấy từ
> `.env` (RECEIVE_*_EMAIL). Xem `app/modules/alerting/domain/usecases/route_department.py`
> và phần wiring trong `app/main.py`.

Bảng điều phối (mảng sản phẩm phổ biến nhất của cụm → phòng ban → email):

| bi_product_area | Phòng ban | Email (.env) |
| --- | --- | --- |
| Telco | TELCO | RECEIVE_TELCO_EMAIL |
| Loyalty | LOYALTY | RECEIVE_LOYALTY_EMAIL |
| Transfer | TRANSFER | RECEIVE_TRANSFER_EMAIL |
| Bill / OTA / Binding / Financial Service / Daily Life Service / Entertainment / Others | Brand/PR (hộp chung) | RECEIVE_EMAIL |

Quy tắc: chọn mảng sản phẩm xuất hiện NHIỀU NHẤT trong các mention của cụm. Nếu mảng đó
có phòng chuyên trách (Telco/Loyalty/Transfer) → gửi về phòng đó; ngược lại → hộp chung.
Thiếu email phòng trong .env → fallback về RECEIVE_EMAIL.
