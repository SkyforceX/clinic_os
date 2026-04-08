Đọc code render bảng trước khi sửa.

Task mode: fix-table-render

Mục tiêu:
- Sửa lỗi hiển thị bảng (table)
- Đảm bảo grouping đúng

Checklist:
1. Data structure:
   - có group theo package không?
   - hay đang flatten?

2. Template:
   - loop đang đặt sai level không?
   - có lặp nhầm data không?

3. Payload:
   - backend build đúng chưa?

Output:
1. Root cause
2. File cần sửa (view / service / template)
3. Code fix

Nguyên tắc:
- mỗi package = 1 bảng
- không trộn danh mục giữa package
- số lượng nhân viên phải đúng package

Lưu ý clinic_os:
- nhiều bug nằm ở payload builder (services/selectors)
- template chỉ là nơi hiển thị