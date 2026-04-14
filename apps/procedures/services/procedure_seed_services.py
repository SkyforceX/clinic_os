from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from ..models import Procedure, ProcedureStep


SEEDED_PROCEDURE_CODES = [
    "QT-CLINICOS-001",
    "QT-CLINICOS-002",
    "QT-CLINICOS-003",
    "QT-CLINICOS-004",
    "QT-CLINICOS-005",
    "QT-CLINICOS-006",
    "QT-CLINICOS-007",
    "QT-CLINICOS-008",
]


@dataclass(frozen=True)
class SeedStep:
    title: str
    description: str
    responsible: str = ""
    duration: str = ""
    color: str = "#0d6efd"
    children: list["SeedStep"] = field(default_factory=list)


@dataclass(frozen=True)
class SeedProcedure:
    code: str
    title: str
    category: str
    description: str
    version: str
    effective_date: date
    status: str
    steps: list[SeedStep]


CLINIC_OS_USAGE_PROCEDURES = [
    SeedProcedure(
        code="QT-CLINICOS-001",
        title="Huong dan dang nhap, phan quyen va dieu huong clinic_os",
        category="operations",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh nen tang danh cho toan bo nhan vien khi bat dau su dung clinic_os: "
            "dang nhap tai khoan staff, hieu co che phan quyen theo group, dung sidebar de truy cap "
            "dung module cong viec va nguyen tac xu ly khi khong thay menu hoac bi tu choi quyen."
        ),
        steps=[
            SeedStep(
                title="Dang nhap tai khoan staff",
                description=(
                    "Mo trang dang nhap staff cua clinic_os, nhap username va password do phong Nhan su "
                    "hoac quan tri he thong cung cap. Neu quen mat khau, thuc hien dung flow quen mat khau "
                    "thay vi tao tai khoan moi."
                ),
                responsible="Toan bo nhan vien",
                duration="1-2 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Kiem tra dung vai tro sau dang nhap",
                description=(
                    "Sau khi vao he thong, doi chieu sidebar va cac menu dang hien thi voi vai tro thuc te "
                    "cua minh nhu Sales Team, Managers, HR Admins, Doctors, Nurses, Executives, "
                    "Operations Team, Accountants, IT Staff."
                ),
                responsible="Nhan vien / Quan ly truc tiep",
                duration="1 phut",
                color="#198754",
                children=[
                    SeedStep(
                        title="Khong thay menu can dung",
                        description=(
                            "Kiem tra lai tai khoan dang dang nhap co dung user hay khong. Neu van thieu, "
                            "lien he HR Admins hoac IT Staff de ra PositionGroupMapping va group Django."
                        ),
                        responsible="Nhan vien / HR Admins / IT Staff",
                        duration="5-10 phut",
                        color="#fd7e14",
                    ),
                    SeedStep(
                        title="Bi bao khong co quyen truy cap",
                        description=(
                            "Chup man hinh trang loi, ghi lai module, thoi diem va thao tac da thuc hien, "
                            "sau do gui ticket Helpdesk hoac bao quan ly."
                        ),
                        responsible="Nhan vien",
                        duration="3 phut",
                        color="#dc3545",
                    ),
                ],
            ),
            SeedStep(
                title="Hieu cau truc sidebar va cac khu vuc chuc nang",
                description=(
                    "Sidebar cua clinic_os chia theo nhom nghiep vu: Tong quan, Kinh doanh, Lich kham "
                    "Doanh nghiep, Quan ly Doanh nghiep, KPI, Giao viec, Cham soc khach hang, Lam sang, "
                    "Lich lam viec, Nhan su, Phe duyet, Quan ly chat luong, Thong ke, Quy trinh va He thong."
                ),
                responsible="Toan bo nhan vien",
                duration="5 phut",
                color="#6f42c1",
            ),
            SeedStep(
                title="Tra cuu quy trinh noi bo truoc khi thao tac",
                description=(
                    "Khi chua ro cach dung mot phan he, vao menu Quy trinh de doc tai lieu tuong ung. "
                    "Uu tien doc quy trinh cung category voi nghiep vu dang xu ly truoc khi thao tac tren du lieu that."
                ),
                responsible="Toan bo nhan vien",
                duration="3-5 phut",
                color="#20c997",
            ),
            SeedStep(
                title="Nguyen tac thao tac du lieu an toan",
                description=(
                    "Khong sua truc tiep du lieu ngoai pham vi cong viec duoc phan quyen. Truoc khi xoa, duyet "
                    "hay khoa du lieu, phai kiem tra chung tu lien quan, nguoi phu trach va tinh trang hien tai "
                    "cua ban ghi."
                ),
                responsible="Toan bo nhan vien",
                duration="Ap dung thuong xuyen",
                color="#212529",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-002",
        title="Quy trinh kinh doanh tu danh muc kham den bao gia va hop dong doanh nghiep",
        category="sale",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Huong dan nghiep vu cho Sales Team va Managers tu luc chuan bi danh muc kham, tao bao gia, "
            "trinh phe duyet den phat hanh ho so hop dong doanh nghiep trong clinic_os."
        ),
        steps=[
            SeedStep(
                title="Kiem tra danh muc kham va goi kham",
                description=(
                    "Vao Catalogs de ra cac category, nhom dich vu va package dang con hieu luc. "
                    "Bao dam gia niem yet, thanh phan goi va mo ta dich vu da cap nhat truoc khi lap bao gia."
                ),
                responsible="Sales Team / Executives",
                duration="10-20 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Tao bao gia doanh nghiep",
                description=(
                    "Mo menu Tao bao gia, nhap thong tin cong ty, dau moi phu trach, danh sach goi kham "
                    "hoac dich vu le, chinh sach gia, chiet khau va phan hoa hong neu co."
                ),
                responsible="Sales Team",
                duration="15-30 phut",
                color="#198754",
                children=[
                    SeedStep(
                        title="Kiem tra preview bao gia",
                        description=(
                            "Su dung man hinh preview de soat format, don gia, tong tien, dieu kien ap dung, "
                            "noi dung phat hanh PDF/DOCX truoc khi trinh duyet."
                        ),
                        responsible="Sales Team",
                        duration="5-10 phut",
                        color="#20c997",
                    ),
                    SeedStep(
                        title="Gui phe duyet bao gia",
                        description=(
                            "Khi noi dung hoan chinh, dung chuc nang submit approval de gui len cap quan ly "
                            "hoac Executives duyet. Khong gui tai lieu ra ngoai khi bao gia chua o trang thai phu hop."
                        ),
                        responsible="Sales Team / Managers",
                        duration="3 phut",
                        color="#fd7e14",
                    ),
                ],
            ),
            SeedStep(
                title="Theo doi phan hoi va chinh sua",
                description=(
                    "Tra cuu tai Danh sach bao gia de xem trang thai draft, cho duyet, da duyet hoac can chinh sua. "
                    "Neu bi reject hoac recall, cap nhat noi dung theo gop y roi gui duyet lai."
                ),
                responsible="Sales Team",
                duration="Theo chu ky dam phan",
                color="#6f42c1",
            ),
            SeedStep(
                title="Tao hop dong doanh nghiep",
                description=(
                    "Khi bao gia duoc chot, chuyen sang man hinh tao hop dong doanh nghiep, nhap dieu khoan chinh, "
                    "thoi gian hieu luc, pham vi kham, dau moi phoi hop va cac tai lieu phat hanh can thiet."
                ),
                responsible="Sales Team / Managers",
                duration="20-40 phut",
                color="#0dcaf0",
            ),
            SeedStep(
                title="Phat hanh ho so hop dong va tai lieu lien quan",
                description=(
                    "Sau khi hop dong duoc phe duyet, su dung chuc nang issue document de phat hanh DOCX/PDF, "
                    "luu dung ban da chot va bao dam ho so phat hanh khop du lieu tren he thong."
                ),
                responsible="Sales Team / Executives",
                duration="5-10 phut",
                color="#212529",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-003",
        title="Quy trinh dang ky lich kham doanh nghiep va theo doi trien khai",
        category="operations",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh su dung cac phan he Contract, Scheduling, Organizations va Implementation Plan "
            "de to chuc lich kham doanh nghiep tu luc mo lich den khi theo doi trien khai."
        ),
        steps=[
            SeedStep(
                title="Khoi tao lich kham cho hop dong",
                description=(
                    "Tai module Lich kham Doanh nghiep, tao lich kham gan voi hop dong da ky, chon cong ty, "
                    "ngay kham, so luong du kien, khung gio va cac thong tin dieu phoi can thiet."
                ),
                responsible="Sales Team / Operations Team",
                duration="10-15 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Phan bo slot va kiem tra nang luc tiep nhan",
                description=(
                    "Mo bang lich chi tiet de kiem tra so slot, tinh trang day/chua day, kha nang tiep nhan cua "
                    "cac ngay kham va dieu chinh phan bo neu can."
                ),
                responsible="Operations Team / Nurses",
                duration="10 phut",
                color="#198754",
            ),
            SeedStep(
                title="Mo cong dang ky cho doanh nghiep hoac danh sach benh nhan",
                description=(
                    "Su dung flow register schedule/booking de cho benh nhan tu dang ky hoac de thu ky y khoa "
                    "nhap lich thay. Luon kiem tra khoang thoi gian contract_start va contract_end."
                ),
                responsible="Nurses / Operations Team",
                duration="Theo ke hoach trien khai",
                color="#20c997",
            ),
            SeedStep(
                title="Theo doi danh sach trien khai",
                description=(
                    "Tai Quan ly Doanh nghiep va Danh sach trien khai, cap nhat tien do chuan bi ho so, "
                    "lay mau, bo tri nhan su, chung tu thanh toan va cac hang muc phat sinh."
                ),
                responsible="Operations Team / Customer Service Team / Sales Team",
                duration="Hang ngay",
                color="#6f42c1",
            ),
            SeedStep(
                title="Xuat bao cao trien khai",
                description=(
                    "Khi can doi soat hoac lam viec voi khach hang, dung chuc nang export excel/print tu "
                    "implementation plan hoac lich kham chi tiet de phat hanh bao cao noi bo."
                ),
                responsible="Operations Team / Managers",
                duration="5-10 phut",
                color="#fd7e14",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-004",
        title="Quy trinh tiep nhan khach hang tai Reception: lookup, check-in, check-out",
        category="customer_care",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh cho bo phan tiep nhan va thu ky y khoa su dung cong cu Reception de tra cuu benh nhan, "
            "check-in, check-out va danh dau quay lai sau trong ngay kham."
        ),
        steps=[
            SeedStep(
                title="Mo cong cu tiep nhan",
                description=(
                    "Vao duong dan tiep nhan/check-in trong clinic_os. Xac nhan dung ca truc, dung nguoi van hanh "
                    "va bao dam may quet barcode hoac ban phim nhap ma BN hoat dong."
                ),
                responsible="Nurses / Reception",
                duration="1 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Tra cuu benh nhan bang ma BN hoac barcode",
                description=(
                    "Quet barcode tren phieu khach hang hoac nhap tay ma BN roi nhan Enter. He thong se goi lookup "
                    "de hien thi thong tin benh nhan, cong ty, ngay sinh, gioi tinh va trang thai hien tai trong ngay."
                ),
                responsible="Nurses / Reception",
                duration="10-20 giay",
                color="#198754",
            ),
            SeedStep(
                title="Thuc hien check-in",
                description=(
                    "Neu benh nhan chua check-in hoac da duoc danh dau quay lai sau, bam nut Check-in. "
                    "Co the nhap ghi chu noi bo neu can bo sung cho ca kham."
                ),
                responsible="Nurses / Reception",
                duration="10 giay",
                color="#20c997",
            ),
            SeedStep(
                title="Thuc hien check-out hoac danh dau quay lai sau",
                description=(
                    "Khi benh nhan hoan tat luot xu ly tai ban tiep nhan, bam Check-out. Neu khach can quay lai "
                    "sau trong ngay, dung nut Quay lai sau de theo doi dung trang thai."
                ),
                responsible="Nurses / Reception",
                duration="10 giay",
                color="#fd7e14",
            ),
            SeedStep(
                title="Xu ly loi thuong gap",
                description=(
                    "Neu khong tim thay ma BN, xac minh lai phieu kham hoac tra cuu tai module Patients/Booking. "
                    "Neu trang thai hien thi khong dung, kiem tra existing record trong ngay va chi chinh khi da xac minh."
                ),
                responsible="Nurses / Operations Team",
                duration="2-5 phut",
                color="#dc3545",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-005",
        title="Quy trinh su dung phan he Clinical cho bac si",
        category="clinical",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh giup Doctors va Managers su dung cac man hinh Clinical nhu Sum Assistant, kham rang, "
            "giai phau benh va tra cuu du lieu lam sang tren clinic_os."
        ),
        steps=[
            SeedStep(
                title="Vao dung phan he lam sang theo nhu cau",
                description=(
                    "Tu sidebar muc Lam sang, chon Sum Assistant khi can tong hop nhanh du lieu benh nhan, "
                    "hoac chon Kham rang/Pathology khi thao tac ho so chuyen biet."
                ),
                responsible="Doctors",
                duration="1 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Tra cuu benh nhan va lich su kham",
                description=(
                    "Nhap patient_id hoac dung du lieu tu danh sach kham de mo ho so. Kiem tra lich su rang ham mat, "
                    "ket qua giai phau benh, du lieu da tai len truoc do va cac thong tin lam sang lien quan."
                ),
                responsible="Doctors",
                duration="2-5 phut",
                color="#198754",
            ),
            SeedStep(
                title="Nhap va cap nhat ket qua lam sang",
                description=(
                    "Ghi nhan phat hien chuyen mon tren man hinh tuong ung, bao dam mo ta ro rang, dung benh nhan "
                    "va dung lan kham. Chi luu khi da hoan thanh phan can nhap."
                ),
                responsible="Doctors",
                duration="5-15 phut",
                color="#20c997",
            ),
            SeedStep(
                title="Su dung AI/assistant ho tro tong hop khi can",
                description=(
                    "Co the dung Sum Assistant hoac AI Assistant de ho tro tong hop, nhung bac si van la nguoi "
                    "chiu trach nhiem kiem tra lai noi dung truoc khi su dung trong van hanh chuyen mon."
                ),
                responsible="Doctors / Managers",
                duration="Tuy ca",
                color="#6f42c1",
            ),
            SeedStep(
                title="Nguyen tac an toan du lieu lam sang",
                description=(
                    "Khong nhap nham ho so benh nhan, khong dung du lieu chua kiem chung de ket luan, va luon "
                    "ra lai file PDF/ket qua upload truoc khi xac nhan su dung."
                ),
                responsible="Doctors",
                duration="Ap dung thuong xuyen",
                color="#212529",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-006",
        title="Quy trinh quan ly nhan su, lich lam viec va lich bac si",
        category="hr",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh danh cho HR Admins, Managers va bo phan dieu phoi de quan ly ho so nhan su, "
            "phong ban, chuc vu, lich lam viec thang va lich bac si trong clinic_os."
        ),
        steps=[
            SeedStep(
                title="Quan ly ho so nhan vien",
                description=(
                    "Vao Nhan su > Danh sach nhan vien de tao moi, xem chi tiet, sua ho so, dieu chuyen "
                    "bo phan hoac offboard nhan su khi can."
                ),
                responsible="HR Admins / Managers",
                duration="10-20 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Chuan hoa phong ban va chuc vu",
                description=(
                    "Dam bao Department, Position va PositionGroupMapping duoc cap nhat dung de sidebar, policy "
                    "va quyen thao tac cua user khop voi co cau to chuc thuc te."
                ),
                responsible="HR Admins",
                duration="Theo dot thay doi co cau",
                color="#198754",
            ),
            SeedStep(
                title="Thiet lap lich lam viec thang",
                description=(
                    "Tai Lich thang, cap nhat ca lam viec theo ma ca cho tung nhan su, theo doi lich su chinh sua "
                    "va ra cac ngay nghi, ngay le, thay doi ca."
                ),
                responsible="HR Admins / Managers",
                duration="Hang tuan hoac hang thang",
                color="#20c997",
            ),
            SeedStep(
                title="Quan ly lich bac si",
                description=(
                    "Dung man hinh doctor schedule de xep ca, luu hang loat, ra tuan bat dau va phan bac si theo "
                    "dung nang luc kham/khung gio lam viec."
                ),
                responsible="HR Admins / Managers",
                duration="15-30 phut",
                color="#fd7e14",
            ),
            SeedStep(
                title="Kiem tra quyen truy cap sau thay doi nhan su",
                description=(
                    "Sau khi tao hoac cap nhat nhan vien, xac minh tai khoan user, trang thai active va cac group "
                    "dang duoc gan trong lich su phan quyen."
                ),
                responsible="HR Admins",
                duration="3-5 phut",
                color="#6f42c1",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-007",
        title="Quy trinh phe duyet, giao viec va hop trien khai",
        category="operations",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh phoi hop noi bo khi can submit phe duyet, tao task trien khai va to chuc meeting "
            "lien phong ban tren clinic_os."
        ),
        steps=[
            SeedStep(
                title="Submit yeu cau phe duyet",
                description=(
                    "Tu tai lieu nguon nhu bao gia hoac hop dong, chon chuc nang submit approval de khoi tao yeu cau, "
                    "dinh kem dung ho so va mo ta ro noi dung can duyet."
                ),
                responsible="Sales Team / Accountants / Managers",
                duration="3-5 phut",
                color="#0d6efd",
            ),
            SeedStep(
                title="Theo doi inbox phe duyet",
                description=(
                    "Executives va nguoi co tham quyen vao Inbox phe duyet de xem danh sach cho xu ly, doc chi tiet, "
                    "approve, reject hoac yeu cau dieu chinh."
                ),
                responsible="Executives / Managers",
                duration="Hang ngay",
                color="#198754",
            ),
            SeedStep(
                title="Tao task trien khai sau khi duoc duyet",
                description=(
                    "Khi ho so da san sang trien khai, vao bang cong viec de tao task, giao nguoi phu trach, deadline, "
                    "pipeline va ghi ro deliverable can hoan thanh."
                ),
                responsible="Managers / Task owners",
                duration="5-10 phut",
                color="#20c997",
            ),
            SeedStep(
                title="To chuc buoi hop trien khai",
                description=(
                    "Neu can phoi hop nhieu bo phan, tao Meeting Session, phan cong khoa/phong tham gia, xac nhan "
                    "shifts, commitments va buoc trien khai hien tai."
                ),
                responsible="Managers / Operations Team",
                duration="15-20 phut",
                color="#fd7e14",
                children=[
                    SeedStep(
                        title="Theo doi commitment sau hop",
                        description=(
                            "Sau cuoc hop, cap nhat cac commitment, han chot, nguoi phu trach va doi chieu voi task "
                            "da tao de tranh bo sot dau viec."
                        ),
                        responsible="Meeting owner / Managers",
                        duration="5-10 phut",
                        color="#6f42c1",
                    ),
                ],
            ),
            SeedStep(
                title="Dong vong kiem soat",
                description=(
                    "Khi cong viec hoan tat, cap nhat task stage, dong meeting neu du dieu kien va dam bao lich su "
                    "phe duyet van truy vet duoc day du."
                ),
                responsible="Managers / Owners",
                duration="Theo tien do cong viec",
                color="#212529",
            ),
        ],
    ),
    SeedProcedure(
        code="QT-CLINICOS-008",
        title="Quy trinh theo doi bao cao, chat luong, Helpdesk va AI ho tro",
        category="it",
        version="1.0",
        effective_date=date(2026, 4, 13),
        status="published",
        description=(
            "Quy trinh ho tro van hanh nang cao cho cap quan ly va cac bo phan chuyen trach khi can xem bao cao, "
            "gui su co chat luong, tao ticket IT hoac dung AI Assistant."
        ),
        steps=[
            SeedStep(
                title="Xem dashboard va bao cao dieu hanh",
                description=(
                    "Executives va Managers dung Dashboard tong quan, Analytics overview, service stats, KPI dashboard "
                    "de theo doi doanh thu, san luong va tien do muc tieu."
                ),
                responsible="Executives / Managers",
                duration="Hang ngay hoac hang tuan",
                color="#0d6efd",
            ),
            SeedStep(
                title="Gui bao cao su co chat luong",
                description=(
                    "Khi phat hien su co chuyen mon, hanh chinh, CNTT hoac an toan nguoi benh, vao module Quality "
                    "de tao incident report voi mo ta day du, dung phan loai va bang chung lien quan."
                ),
                responsible="Toan bo nhan vien / Quality",
                duration="5-15 phut",
                color="#dc3545",
            ),
            SeedStep(
                title="Tao ticket Helpdesk khi co loi he thong",
                description=(
                    "Voi loi phan mem, tai khoan, phan quyen hoac thiet bi IT, tao ticket Helpdesk, mo ta buoc tai hien, "
                    "anh chup loi, muc do anh huong va nguoi lien he."
                ),
                responsible="Managers / IT Staff / Nguoi dung duoc phan quyen",
                duration="5 phut",
                color="#fd7e14",
            ),
            SeedStep(
                title="Su dung AI Assistant dung pham vi",
                description=(
                    "AI Assistant dung de ho tro nhap noi dung, tong hop nhanh hoac goi y xu ly. Khong dung AI thay the "
                    "quyet dinh phe duyet, ket luan chuyen mon hay thao tac du lieu khong duoc kiem chung."
                ),
                responsible="Nguoi dung duoc cap quyen AI",
                duration="Tuy nhu cau",
                color="#6f42c1",
            ),
            SeedStep(
                title="Phan hoi va cai tien quy trinh",
                description=(
                    "Khi phat hien diem nghen, trung thao tac hoac nhu cau bo sung tinh nang, tong hop lai theo quy trinh, "
                    "gui ticket hoac trao doi trong cuoc hop trien khai de cai tien he thong."
                ),
                responsible="Managers / IT Staff / Process owners",
                duration="Theo chu ky cai tien",
                color="#198754",
            ),
        ],
    ),
]


def seed_clinic_os_usage_procedures(*, created_by=None) -> dict:
    created_count = 0
    updated_count = 0
    step_count = 0

    with transaction.atomic():
        for seed in CLINIC_OS_USAGE_PROCEDURES:
            procedure, created = Procedure.objects.get_or_create(
                code=seed.code,
                defaults={
                    "title": seed.title,
                    "category": seed.category,
                    "description": seed.description,
                    "status": seed.status,
                    "version": seed.version,
                    "effective_date": seed.effective_date,
                    "created_by": created_by,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1
                procedure.title = seed.title
                procedure.category = seed.category
                procedure.description = seed.description
                procedure.status = seed.status
                procedure.version = seed.version
                procedure.effective_date = seed.effective_date
                if created_by and procedure.created_by_id != created_by.pk:
                    procedure.created_by = created_by
                procedure.save(
                    update_fields=[
                        "title",
                        "category",
                        "description",
                        "status",
                        "version",
                        "effective_date",
                        "created_by",
                        "updated_at",
                    ]
                )

            procedure.steps.all().delete()
            step_count += _create_steps(procedure=procedure, step_defs=seed.steps)

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "step_count": step_count,
        "procedure_codes": [item.code for item in CLINIC_OS_USAGE_PROCEDURES],
    }


def _create_steps(*, procedure: Procedure, step_defs: list[SeedStep], parent=None) -> int:
    created = 0
    for index, step_def in enumerate(step_defs, start=1):
        step = ProcedureStep.objects.create(
            procedure=procedure,
            parent=parent,
            title=step_def.title,
            description=step_def.description,
            responsible=step_def.responsible,
            duration=step_def.duration,
            order=index,
            color=step_def.color,
        )
        created += 1
        if step_def.children:
            created += _create_steps(
                procedure=procedure,
                step_defs=step_def.children,
                parent=step,
            )
    return created
