Đọc code hiện tại trước khi đề xuất refactor.

Task mode: refactor-safe

Mục tiêu:
- Cải thiện code
- KHÔNG phá behavior hiện tại

Nguyên tắc:
- Không đổi URL
- Không đổi template path
- Không đổi JS contract
- Không phá DB hiện tại

Chiến lược:
1. Xác định phạm vi refactor nhỏ
2. Giữ interface cũ (facade nếu cần)
3. Tách logic vào:
   - selector (read)
   - service (write)

4. Nếu có legacy:
   - giữ lại
   - wrap lại bằng adapter

Output:
1. Vấn đề hiện tại
2. Hướng refactor
3. File cần sửa
4. Code mới (copy-paste được)
5. Đảm bảo backward compatibility

Lưu ý clinic_os:
- ưu tiên refactor từng phần
- không rewrite cả module
- tránh ảnh hưởng template cũ