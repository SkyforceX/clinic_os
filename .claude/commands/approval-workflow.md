Đọc code hiện tại trước khi đề xuất.

Task mode: approval-workflow

Mục tiêu:
- Thiết kế hoặc sửa luồng phê duyệt (approval)
- Phù hợp kiến trúc clinic_os hiện tại

Scope:
- quotation
- contract
- proposal
- payment
- các object có trạng thái

Checklist:
1. State hiện tại:
   - DRAFT / SUBMITTED / APPROVED / REJECTED?
   - Có thiếu state nào không?

2. Role:
   - Ai được submit?
   - Ai được approve?
   - Có multi-level approval không?

3. Logic:
   - Approve có lock dữ liệu không?
   - Reject có rollback không?
   - Có audit log không?

4. UI:
   - Nút approve hiển thị đúng role chưa?
   - Có hiển thị trạng thái rõ ràng không?

5. Data:
   - Có snapshot tại thời điểm duyệt không?

Output:
1. Thiết kế workflow chuẩn
2. State diagram (mô tả text)
3. File cần sửa
4. Code (service / policy / view)
5. Note về backward compatibility

Nguyên tắc:
- Logic duyệt phải nằm ở service
- Permission nằm ở policy
- Không xử lý logic duyệt trong template

Lưu ý clinic_os:
- Approval nên thống nhất 1 pattern dùng chung toàn hệ thống
- Không hardcode role trong view