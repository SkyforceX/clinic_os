from django.utils.html import escape

from apps.catalogs.models import CheckupCategory
from apps.his_integration.selectors import list_active_his_patients_for_organization


def build_checkup_overview_payload(*, user, company_id):
    patients = list(
        list_active_his_patients_for_organization(organization_id=company_id)
    )

    categories = list(
        CheckupCategory.objects.filter(
            group_checkup__name__icontains="siêu âm"
        )
        .values("id", "item_name")
        .order_by("id")
    )

    thead_cells = [
        '<tr class="text-center">',
        "<th>STT</th>",
        "<th>Mã BN</th>",
        "<th>Họ tên</th>",
        "<th>Giới tính</th>",
        "<th>Ngày sinh</th>",
    ]

    for cat in categories:
        cid = cat["id"]
        item_name = escape(cat["item_name"] or "")
        thead_cells.append(
            f"""
            <th class="text-center">
                <div class="d-flex justify-content-center align-items-center m-0">
                    <label for="toggle_all_{cid}" class="m-0">{item_name}</label>
                </div>
                <div class="form-check d-flex justify-content-center align-items-center m-0">
                    <input class="form-check-input js-col-toggle"
                           type="checkbox"
                           data-cid="{cid}"
                           id="toggle_all_{cid}">
                </div>
            </th>
            """
        )

    thead_cells.append("</tr>")
    thead_html = "".join(thead_cells)

    if not patients:
        colspan = 5 + len(categories)
        tbody_html = (
            f'<tr><td colspan="{colspan}" class="text-center py-4 text-muted">'
            f"Không có bệnh nhân thuộc công ty này.</td></tr>"
        )
        return {
            "success": True,
            "thead_html": thead_html,
            "tbody_html": tbody_html,
            "counts": {"patients": 0, "categories": len(categories)},
        }

    rows = []
    for idx, patient in enumerate(patients, start=1):
        pid = patient.id
        ma_bn = escape(patient.ma_bn or "")
        ho_ten = escape(patient.ho_ten or "")
        gioi_tinh = escape(patient.gioi_tinh or "")
        ngay_sinh = patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else ""

        row = [
            "<tr>",
            f'<td class="text-center">{idx}</td>',
            f'<td class="fw-semibold">{ma_bn}</td>',
            f"<td>{ho_ten}</td>",
            f'<td class="text-center">{gioi_tinh}</td>',
            f'<td class="text-center">{ngay_sinh}</td>',
        ]

        for cat in categories:
            cid = cat["id"]
            checkbox_id = f"svc_{pid}_{cid}"
            item_name = escape(cat["item_name"] or "")
            row.append(
                f"""
                <td class="text-center align-middle checkbox-cell">
                  <div class="form-check d-flex justify-content-center align-items-center m-0">
                    <input class="form-check-input js-col-item"
                           type="checkbox"
                           id="{checkbox_id}"
                           name="selections[{pid}][]"
                           value="{cid}"
                           data-cid="{cid}">
                    <label class="visually-hidden" for="{checkbox_id}">{item_name}</label>
                  </div>
                </td>
                """
            )

        row.append("</tr>")
        rows.append("".join(row))

    tbody_html = "".join(rows)

    return {
        "success": True,
        "thead_html": thead_html,
        "tbody_html": tbody_html,
        "counts": {"patients": len(patients), "categories": len(categories)},
    }
