console.log("incident_report_form.js loaded");

// ==== 1. Map nhóm -> danh sách sự cố cụ thể (ĐỒNG BỘ THEO MODEL IncidentName) ====
const INCIDENT_OPTIONS = {
  "CLINICAL": [
    { value: "wrong_diagnosis",  text: "Chẩn đoán sai / chậm chẩn đoán" },
    { value: "wrong_treatment",  text: "Chỉ định điều trị / thủ thuật không phù hợp" },
    { value: "test_error",       text: "Sai sót xét nghiệm (lấy mẫu, nhãn, xử lý, trả kết quả)" },
    { value: "procedure_error",  text: "Sai sót kỹ thuật / thủ thuật" },
    { value: "clinical_other",   text: "Khác (chuyên môn) – ghi rõ ở phần mô tả" },
  ],

  "ADMIN": [
    { value: "billing_error",    text: "Sai sót thu ngân / thanh toán" },
    { value: "insurance_error",  text: "Sai sót BHYT (hưởng sai, nhập sai thông tin, từ chối không đúng)" },
    { value: "data_entry_error", text: "Nhập liệu hành chính sai / thiếu (họ tên, ngày sinh, địa chỉ...)" },
    { value: "admin_other",      text: "Khác (hành chính) – ghi rõ ở phần mô tả" },
  ],

  "CSKH": [
    { value: "rude_behavior",    text: "Thái độ/giao tiếp chưa phù hợp" },
    { value: "info_miscomm",     text: "Truyền đạt thông tin sai / không đầy đủ cho khách hàng" },
    { value: "cskh_other",       text: "Khác (CSKH) – ghi rõ ở phần mô tả" },
  ],

  "IC": [
    { value: "aseptic_break",    text: "Không tuân thủ vô khuẩn / vệ sinh tay" },
    { value: "waste_error",      text: "Phân loại / xử lý rác y tế không đúng" },
    { value: "ic_other",         text: "Khác (KSNK) – ghi rõ ở phần mô tả" },
  ],

  "SAFETY": [
    { value: "fall",             text: "Ngã / suýt ngã trong cơ sở" },
    { value: "drug_allergy",     text: "Dị ứng thuốc (đã biết / chưa được khai thác) " },
    { value: "med_error",        text: "Sai sót dùng thuốc (nhầm liều, nhầm thuốc, nhầm người bệnh...)" },
    { value: "safety_other",     text: "Khác (an toàn NB) – ghi rõ ở phần mô tả" },
  ],

  "EQUIP": [
    { value: "device_failure",   text: "Thiết bị hỏng / lỗi trong khi sử dụng" },
    { value: "device_unavail",   text: "Thiết bị không sẵn sàng khi cần" },
    { value: "equip_other",      text: "Khác (trang thiết bị) – ghi rõ ở phần mô tả" },
  ],

  "IT": [
    { value: "system_down",       text: "Phần mềm / hệ thống bị treo / không truy cập được" },
    { value: "data_loss",         text: "Mất dữ liệu / sai lệch dữ liệu trên hệ thống" },
    { value: "integration_error", text: "Lỗi kết nối giữa các phần mềm (HIS, LIS, PACS…)" },
    { value: "it_other",          text: "Khác (CNTT) – ghi rõ ở phần mô tả" },
  ],
};


function updateIncidentNameOptions(preserveCurrent) {
  const groupSelect = document.getElementById("id_related_policy");
  const incidentSelect = document.getElementById("id_incident_name");

  if (!groupSelect || !incidentSelect) {
    console.warn("Không tìm thấy select id_related_policy hoặc id_incident_name");
    return;
  }

  // Giá trị hiện tại (từ DB hoặc từ lần chọn trước)
  const currentValue = preserveCurrent ? (incidentSelect.value || "") : "";

  const selectedGroup = (groupSelect.value || "").trim().toUpperCase();
  const options = INCIDENT_OPTIONS[selectedGroup] || [];

  incidentSelect.innerHTML = "";
  incidentSelect.appendChild(new Option("---------", ""));

  options.forEach(opt => {
    const o = new Option(opt.text, opt.value);
    incidentSelect.appendChild(o);
  });

  // Khi load form edit lần đầu: giữ lại giá trị đang có
  if (preserveCurrent && currentValue) {
    incidentSelect.value = currentValue;
  }
}


// ==== 2. Auto-grow cho textarea ====
function autoResizeTextarea(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = el.scrollHeight + "px";
}

// ==== 3. Severity badge ====
function setupSeverityIndicator() {
  const select = document.getElementById("id_severity");
  if (!select) return;

  // Tạo badge sau select nếu chưa có
  let indicator = select.parentElement.querySelector(".severity-indicator");
  if (!indicator) {
    indicator = document.createElement("div");
    indicator.className = "severity-indicator sev-unknown";
    indicator.innerHTML = '<span class="dot"></span><span class="label">Chưa chọn mức độ</span>';
    select.parentElement.appendChild(indicator);
  }

  function updateIndicator() {
      const value = (select.value || "").toUpperCase();
      const text = select.options[select.selectedIndex]?.text || "";

      // Reset toàn bộ class cũ
      indicator.classList.remove(
        "sev-near-miss",
        "sev-no-harm",
        "sev-minor",
        "sev-moderate",
        "sev-severe",
        "sev-death",
        "sev-unknown"
      );

      let levelClass = "sev-unknown";
      let labelText = text || "Chưa chọn mức độ";

      // Mapping đúng theo IncidentSeverity
      switch (value) {
        case "NEAR_MISS":
          levelClass = "sev-near-miss";
          break;

        case "NO_HARM":
          levelClass = "sev-no-harm";
          break;

        case "MINOR":
          levelClass = "sev-minor";
          break;

        case "MODERATE":
          levelClass = "sev-moderate";
          break;

        case "SEVERE":
          levelClass = "sev-severe";
          break;

        case "DEATH":
          levelClass = "sev-death";
          break;

        default:
          levelClass = "sev-unknown";
      }

      indicator.classList.add(levelClass);
      indicator.querySelector(".label").textContent = labelText;
    }


  select.addEventListener("change", updateIndicator);
  // init
  updateIndicator();

  // ==== Đính kèm ảnh: click + preview + paste ====
  const dropzone = document.getElementById("incident-attachment-dropzone");
  const fileInput = document.getElementById("id_attachments");
  const previews = document.getElementById("incident-attachment-previews");

  if (dropzone && fileInput && previews) {
    // Click vào dropzone => mở chọn file
    dropzone.addEventListener("click", function (e) {
      // nếu click đúng vào input rồi thì thôi
      if (e.target === fileInput) return;
      fileInput.click();
    });

    function addFilesToInput(newFiles) {
      const dt = new DataTransfer();

      // giữ lại file cũ đã chọn
      for (const f of fileInput.files) {
        dt.items.add(f);
      }
      // thêm file mới
      for (const f of newFiles) {
        if (!f.type.startsWith("image/")) continue;
        dt.items.add(f);
        renderPreview(f);
      }
      fileInput.files = dt.files;
    }

    function renderPreview(file) {
      const reader = new FileReader();
      reader.onload = function (ev) {
        const item = document.createElement("div");
        item.className = "preview-item";
        const img = document.createElement("img");
        img.src = ev.target.result;
        item.appendChild(img);
        previews.appendChild(item);
      };
      reader.readAsDataURL(file);
    }

    // Khi chọn file thủ công
    fileInput.addEventListener("change", function () {
      // xóa preview cũ và vẽ lại theo file hiện có
      previews.innerHTML = "";
      for (const f of fileInput.files) {
        if (f.type.startsWith("image/")) {
          renderPreview(f);
        }
      }
    });

    // Dán ảnh Ctrl+V (desktop)
    document.addEventListener("paste", function (e) {
      // Cho phép dán nếu focus đang trong form incident
      const active = document.activeElement;
      const incidentRoot = document.querySelector(".incident-form");
      if (!incidentRoot) return;

      const isInsideIncident =
        incidentRoot.contains(active) || active === document.body;

      if (!isInsideIncident) return;

      const items = e.clipboardData && e.clipboardData.items;
      if (!items) return;

      const files = [];
      for (const item of items) {
        if (item.type && item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      }

      if (files.length) {
        e.preventDefault();
        addFilesToInput(files);
      }
    });
  }
}

// ==== 4. DOM ready ====
document.addEventListener("DOMContentLoaded", function () {
  // select 1 -> select 2
  const groupSelect = document.getElementById("id_related_policy");
  if (groupSelect) {
    // Lần đầu load trang (tạo mới hoặc sửa): giữ lại tên sự cố hiện có trong select
    updateIncidentNameOptions(true);

    // Khi user đổi nhóm: reload options, reset lựa chọn
    groupSelect.addEventListener("change", function () {
      updateIncidentNameOptions(false);
    });
  }

  // auto-grow cho tất cả textarea trong incident-form
  document.querySelectorAll(".incident-form textarea").forEach((ta) => {
    autoResizeTextarea(ta);
    ta.addEventListener("input", () => autoResizeTextarea(ta));
  });

  // severity badge
  setupSeverityIndicator();
});
