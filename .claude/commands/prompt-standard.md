đọc repo của app contract trong clinic_os

Lỗi:
- mất định dạng của quill html khi inject vào docx và render ra pdf
- thiếu hiển thị hình ảnh khi hiển thị ra pdf
- bảng giá trong báo giá đã tạo còn thiếu:
    + lưu được % hoa hồng cho sale và công ty
    + chưa hiển thị khung thông tin % hoa hồng ở trang preview báo giá
    + % giảm giá của ô giá ở cột đối tượng khách hàng trong bảng giá chưa hiển thị số % giảm (ví dụ -15%) ở trang preview báo giá, và xuất pdf thiếu % giảm giá ở ô có giảm
- trang preview hợp đồng chưa hiển thị khung thông tin % hoa hồng


Yêu cầu:
- sửa code để lưu % hoa hòng chính xác cho trang tạo báo giá và hiển thị ở trang preview báo gái, và hiển thị đầy đủ ở trang sửa báo giá
- sửa code để hiển thị % giảm giá ở ô có giảm của cột đối tượng khách hàng
- tạo code hiển thị % hoa hồng ở trang preview hợp đồng
- tạo app thư viện để upload ảnh về server ngay khi paste, và có trang quản lý dữ liệu file, hình ảnh, đầy đủ chức năng upload/delete/view file pdf, docx, excel, ảnh....
- sửa hiển thị html của quill thành docx XML block vào document để tránh mất định dạng văn bản
Output:
- tạo full path cho các file cần sửa và các file mới, app mới
- giữ style và layout chuẩn đang có


chỉ đọc file liên quan, không cần đọc toàn bộ repo dự án