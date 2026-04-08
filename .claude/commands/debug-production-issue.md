Đọc code hiện tại trước khi debug.

Task mode: debug-production-issue

Mục tiêu:
- Tìm root cause thật sự

Checklist:
1. Triệu chứng:
   - lỗi UI?
   - sai data?
   - crash?

2. Flow:
   - request → view → service → DB → response

3. Data:
   - input có đúng không?
   - DB có dữ liệu không?

4. Edge case:
   - null?
   - empty?
   - race condition?

Output:
1. Root cause thật sự
2. File cần sửa
3. Code fix
4. Cách test lại

Nguyên tắc:
- không đoán
- trace thật
- fix đúng chỗ

Lưu ý clinic_os:
- nhiều bug do legacy + code mới xung đột