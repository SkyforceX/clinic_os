Đọc code hiện tại trước khi tối ưu.

Task mode: performance-optimization

Mục tiêu:
- Tối ưu query, giảm load DB

Checklist:
1. Query:
   - có N+1 không?
   - có filter đúng index không?

2. ORM:
   - dùng select_related?
   - dùng prefetched_related?

3. Aggregation:
   - có loop Python thay vì query DB không?

4. Cache:
   - có cache được không?
   - cache theo tenant?

5. Index:
   - field nào cần index?

Output:
1. Root cause (chậm ở đâu)
2. File cần sửa
3. Code tối ưu
4. Gợi ý index (nếu cần)
5. Note về trade-off

Nguyên tắc:
- ưu tiên sửa query trước
- không optimize sớm quá
- không làm code khó đọc quá mức

Lưu ý clinic_os:
- dashboard thường rất nặng
- cohort / NRR cần aggregate tốt