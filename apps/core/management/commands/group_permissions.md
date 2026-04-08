# Cấu trúc nhóm phân quyền – clinic_os

> Tài liệu thiết kế nhóm Django cho hệ thống quản lý phòng khám
> khám sức khoẻ doanh nghiệp.

---

## Nhóm & Vai trò

| # | Tên nhóm | Vai trò thực tế | Ghi chú policy |
|---|----------|-----------------|----------------|
| 1 | **Managers** | Trưởng phòng / Quản lý | `ContractPolicy.MANAGER_GROUP_NAMES` |
| 2 | **Sales Team** | Nhân viên kinh doanh | `menu.html` in_group |
| 3 | **Doctor** | Bác sĩ | `menu.html` in_group |
| 4 | **Nurses** | Y tá / Điều dưỡng | `ContractPolicy.NURSE_GROUP_NAMES` |
| 5 | **Executives** | Ban Giám đốc (view-only) | `ContractPolicy.EXECUTIVE_GROUP_NAMES` |
| 6 | **Accountants** | Kế toán / Tài chính | Mới – phiếu thanh toán |
| 7 | **Quality** | Kiểm soát chất lượng | Mới – HSBA & sự cố |

---

## Ma trận quyền theo module

| Module | Managers | Sales Team | Doctor | Nurses | Executives | Accountants | Quality |
|--------|:--------:|:----------:|:------:|:------:|:----------:|:-----------:|:-------:|
| Báo giá (QuotationDraft) | CRUD | CRU | – | – | R | R | – |
| Hợp đồng (Contract) | CRUD | CRU | – | R | R | R | – |
| Phiếu đề xuất (ProposalForm) | CRUD | CRU | – | – | R | R | – |
| Phiếu thanh toán (PaymentVoucher) | CRUD | CRU | – | – | R | CRU | – |
| Kế hoạch thực hiện (ImplementationPlan) | CRUD | CRU | – | – | R | R | – |
| Khách hàng (Company) | CRUD | CRU | – | – | R | R | – |
| Bệnh nhân (Patient) | CRUD | R | R | CR | – | – | R |
| Lịch slot (ScheduleSlot) | CRUD | R | R | R | – | – | – |
| Appointment | CRUD | CRU | R | CRU | – | – | – |
| Phê duyệt (ApprovalRequest) | CRUD | CR | – | – | R | CR | – |
| Lâm sàng – Pathology | CRUD | – | CRU | – | – | – | – |
| Lâm sàng – Dental | CRUD | – | CRU | – | – | – | – |
| Kiểm HSBA (MedicalRecordAudit) | CRUD | – | – | – | – | – | CRUD |
| Báo cáo sự cố (IncidentReport) | CRUD | – | – | – | – | – | CRUD |
| Inbox phê duyệt | ✔ | – | – | – | – | – | – |

> **CRUD** = Create + Read + Update + Delete  
> **CRU** = Create + Read + Update (không xoá)  
> **CR** = Create + Read  
> **R** = Read only  
> **–** = Không có quyền

---

## Quy tắc quan trọng

### 1. Phê duyệt (Approval Workflow)
- Chỉ **Managers** thấy **Inbox phê duyệt** (`ApprovalPolicy.can_view_inbox`)
- Bất kỳ user đăng nhập đều có thể **nộp** tài liệu (`can_submit`)
- Manager **không được tự duyệt** tài liệu do chính mình tạo (trừ superuser)
- **Recall** chỉ được phép khi request vẫn ở trạng thái PENDING

### 2. Hợp đồng & Báo giá
- Chỉ **Managers** có thể approve contract/quotation
- Tài liệu ở trạng thái `is_locked = True` không ai được sửa/xoá (kể cả Manager)
- **Sales Team** chỉ xem/sửa tài liệu do chính mình tạo (trừ Manager override)
- **Executives** chỉ xem, không tạo/sửa/xoá bất kỳ thứ gì

### 3. Bệnh nhân
- **Managers** và user có username trong `DELETE_ALLOWED_USERNAMES` mới được xoá patient
- Import danh sách bệnh nhân: Sales Team & Nurses đều được phép

### 4. Lịch KSK (Scheduling)
- Quản lý slot/giới hạn tổng chỉ **Managers**
- Phân bổ lịch cho hợp đồng: Sales Team (chỉ hợp đồng của mình) + Managers

---

## Triển khai

```bash
# Chạy lần đầu sau migrate
python manage.py seed_groups

# Xem trước (không lưu)
python manage.py seed_groups --dry-run

# In chi tiết từng permission
python manage.py seed_groups --verbosity 2

# Tích hợp vào deploy script
python manage.py migrate && python manage.py seed_groups
```

---

## Cập nhật Policy class

Khi thêm nhóm mới, cần cập nhật các file policy tương ứng:

```python
# apps/contract/policies.py
class ContractPolicy:
    MANAGER_GROUP_NAMES   = {"Manager", "Managers"}
    NURSE_GROUP_NAMES     = {"Nurses"}
    EXECUTIVE_GROUP_NAMES = {"Executive", "Executives"}
    # Thêm nếu cần:
    ACCOUNTANT_GROUP_NAMES = {"Accountants"}
    QUALITY_GROUP_NAMES    = {"Quality"}
```

---

## Thêm nhóm mới vào seed_groups

Mở `apps/core/management/commands/seed_groups.py`, thêm entry vào `GROUP_CONFIG`:

```python
(
    "Tên nhóm",   # ← phải khớp với chuỗi trong Policy class
    "Mô tả tiếng Việt",
    [
        PermSpec("app_label", "model_name_lowercase", ("view", "add", "change")),
        # ...
    ],
),
```
