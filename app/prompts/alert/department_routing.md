# Rule route phòng ban cho alert ZaloPay
#
# Cú pháp mỗi dòng:  <chuỗi khớp (lowercase)> => <Tên phòng ban>
# Khớp theo bi_product_area / nhãn cụm / chủ đề. Dòng bắt đầu bằng # là chú thích.
# Không khớp dòng nào → fallback "Marketing/PR" (xử lý trong code).

thanh toán => Kỹ thuật - Payment
hóa đơn => Kỹ thuật - Payment
chuyển => Kỹ thuật - Payment
nạp => Kỹ thuật - Payment
rút tiền => Kỹ thuật - Payment
ngân hàng => Kỹ thuật - Liên kết ngân hàng
thẻ => Kỹ thuật - Liên kết ngân hàng
chứng khoán => Sản phẩm - Chứng khoán
ví => Sản phẩm - Ví & số dư
số dư => Sản phẩm - Ví & số dư
tài khoản => An ninh & Bảo mật
bảo mật => An ninh & Bảo mật
khuyến mãi => Marketing/PR
hoàn tiền => Marketing/PR
hiệu năng => Kỹ thuật - App
lỗi app => Kỹ thuật - App
cskh => CSKH
hỗ trợ => CSKH
