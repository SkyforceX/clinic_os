"""
Seed nhân viên HRM từ file Excel đã chốt sẵn dữ liệu.
Nguồn:
- Sheet: LƯƠNG NĂM 2025
- Header: hàng 5
- Dữ liệu lấy từ: cột C -> H
- Bắt đầu từ: hàng 13

Mapping:
- C -> full_name
- D -> tax_code
- E -> id_card_number
- F -> address
- G -> email
- H -> phone

Lưu ý:
- Vì phạm vi import không gồm cột mã nhân viên gốc, command này sinh employee_code
  cố định theo số hàng Excel: VMD-<row>, ví dụ VMD-0013.
- Command dùng update_or_create để chạy nhiều lần không bị nhân bản.
"""

from __future__ import annotations

import textwrap

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hrm.models import Employee, EmployeeStatus, EmploymentType


EMPLOYEES = [
    {
        "source_row": 1,
        "employee_code": "VMD-0001",
        "full_name": "Phạm Thế Việt",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "theviet.pham@gmail.com",
        "phone": "0939999999"
    },
    {
        "source_row": 2,
        "employee_code": "VMD-0002",
        "full_name": "Nguyễn Thị Ngọc Châu",
        "tax_code": "03111111111",
        "id_card_number": "03111111111",
        "address": "TP.HCM",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 13,
        "employee_code": "VMD-0013",
        "full_name": "Nguyễn Thị Ngần",
        "tax_code": "034183017666",
        "id_card_number": "034183017666",
        "address": "THÔN 3, EAKHAL, EAH'LEO, ĐĂKLĂK",
        "email": "thuyngan231283@gmail.com",
        "phone": "0937274619"
    },
    {
        "source_row": 14,
        "employee_code": "VMD-0014",
        "full_name": "Nguyễn Huỳnh Diễm My",
        "tax_code": "052199012068",
        "id_card_number": "052199012068",
        "address": "An Lương, Mỹ Chánh, Phù Mỹ, Bình Định",
        "email": "nguyenhuynhdiemmy1011@gmail.com",
        "phone": "0375143321"
    },
    {
        "source_row": 15,
        "employee_code": "VMD-0015",
        "full_name": "Trần Thanh Long",
        "tax_code": "080083015372",
        "id_card_number": "080083015372",
        "address": "10/4 cù khắc kiệm khu phố giống định phường khánh hậu TP Tân An Long An",
        "email": "thanhlongtran963@gmail.com",
        "phone": "0583570441"
    },
    {
        "source_row": 16,
        "employee_code": "VMD-0016",
        "full_name": "Lê Đình Nhân",
        "tax_code": "083083021939",
        "id_card_number": "083083021939",
        "address": "81/6c khu phố 1 Ba triệu thị trấn hóc môn tphcm",
        "email": "lenhan190982@gmail.com",
        "phone": "0907514756"
    },
    {
        "source_row": 17,
        "employee_code": "VMD-0017",
        "full_name": "Trần Kim Hoàng",
        "tax_code": "080060012880",
        "id_card_number": "080060012880",
        "address": "207/39 Bạch Đằng, Tổ 60, P15, Bình Thạnh, TP.HCM",
        "email": "",
        "phone": "0988073030"
    },
    {
        "source_row": 18,
        "employee_code": "VMD-0018",
        "full_name": "Trương Đình Duy",
        "tax_code": "074088057809",
        "id_card_number": "074088057809",
        "address": "Ấp 3 Xã Tân Hưng, Huyện Bàu Bàng, Tỉnh Bình Dương",
        "email": "dinhduy01684338206@gmail.com",
        "phone": "0937463175"
    },
    {
        "source_row": 19,
        "employee_code": "VMD-0019",
        "full_name": "Lê Hiệp Huy",
        "tax_code": "092082016166",
        "id_card_number": "092082016166",
        "address": "197/1/2 Trần Kế Xương, Phường 07, Quận Phú Nhuận, Thành Phố Hồ Chí Minh",
        "email": "huy27081982@gmail.com",
        "phone": "0774828204"
    },
    {
        "source_row": 20,
        "employee_code": "VMD-0020",
        "full_name": "Nguyễn Hồng Thuỳ Trang",
        "tax_code": "079172021476",
        "id_card_number": "079172021476",
        "address": "12, Lô B Phạm Văn Chí, Phường 07, Quận 6, TP.HCM",
        "email": "thuytrang.171272@gmail.com",
        "phone": "0946666756"
    },
    {
        "source_row": 21,
        "employee_code": "VMD-0021",
        "full_name": "Nguyễn Thị Huyền",
        "tax_code": "094175019814",
        "id_card_number": "094175019814",
        "address": "719/7, Lê Hồng Phong, Phường 3, TP. Sóc Trăng, Sóc Trăng",
        "email": "xuanhuyenn1975@gmail.com",
        "phone": "0367788009"
    },
    {
        "source_row": 22,
        "employee_code": "VMD-0022",
        "full_name": "Võ Thị Đan Kim",
        "tax_code": "058181001972",
        "id_card_number": "058181001972",
        "address": "Khu Phố 5 , Phường Phủ Hà, Thành Phố Phan Rang, Tỉnh Ninh Thuận",
        "email": "dankimpr@gmail.com",
        "phone": "0866991599"
    },
    {
        "source_row": 23,
        "employee_code": "VMD-0023",
        "full_name": "Phạm Thị Huệ",
        "tax_code": "089186013896",
        "id_card_number": "089186013896",
        "address": "Mỹ Trung, Mỹ An, Chợ Mới, An Giang",
        "email": "phamhue102@gmail.com",
        "phone": "0906983328"
    },
    {
        "source_row": 24,
        "employee_code": "VMD-0024",
        "full_name": "Nguyễn Thị Hoa",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 25,
        "employee_code": "VMD-0025",
        "full_name": "Triệu Thùy Dung",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 26,
        "employee_code": "VMD-0026",
        "full_name": "Nguyễn Thanh Hà",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 27,
        "employee_code": "VMD-0027",
        "full_name": "Võ Nguyễn Tôn Dương",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 28,
        "employee_code": "VMD-0028",
        "full_name": "Nguyễn Thị Ngọc Nhân",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 29,
        "employee_code": "VMD-0029",
        "full_name": "Phan Quốc Kiều Nguyên",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 30,
        "employee_code": "VMD-0030",
        "full_name": "Bùi Thuỳ Trang",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 31,
        "employee_code": "VMD-0031",
        "full_name": "Phạm Minh Đức",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 32,
        "employee_code": "VMD-0032",
        "full_name": "Nguyễn Hoàng Anh",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 33,
        "employee_code": "VMD-0033",
        "full_name": "Phùng Đắc Thanh Nhân",
        "tax_code": "079098024636",
        "id_card_number": "079098024636",
        "address": "96/5 Bình Tiên, Tổ Dân Phố 58, KP 4, Phường Bình Tiên, TPHCM",
        "email": "michaelnhan1998@gmail.com",
        "phone": "0335471387"
    },
    {
        "source_row": 34,
        "employee_code": "VMD-0034",
        "full_name": "Lê Nguyễn Ngọc Minh",
        "tax_code": "079180018188",
        "id_card_number": "079180018188",
        "address": "19 Tầng 2 Khu Ttbp, Nguyễn Kiệm, Phường 3, Gò Vấp, TP.HCM",
        "email": "ngocminh.droh@gmail.com",
        "phone": "0901694477"
    },
    {
        "source_row": 35,
        "employee_code": "VMD-0035",
        "full_name": "Hà Minh Ngọc",
        "tax_code": "079197016813",
        "id_card_number": "079197016813",
        "address": "56/13 Văn Chung, phường 13, quận Tân Bình, Thành phố Hồ Chí Minh",
        "email": "haminhngoc2015@gmail.com",
        "phone": "0938154564"
    },
    {
        "source_row": 36,
        "employee_code": "VMD-0036",
        "full_name": "Nguyễn Hùng Sơn",
        "tax_code": "052201012736",
        "id_card_number": "052201012736",
        "address": "183 Phạm Văn Đồng, Nhơn Thành, An Nhơn, Bình Định",
        "email": "sonvip2001@gmail.com",
        "phone": "0962810248"
    },
    {
        "source_row": 37,
        "employee_code": "VMD-0037",
        "full_name": "Hoàng Quân",
        "tax_code": "075203008306",
        "id_card_number": "075203008306",
        "address": "Tổ 21, Tân mai 2, Phước Tân, Thành phố Biên Hòa, Đồng Nai",
        "email": "hoangquan.sujian@gmail.com",
        "phone": "0932175782"
    },
    {
        "source_row": 38,
        "employee_code": "VMD-0038",
        "full_name": "Nguyễn Thị Thu Hương",
        "tax_code": "093193002693",
        "id_card_number": "093193002693",
        "address": "Khu Vực 3, Phường I, Thành phố Vị Thanh, Hậu Giang",
        "email": "ntthuong2810@gmail.com",
        "phone": "0904245611"
    },
    {
        "source_row": 39,
        "employee_code": "VMD-0039",
        "full_name": "Nguyễn Phương Uyên",
        "tax_code": "087183001025",
        "id_card_number": "087183001025",
        "address": "230/15 Hai Bà Trưng, P. Tân Định, Quận 1, Tp. Hồ Chí Minh",
        "email": "uyenpenny@gmail.com",
        "phone": "0908540403"
    },
    {
        "source_row": 40,
        "employee_code": "VMD-0040",
        "full_name": "Tô Yến Thu",
        "tax_code": "095191003127",
        "id_card_number": "095191003127",
        "address": "81/24 TA06, KP24, phường thới an, quận 12",
        "email": "toyenthu191219@gmail.com",
        "phone": "0785489479"
    },
    {
        "source_row": 41,
        "employee_code": "VMD-0041",
        "full_name": "Ngô Thị Bích Phượng",
        "tax_code": "072192007875",
        "id_card_number": "072192007875",
        "address": "332/133/4/14, Dương Quảng Hàm, Phường 05, Quận Gò Vấp, Thành phố Hồ Chí Minh",
        "email": "phuongngo155014@gmail.com",
        "phone": "0978155014"
    },
    {
        "source_row": 42,
        "employee_code": "VMD-0042",
        "full_name": "Trương Thị Ngọc Trúc",
        "tax_code": "082197000843",
        "id_card_number": "082197000843",
        "address": "Ấp 8, Tân phước, Gò Công Đông, Tiền Giang",
        "email": "ttntruc4597@gmail.com",
        "phone": "0968838350"
    },
    {
        "source_row": 43,
        "employee_code": "VMD-0043",
        "full_name": "Nguyễn Thiên Chương",
        "tax_code": "079076023321",
        "id_card_number": "079076023321",
        "address": "218 Lô A C/C Phạm Thế Hiển,  Phường 4, Quận 8, TP.HCM",
        "email": "chuongnt.nmt@gmail.com",
        "phone": "0907696989"
    },
    {
        "source_row": 44,
        "employee_code": "VMD-0044",
        "full_name": "Đỗ Như Quỳnh",
        "tax_code": "8941885542",
        "id_card_number": "064300000249",
        "address": "tổ 7, Pleiku, Gia Lai",
        "email": "",
        "phone": "0941778127"
    },
    {
        "source_row": 45,
        "employee_code": "VMD-0045",
        "full_name": "Nguyễn Văn Hội",
        "tax_code": "030083013220",
        "id_card_number": "030083013220",
        "address": "90/45 Trần Văn Ơn, Phường Tân Sơn Nhì, Tp.Hồ Chí Minh",
        "email": "hoinguyen140583@gmail.com",
        "phone": "0908893959"
    },
    {
        "source_row": 46,
        "employee_code": "VMD-0046",
        "full_name": "Lê Nguyễn Bảo San",
        "tax_code": "086197006797",
        "id_card_number": "086197006797",
        "address": "71/34, Nguyễn Văn Thiệt, TP. Vĩnh Long, Vĩnh Long",
        "email": "baosan2105@gmail.com",
        "phone": "0986560637"
    },
    {
        "source_row": 47,
        "employee_code": "VMD-0047",
        "full_name": "Nguyễn Thị Ngọc Hạnh",
        "tax_code": "089197007377",
        "id_card_number": "089197007377",
        "address": "Tổ 18, Ấp Thị, Mỹ Hiệp, Chợ Mới, An Giang",
        "email": "nguyenthingochanh356@gmail.com",
        "phone": "0383174292"
    },
    {
        "source_row": 48,
        "employee_code": "VMD-0048",
        "full_name": "Nguyễn Thị Kiều Tiên",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 49,
        "employee_code": "VMD-0049",
        "full_name": "Phạm Thị Trúc Mai",
        "tax_code": "051199006593",
        "id_card_number": "051199006593",
        "address": "Thôn Vĩnh Xuân, xã Phổ Phong, Thị xã Đức Phổ, tỉnh Quảng Ngãi",
        "email": "dp1.2017.phamthitrucmai@gmail.com",
        "phone": "0965825383"
    },
    {
        "source_row": 50,
        "employee_code": "VMD-0050",
        "full_name": "Nguyễn Ngọc Diễm Trang",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 51,
        "employee_code": "VMD-0051",
        "full_name": "Lê Thị Kiều Chinh",
        "tax_code": "079182003175",
        "id_card_number": "079182003175",
        "address": "73/2/5 Hoàng Văn Thụ, p15, q. Phú Nhuận, Tp. Hồ Chí Minh",
        "email": "vyvyle2684@gmail.com",
        "phone": "0938210018"
    },
    {
        "source_row": 52,
        "employee_code": "VMD-0052",
        "full_name": "Nguyễn Lê Hoàng",
        "tax_code": "079073034756",
        "id_card_number": "079073034756",
        "address": "781/10 Lê Đức Thọ, P. An Hội Đông, TPHCM",
        "email": "hoangnguyenle0717@gmail.com",
        "phone": "0913301298"
    },
    {
        "source_row": 53,
        "employee_code": "VMD-0053",
        "full_name": "Lao Văn Phàng",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 54,
        "employee_code": "VMD-0054",
        "full_name": "Trần Văn Hai",
        "tax_code": "",
        "id_card_number": "",
        "address": "",
        "email": "",
        "phone": ""
    },
    {
        "source_row": 55,
        "employee_code": "VMD-0055",
        "full_name": "Nguyễn Thị Trúc Ly",
        "tax_code": "082197007038",
        "id_card_number": "082197007038",
        "address": "Ấp Mỹ Hội, Mỹ Long, Cai Lậy, Tiền Giang",
        "email": "nttl97ulaw@gmail.com",
        "phone": "0385287166"
    },
    {
        "source_row": 56,
        "employee_code": "VMD-0056",
        "full_name": "Võ Duy Luân",
        "tax_code": "075091005530",
        "id_card_number": "075091005530",
        "address": "95/67 Trương Vĩnh Ký, Phường 12, Tân Bình, Thành phố Hồ Chí Minh",
        "email": "voduyluan11@gmail.com",
        "phone": "0769676919"
    },
    {
        "source_row": 57,
        "employee_code": "VMD-0057",
        "full_name": "Nguyễn Thị Phương Thảo",
        "tax_code": "075300001849",
        "id_card_number": "075300001849",
        "address": "Tổ 4, Ấp Bể Bạc Xuân Đông, Cẩm Mỹ, Đồng Nai",
        "email": "ph.thao216@gmail.com",
        "phone": "0765833958"
    },
    {
        "source_row": 58,
        "employee_code": "VMD-0058",
        "full_name": "Trương Hoàng Thùy Linh",
        "tax_code": "049195000787",
        "id_card_number": "049195000787",
        "address": "Tổ 8, Thôn 1, Tiên Cảnh, Tiên Phước, Quảng NAm",
        "email": "th.thuylinh1601@gmail.com",
        "phone": "0973008010"
    },
    {
        "source_row": 59,
        "employee_code": "VMD-0059",
        "full_name": "Nguyễn Hoàng Khánh Minh",
        "tax_code": "094201008327",
        "id_card_number": "094201008327",
        "address": "Ấp Vĩnh Kiên, Vĩnh Quới, Thị xã Ngã Năm, Sóc Trăng",
        "email": "nguyenhoangkhanhminh010301@gmail.com",
        "phone": "0336114864"
    },
    {
        "source_row": 60,
        "employee_code": "VMD-0060",
        "full_name": "Phan Thị Diễm Kiều",
        "tax_code": "060181003460",
        "id_card_number": "060181003460",
        "address": "Khu phố 4, Phường Tân An, Thị Xã LaGi, Bình Thuận",
        "email": "diemkieu8195@gmail.com",
        "phone": "0966283931"
    }
]


def _clean(value: str) -> str:
    return (value or "").strip()


class Command(BaseCommand):
    help = textwrap.dedent("""\
        Seed danh sách nhân viên HRM từ dữ liệu Excel đã extract sẵn.
        Idempotent: update_or_create theo employee_code.
    """)

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Xem trước, không ghi vào database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        created_count = 0
        updated_count = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN - không lưu dữ liệu.\n"))

        with transaction.atomic():
            for item in EMPLOYEES:
                employee, created = Employee.objects.update_or_create(
                    employee_code=item["employee_code"],
                    defaults={
                        "full_name": _clean(item["full_name"]),
                        "tax_code": _clean(item["tax_code"]),
                        "id_card_number": _clean(item["id_card_number"]),
                        "address": _clean(item["address"]),
                        "email": _clean(item["email"]).lower(),
                        "phone": _clean(item["phone"]),
                        "status": EmployeeStatus.ACTIVE,
                        "employment_type": EmploymentType.FULLTIME,
                        "note": f'',
                    },
                )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'[CREATE] {employee.employee_code} - {employee.full_name}'
                    ))
                else:
                    updated_count += 1
                    self.stdout.write(
                        f'[UPDATE] {employee.employee_code} - {employee.full_name}'
                    )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✔ Hoàn tất. Created={created_count}, Updated={updated_count}, Total={len(EMPLOYEES)}"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN - đã rollback."))
