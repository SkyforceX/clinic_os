// ==== FILTER PATIENT LIST FORM COMPANY SELECT BOX ==== //
// biến toàn cục
const companyFilter = document.getElementById("companyFilter");
const nameFilter = document.getElementById("nameFilter");
const codeFilter = document.getElementById("codeFilter");
const patientContainer = document.getElementById("patientContainer");
let loadedPatients = [];

// Tự động xác định form đang dùng dựa trên URL
let currentFormType = "dental";  // mặc định

const path = window.location.pathname;
if (path.includes("pathology-detail")) {
    currentFormType = "pathology_detail"; // luôn nằm trước "pathology"
}else if (path.includes("pathology")) {
    currentFormType = "pathology";
} else if (path.includes("dental-exam")) {
    currentFormType = "dental";
}

// Hàm render danh sách bệnh nhân
function renderPatients() {
    patientContainer.innerHTML = "";

    const nameSearch = removeVietnameseTones(nameFilter.value.toLowerCase());
    const codeSearch = codeFilter.value.toLowerCase();

    const filtered = loadedPatients.filter(p => {
        const name = removeVietnameseTones(p.ho_ten.toLowerCase());
        const code = p.ma_bn.toLowerCase();
        return name.includes(nameSearch) && code.includes(codeSearch);
    });

    filtered.forEach(p => {
        const div = document.createElement("div");
        div.className = "patient-item";
        div.id = p.ma_bn;
        div.style.cursor = "pointer";
        div.onclick = () => selectPatient(p.id, currentFormType);  // sự kiện click item BN -> auto điền form 'dental'
        div.innerHTML = `
            <div class="patient-name"><strong>${p.ho_ten}</strong></div>
            <div class="patient-meta">${p.gioi_tinh} | ${p.ngay_sinh}</div>
            <div class="patient-code">${p.ma_bn}</div>
        `;
        patientContainer.appendChild(div);
    });
}

// Hàm lấy danh sách bệnh nhân theo công ty hoặc toàn bộ
function fetchPatients() {
    const companyId = companyFilter.value || "";
    nameFilter.value = "";
    codeFilter.value = "";

    patientContainer.innerHTML = "";

    const url = companyId 
        ? `get_patients_by_company/${companyId}/` 
        : `get_all_patients/`;

    fetch(url)
        .then(res => res.json())
        .then(data => {
            loadedPatients = data.patients || [];
            renderPatients();
        });
}

// Xử lý khi chọn công ty
if (companyFilter) {
  companyFilter.addEventListener("change", () => {
      fetchPatients();
  });
}

// Lọc theo tên hoặc mã BN nếu không chọn công ty
if (nameFilter) {
  nameFilter.addEventListener("input", () => {
    if (!companyFilter.value) {
        fetch(`get_all_patients/`)
            .then(res => res.json())
            .then(data => {
                loadedPatients = data.patients || [];
                renderPatients();
            });
    } else {
        renderPatients();
    }
  });
}

if (codeFilter) {
  codeFilter.addEventListener("input", () => {
    if (!companyFilter.value) {
        fetch(`get_all_patients/`)
            .then(res => res.json())
            .then(data => {
                loadedPatients = data.patients || [];
                renderPatients();
            });
    } else {
        renderPatients();
    }
  });
}

// Chuyển chuỗi có dấu thành không dấu
function removeAccents(str) {
  return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

// Tìm kiếm bệnh nhân
// document.addEventListener("DOMContentLoaded", function () {
//   const input = document.querySelector(".patient-filter");
//   const items = document.querySelectorAll(".patient-item");

//   input.addEventListener("input", function () {
//     const filter = removeAccents(this.value.trim());

//     items.forEach((item) => {
//       const name = removeAccents(item.querySelector(".patient-name").textContent);
//       if (name.includes(filter)) {
//         item.style.display = "";
//       } else {
//         item.style.display = "none";
//       }
//     });
//   });
// });

function selectPatient(patient_id, form_type) {
  let url = "";
  if (form_type === "dental") {
    url = `get_dental_data/${patient_id}/`;
  } else if (form_type === "pathology" || form_type === "pathology_detail") {
    url = `get_pathology_data/${patient_id}/`;
  } else {
    alert("Loại form không hợp lệ.");
    return;
  }

  fetch(url)
    .then(response => response.json())
    .then(result => {
      console.log("result:", result);
      console.log("form_type:", form_type);

      if (result.status === "success" && result.data) {
        const data = result.data;

        //###############################
        // Điền thông tin hành chính (chung)
        //###############################
        const infoFields = {
          'patient_id': data.patient_id,
          'patient_code': data.patient_code,
          'full_name': data.full_name,
          'dob': data.dob,
          'gender': data.gender,
        };
        Object.entries(infoFields).forEach(([key, value]) => {
          const el = document.getElementById(key) || document.querySelector(`[name="${key}"]`);
          if (el) {
            if ('value' in el) {
              el.value = value || '';
            } else {
              el.textContent = value || '';
            }
          }
        });

        //###############################
        // Điền dữ liệu form khám răng
        //###############################
        if (form_type === "dental") {
          // Dữ liệu khám răng miệng
          const dentalFields = {
            'dental_exam_id': data.dental_exam_id,
            'other_oral_conditions': data.other_oral_conditions,
            'chewing_ability': data.chewing_ability,
            'conclusion': data.conclusion,
          };
          Object.entries(dentalFields).forEach(([key, value]) => {
            const el = document.getElementById(key) || document.querySelector(`[name="${key}"]`);
            if (el) {
              if ('value' in el) {
                el.value = value || '';
              } else {
                el.textContent = value || '';
              }
            }
          });

          // Phân loại mất răng
          if (data.loss_classification) {
            const radios = document.querySelectorAll('[name="missing_type"]');
            radios.forEach(r => {
              r.checked = r.value === data.loss_classification;
            });
            const lossSelect = document.getElementById("missing_type");
            if (lossSelect) lossSelect.value = data.loss_classification;
          }

          // Phân loại sức khỏe răng miệng
          if (data.health_classification) {
            const healthSelect = document.getElementById("health_classification");
            if (healthSelect) healthSelect.value = data.health_classification;
          }

          // Dữ liệu răng chi tiết
          if (data.tooth_details) {
            Object.entries(data.tooth_details).forEach(([fieldName, value]) => {
              const input = document.querySelector(`[name="${fieldName}"]`);
              if (input) input.value = value || '';
            });
          }
        }

        //###############################
        // Form upload file giải phẫu bệnh - không cần xử lý thêm
        if (form_type === "pathology") {
          const selectedOption = companyFilter.options[companyFilter.selectedIndex];  // const companyFilter => global.js
          const companyName = selectedOption.dataset.value || "";
          document.getElementById("company").value = companyName;
        }
        //###############################

        //###############################
        // Điền dữ liệu form kết quả giải phẫu bệnh
        //###############################
        // ✅ Nếu là form pathology_detail → hiển thị danh sách GPB
        if (form_type === "pathology_detail" && data.results) {
          console.log("✓ Vào phần xử lý pathology_detail");
          console.log("data.results:", data.results);
          const container = document.getElementById("resultList");
          container.innerHTML = "";

          data.results.forEach((r, index) => {
            const div = document.createElement("div");
            div.className = "mb-3";
            div.id = `evaluation_${r.id}`;

            // Xác định màu nền theo đánh giá
            let bgClass = "";
            if (r.evaluation === 'normal') {
              bgClass = "bg-success bg-opacity-10 border border-success p-2 rounded transition-bg";
            } else if (r.evaluation === 'follow') {
              bgClass = "bg-danger bg-opacity-10 border border-danger p-2 rounded transition-bg";
            }

            div.innerHTML = `
              <div class="card-body ${bgClass}" id="card_body_${r.id}">
                <p><strong>Vị trí lấy mẫu:</strong> ${r.location}</p>
                <p><strong>Ngày ra kết quả:</strong> ${r.result_date}</p>

                <div class="mb-3" id="evaluation_${r.id}">
                  <label class="me-3">
                    <input type="radio" name="eval_${r.id}" value="normal" ${r.evaluation === 'normal' ? 'checked' : ''}> Bình thường
                  </label>
                  <label>
                    <input type="radio" name="eval_${r.id}" value="follow" ${r.evaluation === 'follow' ? 'checked' : ''}> Theo dõi
                  </label>
                  <button class="btn btn-sm btn-success ms-3" onclick="updateEvaluation(${r.id})">Cập nhật</button>
                </div>
                <div id="status_msg_${r.id}" class="mt-2"></div>

                <div class="mb-3">
                  <label><strong>Kết quả:</strong></label>
                  <textarea class="form-control bg-light" rows="3" readonly>${r.manual_conclusion}</textarea>
                </div>

                <div class="mb-3">
                  <label><strong>Kết quả (trích xuất tự động):</strong></label>
                  <textarea class="form-control bg-light" rows="3" readonly>${r.auto_extracted_text}</textarea>
                </div>

                <button class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#pdfModal_${r.id}">
                  📄 Xem file PDF
                </button>
              </div>

              <div class="modal fade" id="pdfModal_${r.id}" tabindex="-1" aria-labelledby="pdfModalLabel_${r.id}" aria-hidden="true">
                <div class="modal-dialog modal-xl modal-dialog-centered">
                  <div class="modal-content">
                    
            
                    <div class="modal-header bg-light border-bottom">
                      <div class="container-fluid">
                        <div class="row g-3 align-items-center">
                          <div class="col-md-3">
                            <strong>👤 Họ tên:</strong> <span class="text-dark">${data.full_name}</span>
                          </div>
                          <div class="col-md-3">
                            <strong>🎂 Ngày sinh:</strong> <span class="text-dark">${data.dob}</span>
                          </div>
                          <div class="col-md-3">
                            <strong>👩‍⚕️ Giới tính:</strong> <span class="text-dark">${data.gender}</span>
                          </div>
                          <div class="col-md-3">
                            <strong>🆔 Mã BN:</strong> <span class="text-dark">${data.patient_code}</span>
                          </div>
                        </div>
                      </div>
                      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Đóng"></button>
                    </div>

                    <!-- Body PDF -->
                    <div class="modal-body">
                        ${r.file_exists ? `
                        <iframe src="${r.file_url}" width="100%" height="600px" style="border: none; border-radius: 6px; box-shadow: 0 0 6px rgba(0,0,0,0.1);"></iframe>
                      ` : `
                        <div class="alert alert-warning d-flex align-items-center" role="alert">
                          <i class="bi bi-exclamation-triangle-fill me-2"></i>
                          ⚠️ Không tìm thấy file PDF.
                        </div>
                      `}
                    </div>
                    
                  </div>
                </div>
              </div>

            `;
            container.appendChild(div);
          });
        }
      } else {
        alert(result.message || "Không tìm thấy dữ liệu.");
      }
    })
    .catch(error => {
      // console.error("Lỗi khi tải dữ liệu:", error);
      alert(error);
    });
}

const today = new Date().toISOString().split('T')[0];
const printDateEl = document.getElementById('printDate');
if (printDateEl) {
  printDateEl.value = today || "";
}

document.addEventListener('DOMContentLoaded', function () {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = "opacity 0.5s ease";
      alert.style.opacity = "0";
      setTimeout(() => alert.remove(), 500);
    }, 4000);
  });

  const btnSaveAndPrint = document.getElementById('btnSaveAndPrint');
  const btnSaveOnly = document.getElementById('btnSaveOnly');
  const dentalForm = document.getElementById('dental-exam-form');
  const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');

  if (btnSaveAndPrint && dentalForm && csrfInput) {
    btnSaveAndPrint.addEventListener('click', function () {
      const formData = new FormData(dentalForm);
      const csrfToken = csrfInput.value;

      fetch(API_SAVE_DENTAL_EXAM_URL, {
          method: 'POST',
          headers: {
              'X-CSRFToken': csrfToken
          },
          body: formData
      })
      .then(response => response.json())
      .then(data => {
          if (data.status === 'success') {
              in_phieu();
          } else {
              alert('❌ Lỗi khi lưu dữ liệu: ' + data.message);
          }
      })
      .catch(error => {
          console.error('Lỗi in', error);
      });
    });
  }

  if (btnSaveOnly && dentalForm && csrfInput) {
    btnSaveOnly.addEventListener('click', function (e) {
      e.preventDefault();

      const formData = new FormData(dentalForm);

      fetch(window.location.href, {
          method: 'POST',
          body: formData,
          headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': csrfInput.value
          }
      })
      .then(response => response.json())
      .then(data => {
          if (data.success) {
            showSuccessToast("Lưu dữ liệu thành công");
          } else {
            showCustomToast(data.message || 'Lưu dữ liệu thất bại!');
          }
      })
      .catch(error => {
        showCustomToast('Có lỗi kết nối server!');
        console.error(error);
      });
    });
  }

  initListCompanyPatientActions();
});

function in_phieu() {
  try {
    // Lấy dữ liệu từ form
    const hoTen = document.querySelector('[name="full_name"]').value || "";
    const maBN = document.querySelector('[name="patient_code"]').value || "";
    const ngaySinh = document.querySelector('[name="dob"]').value || "";
    const gioiTinh = document.querySelector('[name="gender"]').value || "";
    const missing_type = document.querySelector('#missing_type').value || "";
    const other_conditions = document.querySelector('[name="other_oral_conditions"]').value || "";
    const conclusion = document.querySelector('[name="conclusion"]').value || "";
    const sucNhai = document.querySelector('[name="chewing_ability"]').value || "";
    const health_classification = document.querySelector('[name="health_classification"]').value || "";
    const full_name_signature = document.getElementById('js-print-fullname-signature').textContent || "";

    const printDateInput = document.getElementById("printDate").value || "";
    let printDateFormatted = "";

    if (printDateInput) {
        const [year, month, day] = printDateInput.split("-");
        printDateFormatted = `Ngày ${day} tháng ${month} năm ${year}`;
    } else {
        // fallback nếu không có ngày
        const now = new Date();
        const ngay = now.getDate().toString().padStart(2, '0');
        const thang = (now.getMonth() + 1).toString().padStart(2, '0');
        const nam = now.getFullYear();
        printDateFormatted = `Ngày ${ngay} tháng ${thang} năm ${nam}`;
    }

    const upperTeeth = [18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28];
    const lowerTeeth = [48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38];

    // Clone nội dung printSection
    const printContent = document.getElementById("printSection").cloneNode(true);

    // Gán nội dung động vào thẻ span
    printContent.querySelector(".js-print-fullname").textContent = hoTen;
    printContent.querySelector(".js-print-ID").textContent = maBN;
    printContent.querySelector(".js-print-dob").textContent = ngaySinh;
    printContent.querySelector(".js-print-gender").textContent = gioiTinh;
    printContent.querySelector("#printMissing_type").textContent = missing_type;
    printContent.querySelector("#printOther_conditions").textContent = other_conditions;
    printContent.querySelector("#printSucNhai").textContent = sucNhai + ' %';
    printContent.querySelector(".js-health-classification").textContent = health_classification;
    printContent.querySelector(".js-print-date").textContent = printDateFormatted;

    // Nếu là Bs. Đỗ Thị Hoạt thì hiển thị ảnh chữ ký
    if (full_name_signature.trim() !== 'Đỗ Thị Hoạt') {
      const signatureImg = printContent.querySelector('#signature-img');
      if (signatureImg) {
          signatureImg.classList.add('hidden');
      }
    }else{
      const signatureImg = printContent.querySelector('#signature-img');
        if (signatureImg) {
            signatureImg.classList.remove('hidden');
        }
    }

    const conclusionSpan = printContent.querySelector("#printConclusion");
    if (conclusionSpan) conclusionSpan.textContent = conclusion;

    upperTeeth.forEach(tooth => {
        const val = document.querySelector(`[name="tooth_upper_${tooth}"]`).value || "";
        const cell = printContent.querySelector(`#printTooth_${tooth}`);
        if (cell) cell.textContent = val;
    });

    lowerTeeth.forEach(tooth => {
        const val = document.querySelector(`[name="tooth_lower_${tooth}"]`).value || "";
        const cell = printContent.querySelector(`#printTooth_${tooth}`);
        if (cell) cell.textContent = val;
    });

    // lấy giá trị ngày tháng năm hiện tại
    // const now = new Date();
    // const ngay = now.getDate().toString().padStart(2, '0');
    // const thang = (now.getMonth() + 1).toString().padStart(2, '0'); // Tháng bắt đầu từ 0
    // const nam = now.getFullYear();
    // const formattedDate = `Ngày ${ngay} tháng ${thang} năm ${nam}`;
    // printContent.querySelector(".js-print-date").textContent = formattedDate;

    // Tạo cửa sổ mới để in
    const printWindow = window.open('', '_blank', 'width=1000, height=1000, scrollbars=yes');
    printWindow.document.write(`
        <html>
        <head>
            
            <title>Phiếu khám RHM</title>
            <link rel="stylesheet" href="${window.location.origin}/static/clinic/css/print.css">
        </head>
        <body>
            <div class="print-preview-wrapper">
                <div class="print-a4">
                    ${printContent.outerHTML}
                </div>
            </div>
        </body>
        </html>
    `);

    printWindow.document.close(); // Đảm bảo hoàn tất ghi nội dung
    printWindow.onload = function () {
      printWindow.focus();         // Focus vào cửa sổ in
      printWindow.print();         // Gọi lệnh in
      printWindow.onafterprint = function () {
          //printWindow.close();
      };
    };
  } catch (e) {
    alert("Đã xảy ra lỗi khi tạo phiếu in:\n" + e.message);
    console.error("Print error:", e);
  }
}


// xóa form khám
function clearDentalForm() {
  // Xóa tất cả các input, textarea, radio, checkbox từ phần than phiền chính trở xuống
  const container = document.querySelector('.js-form-container'); // Gán đúng ID vùng muốn reset
  if (!container) return;
  // Reset các trường input & textarea
  container.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(el => {
      el.value = '';
      el.classList.remove('highlight-nonzero', 'highlight-empty');
  });

  // Reset radio/checkbox
  container.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach(el => el.checked = false);
}

// tự động điền tất cả input là 0
function fillMainComplainWithZero() {
  // Lấy tất cả input trong khu vực Than phiền chính
  const mainComplainInputs = document.querySelectorAll('.js-complaint-table input[type="text"]');
  mainComplainInputs.forEach(input => {
    input.value = '0';
  });
    updateInputHighlights(); // 🔥 Gọi lại cập nhật mà
}

//   tự động điền giá trị vào input khi click vào các chú thích
document.addEventListener("DOMContentLoaded", () => {
  let activeInput = null;

  document.addEventListener("focusin", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
      activeInput = e.target;
    }
  });

  document.querySelectorAll(".note-item").forEach((item) => {
    item.addEventListener("click", () => {
      if (!activeInput) return;

      const value = item.dataset.value || "";
      const cursorPos = activeInput.selectionStart;
      const original = activeInput.value || "";

      // Tìm từ gần con trỏ bằng regex
      const wordRegex = /\S+/g;
      let match, closestWord = "", closestStart = -1, closestEnd = -1;

      while ((match = wordRegex.exec(original)) !== null) {
        const start = match.index;
        const end = start + match[0].length;
        if (cursorPos >= start && cursorPos <= end) {
          closestWord = match[0];
          closestStart = start;
          closestEnd = end;
          break;
        }
      }

      if (closestWord === value) {
        // Nếu trùng thì xoá
        const newVal =
          original.slice(0, closestStart).trimEnd() +
          " " +
          original.slice(closestEnd).trimStart();
        const newCursor = original.slice(0, closestStart).trimEnd().length + 1;
        activeInput.value = newVal.trim();
        activeInput.setSelectionRange(newCursor, newCursor);
      } else if (closestWord) {
        // Nếu có từ gần đó, thay thế
        const newVal =
          original.slice(0, closestStart) + value + original.slice(closestEnd);
        const newCursor = closestStart + value.length;
        activeInput.value = newVal;
        activeInput.setSelectionRange(newCursor, newCursor);
      } else {
        // Nếu không có từ nào thì thêm mới
        const needsSpace =
          cursorPos > 0 && original[cursorPos - 1] !== " ";
        const space = needsSpace ? " " : "";
        const newVal =
          original.slice(0, cursorPos) +
          space +
          value +
          " " +
          original.slice(cursorPos);
        const newCursor = cursorPos + space.length + value.length + 1;
        activeInput.value = newVal.trim();
        activeInput.setSelectionRange(newCursor, newCursor);
      }

      activeInput.focus();
      updateInputHighlights(); // 🔥 Gọi lại cập nhật màu
    });
  });
});

// Gọi lần đầu để tô màu các input đã có sẵn
updateInputHighlights();
// tự động tô màu input
function updateInputHighlights() {
  document.querySelectorAll(".complaint-table td input").forEach((input) => {
    const val = input.value.trim();

    input.classList.remove("highlight-nonzero", "highlight-empty");

    if (val === "") {
      input.classList.add("highlight-empty");
    } else if (!isNaN(val) && parseFloat(val) !== 0) {
      input.classList.add("highlight-nonzero");
    }
  });
}

// Gọi ban đầu
updateInputHighlights();
// Gọi mỗi khi người dùng thay đổi input
document.querySelectorAll(".complaint-table td input").forEach((input) => {
  input.addEventListener("input", updateInputHighlights);
});

// chỉ cho phép nhập các giá trị từ 1 đến 11, 11.1–11.4 hoặc √1, ngăn cách bằng dấu phẩy
function validateMainComplain(input) {
  const value = input.value.trim() || "";
  const allowedValues = [
    ...Array.from({length: 11}, (_, i) => (i + 1).toString()),  // '1' đến '11'
    ...['11.1', '11.2', '11.3', '11.4'],
    '√1'
  ];

  // Nếu nhập nhiều mã cách nhau bằng dấu phẩy, kiểm tra từng mã
  const values = value.split(',').map(v => v.trim());

  const allValid = values.every(v => allowedValues.includes(v));
  if (!allValid) {
    input.setCustomValidity("Chỉ nhập giá trị từ 1 đến 11, 11.1–11.4 hoặc √1.");
    input.reportValidity();
  } else {
    input.setCustomValidity('');
  }
}

// giới hạn nhập số từ 1 đến 100 cho sức nhai
function validateSucNhai(input) {
  let value = input.value || "";

  // Nếu người dùng nhập quá 3 ký tự, cắt bớt
  if (value.length > 3) {
    input.value = value.slice(0, 3);
    return;
  }

  // Chuyển sang số để kiểm tra logic
  const num = parseInt(value);

  if ((num > 100) || (num < 1)) {
    input.setCustomValidity("Chỉ được nhập số từ 1 đến 100");
    input.reportValidity();
  } else {
    input.setCustomValidity("");
  }

  // Nếu nhập không phải là số, cũng báo lỗi
  if (isNaN(num)) {
    input.setCustomValidity("Vui lòng nhập số hợp lệ từ 1 đến 100");
    input.reportValidity();
  }
}

//###############################
// Cập nhật đánh giá kết quẩ (pathology_detail.html)
//###############################
function updateEvaluation(resultId) {
  const radios = document.getElementsByName(`eval_${resultId}`);
  const msgDiv = document.getElementById(`status_msg_${resultId}`);
  const cardBody = document.getElementById(`card_body_${resultId}`);

  let selectedValue = '';
  radios.forEach(r => { if (r.checked) selectedValue = r.value || ""; });

  if (!selectedValue) {
    msgDiv.innerHTML = `<div class="text-danger status-msg">⚠️ Vui lòng chọn một đánh giá.</div>`;
    setTimeout(() => { msgDiv.innerHTML = ''; }, 3000);
    return;
  }

  // Hiển thị spinner trong quá trình cập nhật
  msgDiv.innerHTML = `<div class="text-secondary">
    <span class="spinner-border spinner-border-sm me-1"></span>Đang cập nhật...
  </div>`;

  fetch(`update_pathology_evaluation/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify({
      result_id: resultId,
      evaluation: selectedValue
    })
  })
  .then(res => {
    if (!res.ok) throw new Error("Lỗi kết nối server");
    return res.json();
  })
  .then(data => {
    if (data.status === "success") {
      // ✅ Hiển thị thông báo
      msgDiv.innerHTML = selectedValue === "normal"
        ? `<div class="text-success status-msg">✔️ Đã cập nhật: <strong>Bình thường</strong></div>`
        : `<div class="text-danger status-msg">⚠️ Đã cập nhật: <strong>Theo dõi</strong></div>`;

      // 🎨 Cập nhật màu nền theo đánh giá
      cardBody.classList.remove('bg-success', 'bg-danger', 'border', 'border-success', 'border-danger', 'bg-opacity-10');
      if (selectedValue === 'normal') {
        cardBody.classList.add('bg-success', 'bg-opacity-10', 'border', 'border-success', 'rounded', 'p-2');
      } else {
        cardBody.classList.add('bg-danger', 'bg-opacity-10', 'border', 'border-danger', 'rounded', 'p-2');
      }

    } else {
      throw new Error(data.message || "Lỗi không xác định");
    }
  })
  .catch(err => {
    msgDiv.innerHTML = `<div class="text-danger status-msg">❌ ${err.message}</div>`;
  })
  .finally(() => {
    setTimeout(() => { msgDiv.innerHTML = ''; }, 3000);
  });
}

// js modal edit - delete - toast patient in list
function initListCompanyPatientActions() {
  const editModalEl = document.getElementById('editPatientModal');
  const deleteModalEl = document.getElementById('deletePatientModal');
  const editForm = document.getElementById('editPatientForm');
  const confirmDeleteBtn = document.getElementById('confirmDeletePatientBtn');

  if (!editModalEl || !deleteModalEl || !editForm || !window.CLINIC_PATIENT_AJAX) {
    return;
  }

  const editModal = new bootstrap.Modal(editModalEl);
  const deleteModal = new bootstrap.Modal(deleteModalEl);

  function clearEditErrors() {
    ['ma_bn', 'ho_ten', 'gioi_tinh', 'ngay_sinh'].forEach(name => {
      const input = document.getElementById(`edit_${name}`);
      const error = document.getElementById(`error_${name}`);
      if (input) input.classList.remove('is-invalid');
      if (error) error.textContent = '';
    });

    const generalError = document.getElementById('editPatientGeneralError');
    if (generalError) {
      generalError.classList.add('d-none');
      generalError.textContent = '';
    }
  }

  function setEditLoading(isLoading) {
    const btn = document.getElementById('savePatientBtn');
    if (!btn) return;

    const text = btn.querySelector('.js-btn-text');
    const spinner = btn.querySelector('.js-btn-spinner');

    btn.disabled = isLoading;
    if (spinner) spinner.classList.toggle('d-none', !isLoading);
    if (text) text.textContent = isLoading ? 'Đang lưu...' : 'Lưu thay đổi';
  }

  function setDeleteLoading(isLoading) {
    if (!confirmDeleteBtn) return;

    const text = confirmDeleteBtn.querySelector('.js-btn-text');
    const spinner = confirmDeleteBtn.querySelector('.js-btn-spinner');

    confirmDeleteBtn.disabled = isLoading;
    if (spinner) spinner.classList.toggle('d-none', !isLoading);
    if (text) text.textContent = isLoading ? 'Đang xóa...' : 'Xóa';
  }

  function showListCompanyToast(message, type = 'success') {
    const toastEl = document.getElementById('listCompanyToast');
    const toastBody = document.getElementById('listCompanyToastBody');
    if (!toastEl || !toastBody) return;

    toastBody.textContent = message;
    toastEl.classList.remove('text-bg-success', 'text-bg-danger', 'text-bg-warning');
    toastEl.classList.add(
      type === 'success' ? 'text-bg-success' :
      type === 'warning' ? 'text-bg-warning' : 'text-bg-danger'
    );

    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 3000 });
    toast.show();
  }

  function updatePatientRow(patient) {
    const row = document.getElementById(`patient-row-${patient.id}`);
    if (!row) return;

    row.querySelector('.patient-ma-bn').textContent = patient.ma_bn;
    row.querySelector('.patient-ho-ten').textContent = patient.ho_ten;
    row.querySelector('.patient-gioi-tinh').textContent = patient.gioi_tinh;

    const ngaySinhCell = row.querySelector('.patient-ngay-sinh');
    if (ngaySinhCell) {
      ngaySinhCell.textContent = patient.ngay_sinh;
      ngaySinhCell.dataset.date = patient.ngay_sinh_iso;
    }

    const editBtn = row.querySelector('.js-edit-patient-btn');
    if (editBtn) {
      editBtn.dataset.maBn = patient.ma_bn;
      editBtn.dataset.hoTen = patient.ho_ten;
      editBtn.dataset.gioiTinh = patient.gioi_tinh;
      editBtn.dataset.ngaySinh = patient.ngay_sinh_iso;
    }

    const deleteBtn = row.querySelector('.js-delete-patient-btn');
    if (deleteBtn) {
      deleteBtn.dataset.patientName = patient.ho_ten;
    }
  }

  function reindexPatientRows() {
    document.querySelectorAll('#patientTableBody tr').forEach((row, index) => {
      const sttCell = row.querySelector('.patient-stt');
      if (sttCell) sttCell.textContent = index + 1;
    });
  }

  document.addEventListener('click', function (e) {
    const editBtn = e.target.closest('.js-edit-patient-btn');
    if (editBtn) {
      clearEditErrors();

      document.getElementById('edit_patient_id').value = editBtn.dataset.patientId || '';
      document.getElementById('edit_ma_bn').value = editBtn.dataset.maBn || '';
      document.getElementById('edit_ho_ten').value = editBtn.dataset.hoTen || '';
      document.getElementById('edit_gioi_tinh').value = editBtn.dataset.gioiTinh || '';
      document.getElementById('edit_ngay_sinh').value = editBtn.dataset.ngaySinh || '';

      editModal.show();
      return;
    }

    const deleteBtn = e.target.closest('.js-delete-patient-btn');
    if (deleteBtn) {
      document.getElementById('delete_patient_id').value = deleteBtn.dataset.patientId || '';
      document.getElementById('delete_patient_name').textContent = deleteBtn.dataset.patientName || '';
      deleteModal.show();
    }
  });

  editForm.addEventListener('submit', function (e) {
    e.preventDefault();
    clearEditErrors();
    setEditLoading(true);

    const patientId = document.getElementById('edit_patient_id').value;
    const formData = new FormData(editForm);
    const csrfToken = editForm.querySelector('[name=csrfmiddlewaretoken]').value;
    const url = window.CLINIC_PATIENT_AJAX.updateBaseUrl.replace('/0/', `/${patientId}/`);

    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: formData
    })
    .then(async response => {
      const data = await response.json();
      if (!response.ok) {
        throw data;
      }
      return data;
    })
    .then(data => {
      updatePatientRow(data.patient);
      editModal.hide();
      showListCompanyToast(data.message || 'Cập nhật thành công', 'success');
    })
    .catch(error => {
      if (error && error.errors) {
        Object.entries(error.errors).forEach(([field, message]) => {
          const input = document.getElementById(`edit_${field}`);
          const errorBox = document.getElementById(`error_${field}`);
          if (input) input.classList.add('is-invalid');
          if (errorBox) errorBox.textContent = message;
        });
      } else {
        const generalError = document.getElementById('editPatientGeneralError');
        if (generalError) {
          generalError.textContent = error.message || error.message || 'Có lỗi xảy ra khi cập nhật.';
          generalError.classList.remove('d-none');
        }
        showListCompanyToast(error.message || 'Cập nhật thất bại', 'danger');
      }
    })
    .finally(() => {
      setEditLoading(false);
    });
  });

  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', function () {
      const patientId = document.getElementById('delete_patient_id').value;
      const csrfToken = document.querySelector('#editPatientForm [name=csrfmiddlewaretoken]')?.value
        || document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || '';
      const url = window.CLINIC_PATIENT_AJAX.deleteBaseUrl.replace('/0/', `/${patientId}/`);

      setDeleteLoading(true);

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        }
      })
      .then(async response => {
        const data = await response.json();
        if (!response.ok) {
          throw data;
        }
        return data;
      })
      .then(data => {
        const row = document.getElementById(`patient-row-${data.patient_id}`);
        if (row) row.remove();
        reindexPatientRows();
        deleteModal.hide();
        showListCompanyToast(data.message || 'Xóa thành công', 'success');
      })
      .catch(error => {
        showListCompanyToast(error.message || 'Xóa thất bại', 'danger');
      })
      .finally(() => {
        setDeleteLoading(false);
      });
    });
  }
}