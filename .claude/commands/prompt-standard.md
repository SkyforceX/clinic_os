đọc repo của app contract trong clinic_os

Lỗi:
- Khi xuất PDF báo giá thì có lỗi:
WeasyPrint could not import some external libraries. Please carefully follow the installation steps before reporting an issue:
https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation
https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting 

-----

Lỗi khi chuyển đổi PDF quotation #13: cannot load library 'C:\Program Files\Tesseract-OCR\libgobject-2.0-0.dll': error 0x7e
HTTP 302 response started for ['127.0.0.1', 52309]
HTTP close for ['127.0.0.1', 52309]
HTTP response complete for ['127.0.0.1', 52309]

Yêu cầu:
- tìm code bị lỗi trong app contract, .env. settings.py và các file liên quan để sửa lỗi

Output:
- tạo code sửa và chỗ sửa


chỉ đọc file liên quan, không cần đọc toàn bộ repo dự án