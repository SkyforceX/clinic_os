Đọc cả template + JS trước khi sửa.

Task mode: fix-js-data-flow

Mục tiêu:
- Sửa lỗi JS nhưng không phá server-render

Checklist:
1. Data từ Django render ra:
   - có đúng không?
2. JS có overwrite không?
3. Event:
   - click / change có đúng binding không?
4. State:
   - có reset sai không?

Output:
1. Root cause
2. File JS/template cần sửa
3. Code fix

Nguyên tắc:
- không phá data từ backend
- không reset state sai
- giữ UX hiện tại

Bug thường gặp:
- add package → reset data
- biến global bị undefined
- JS giữ state cũ