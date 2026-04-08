Đọc code hiện tại trước khi sửa.

Task mode: fix-template-ui

Mục tiêu:
- Sửa lỗi giao diện (template / HTML / CSS / JS)
- KHÔNG thay đổi logic backend nếu không cần thiết

Nguyên tắc:
- Giữ nguyên layout hiện tại
- Không redesign UI
- Không đổi class CSS trừ khi bắt buộc
- Không phá template inheritance (extends / block)

Quy trình:
1. Xác định template đang render
2. Trace từ view → context → template → JS
3. Kiểm tra data truyền từ Django sang template
4. Kiểm tra JS có override hoặc xử lý sai không

Output:
1. Root cause (UI lỗi do đâu)
2. File template cần sửa
3. Code sửa (copy-paste được)
4. Nếu có JS → chỉ rõ đoạn cần sửa

Lưu ý clinic_os:
- Nhiều page dùng server-render + JS tính toán → phải kiểm tra cả 2
- Bảng (table) phải giữ đúng cấu trúc hiện tại
- Responsive phải không bị vỡ mobile