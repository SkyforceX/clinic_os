Đọc code hiện tại trước khi kiểm tra.

Task mode: data-consistency-check

Mục tiêu:
- Đảm bảo dữ liệu đúng logic business

Checklist:
1. Data source:
   - lấy từ đâu?

2. Quan hệ:
   - FK đúng không?
   - có mismatch không?

3. Sync:
   - data có bị lệch giữa các bảng không?

4. Snapshot:
   - có bị sai snapshot không?

Output:
1. Kết luận
2. Chỗ sai
3. File cần sửa
4. Code fix

Nguyên tắc:
- ưu tiên đúng dữ liệu hơn đẹp code