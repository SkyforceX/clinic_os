Đọc code app contract trước khi sửa.

Task mode: fix-contract-flow

Scope:
- contract
- corporate contract
- preview / print
- liên quan quotation

Checklist:
1. Contract đang phụ thuộc quotation ở đâu?
2. Có snapshot data chưa?
3. Preview đang render từ đâu?
4. Khi delete contract:
   - quotation có được unlock không?

5. Khi tạo contract:
   - data có bị lấy dynamic không?

Output:
1. Root cause
2. File cần sửa
3. Code fix (copy-paste)
4. Note về snapshot

Nguyên tắc:
- contract phải độc lập
- không phụ thuộc quotation sau khi tạo
- preview phải dùng snapshot

Bug thường gặp:
- contract đọc lại quotation.lines
- delete contract không reset quotation
- preview bị lệch dữ liệu