Đọc code hiện tại trước khi thiết kế.

Task mode: rag-ai-integration

Mục tiêu:
- Thiết kế RAG (Retrieval Augmented Generation)
- Tích hợp AI vào clinic_os

Scope:
- chatbot nội bộ
- trợ lý bác sĩ / sale
- tìm kiếm dữ liệu

Checklist:
1. Data source:
   - contract
   - quotation
   - medical records
   - documents

2. Storage:
   - vector DB (pgvector?)
   - embedding lưu ở đâu?

3. Pipeline:
   - ingest → embed → store → retrieve → generate

4. Query:
   - user hỏi gì?
   - cần filter theo tenant không?

5. Security:
   - phân quyền dữ liệu
   - không leak data giữa tenant

Output:
1. Kiến trúc RAG
2. Flow chi tiết
3. File cần tạo
4. Code skeleton (service + integration)
5. Cách test local

Nguyên tắc:
- Không embed trực tiếp trong view
- Tách:
  - ingestion service
  - retrieval service
  - generation service

Lưu ý clinic_os:
- Multi-tenant → filter theo tenant_id
- Dữ liệu y tế → cần kiểm soát truy cập