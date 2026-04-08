Đọc code hiện tại trước khi phân tích.

Task mode: snapshot-integrity-check

Mục tiêu:
- Kiểm tra dữ liệu đang dùng là snapshot hay live data
- Đảm bảo dữ liệu không bị sai khi source thay đổi hoặc bị xóa

Áp dụng cho:
- quotation
- contract
- preview / print
- issued documents

Checklist:
1. Dữ liệu đang render lấy từ đâu?
   - model hiện tại?
   - hay snapshot payload?

2. Khi tạo object:
   - có snapshot toàn bộ data không?
   - hay chỉ lưu reference?

3. Khi source bị sửa/xóa:
   - dữ liệu hiện tại có bị sai không?

4. Preview / print:
   - có phụ thuộc lại source không?
   - hay dùng snapshot?

Output:
1. Kết luận: đang dùng snapshot hay live
2. Nếu sai → chỉ rõ chỗ sai
3. File cần sửa
4. Code fix (copy-paste được)

Nguyên tắc:
- Ưu tiên snapshot
- Không phụ thuộc dữ liệu mutable
- Đảm bảo dữ liệu contract không bị thay đổi theo quotation

Lưu ý clinic_os:
- contract KHÔNG được phụ thuộc quotation sau khi tạo
- preview phải dùng snapshot