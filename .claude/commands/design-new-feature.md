Đọc code hiện tại trước khi thiết kế.

Task mode: design-new-feature

Mục tiêu:
- Thiết kế feature mới phù hợp kiến trúc hiện tại

Checklist:
1. Feature thuộc app nào?
2. Có reuse được logic cũ không?
3. Data model:
   - cần model mới?
   - hay extend model cũ?

4. Flow:
   - user action → service → DB → UI

5. Permission:
   - role nào dùng?

Output:
1. Thiết kế tổng thể
2. Danh sách file cần tạo/sửa
3. Code skeleton
4. Luồng hoạt động

Nguyên tắc:
- không tạo app mới nếu không cần
- reuse service / selector cũ nếu có
- follow pattern hiện tại của app

Lưu ý clinic_os:
- ưu tiên consistency hơn “clean architecture”