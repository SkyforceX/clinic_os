// ==== FILTER PATIENT LIST FORM COMPANY SELECT BOX ==== //
const companyFilter = document.getElementById("companyFilter");
const nameFilter = document.getElementById("nameFilter");
const codeFilter = document.getElementById("codeFilter");
const patientContainer = document.getElementById("patientContainer");
const syncPatientsNowBtn = document.getElementById("syncPatientsNowBtn");
const syncPatientsNowStatus = document.getElementById("syncPatientsNowStatus");

// helper active state khi chọn bệnh nhân trong danh sách
function setActivePatient(id) {
  document.querySelectorAll("#patientContainer .patient-item").forEach(function(el) {
    el.classList.toggle("active", el.id === "patient-" + id);
  });
}

let loadedPatients = [];
let currentPatientFetchController = null;
let patientSearchTimer = null;

// Tự động xác định form đang dùng dựa trên URL
let currentFormType = "dental";

const path = window.location.pathname;
if (path.includes("pathology-detail")) {
  currentFormType = "pathology_detail";
} else if (path.includes("pathology")) {
  currentFormType = "pathology";
} else if (path.includes("dental-exam")) {
  currentFormType = "dental";
}

function removeVietnameseTones(str) {
  return (str || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

function setPatientContainerMessage(msg, type) {
  if (!patientContainer) return;
  patientContainer.classList.remove("hidden");
  const icon = type === "danger"
    ? "fa-triangle-exclamation"
    : msg.includes("Đang tải")
    ? "fa-circle-notch fa-spin"
    : "fa-users-slash";
  patientContainer.innerHTML = `
    <div class="pl-empty">
      <i class="fa-solid ${icon}"></i>
      ${msg}
    </div>`;
  const countEl = document.getElementById("patientCount");
  if (countEl) countEl.textContent = "";
}

function setSyncPatientsStatus(message, tone) {
  if (!syncPatientsNowStatus) return;
  syncPatientsNowStatus.textContent = message || "";
  syncPatientsNowStatus.className = "small mt-2";
  if (tone === "success") {
    syncPatientsNowStatus.classList.add("text-success");
    return;
  }
  if (tone === "danger") {
    syncPatientsNowStatus.classList.add("text-danger");
    return;
  }
  syncPatientsNowStatus.classList.add("text-muted");
}

function hidePatientContainer() {
  if (!patientContainer) return;
  patientContainer.innerHTML = "";
  patientContainer.classList.add("hidden");
  const countEl = document.getElementById("patientCount");
  if (countEl) countEl.textContent = "";
}

function clearPatientList() {
  loadedPatients = [];
  if (patientContainer) {
    patientContainer.innerHTML = "";
  }
}

function renderPatients() {
  if (!patientContainer) return;

  patientContainer.classList.remove("hidden");
  patientContainer.innerHTML = "";
  const filtered = loadedPatients;

  if (!filtered.length) {
    setPatientContainerMessage("Không có bệnh nhân phù hợp.");
    return;
  }

  const countEl = document.getElementById("patientCount");
  if (countEl) countEl.textContent = filtered.length;

  filtered.forEach((p) => {
    const div = document.createElement("div");
    div.className = "patient-item";
    div.id = `patient-${p.id}`;
    div.style.cursor = "pointer";
    div.onclick = () => selectPatient(p.id, currentFormType);

    const isMale = (p.gioi_tinh || "").toLowerCase().includes("nam");

    div.innerHTML = `
      <div class="pi-name">
        ${p.ho_ten || ""}
      </div>
      <div class="pi-row">
        <span class="pi-gender ${isMale ? "pi-male" : "pi-female"}">
          <i class="fa-solid ${isMale ? "fa-mars" : "fa-venus"}"></i>
          ${p.gioi_tinh || ""}
        </span>
        <span class="pi-dob">
          <i class="fa-regular fa-calendar"></i> ${p.ngay_sinh || ""}
        </span>
      </div>
      <div class="pi-code">
        <i class="fa-solid fa-id-card"></i> ${p.ma_bn || ""}
      </div>
    `;

    patientContainer.appendChild(div);
  });
}

function fetchPatients() {
  if (!patientContainer || !window.CLINIC_PATIENT_AJAX) return;

  const nameQuery = (nameFilter?.value || "").trim();
  const codeQuery = (codeFilter?.value || "").trim();
  const companyId = (companyFilter?.value || "").trim();
  const combinedQuery = [nameQuery, codeQuery].filter(Boolean).join(" ").trim();

  if (!combinedQuery) {
    if (currentPatientFetchController) {
      currentPatientFetchController.abort();
      currentPatientFetchController = null;
    }
    clearPatientList();
    hidePatientContainer();
    return;
  }

  clearPatientList();

  let url = "";
  if (companyId) {
    url = (window.CLINIC_PATIENT_AJAX.getPatientsByCompanyUrl || "").replace(
      "/0/",
      `/${companyId}/`
    );
  } else {
    url = window.CLINIC_PATIENT_AJAX.getAllPatientsUrl || "";
  }

  if (!url) {
    setPatientContainerMessage("Không tìm thấy URL tải danh sách bệnh nhân.", "danger");
    return;
  }

  const params = new URLSearchParams();
  if (nameQuery) params.set("name", nameQuery);
  if (codeQuery) params.set("code", codeQuery);
  params.set("q", combinedQuery);
  url += (url.includes("?") ? "&" : "?") + params.toString();

  if (currentPatientFetchController) {
    currentPatientFetchController.abort();
  }
  currentPatientFetchController = new AbortController();

  setPatientContainerMessage("Đang tải danh sách bệnh nhân...");

  fetch(url, {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
    signal: currentPatientFetchController.signal,
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error("Không tải được danh sách bệnh nhân.");
      }
      return res.json();
    })
    .then((data) => {
      currentPatientFetchController = null;
      loadedPatients = data.patients || [];
      renderPatients();
    })
    .catch((error) => {
      currentPatientFetchController = null;
      if (error.name === "AbortError") {
        return;
      }
      console.error("fetchPatients error:", error);
      setPatientContainerMessage("Không tải được danh sách bệnh nhân.", "danger");
    });
}

function scheduleFetchPatients() {
  if (patientSearchTimer) {
    clearTimeout(patientSearchTimer);
  }
  patientSearchTimer = setTimeout(fetchPatients, 250);
}

function hasPatientSearchQuery() {
  return Boolean((nameFilter?.value || "").trim() || (codeFilter?.value || "").trim());
}

function syncPatientsNow() {
  const syncUrl = window.CLINIC_PATIENT_AJAX?.triggerHisSyncUrl || "";
  if (!syncUrl) {
    setSyncPatientsStatus("Không tìm thấy endpoint đồng bộ BN.", "danger");
    return;
  }

  const csrfToken = document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
  if (syncPatientsNowBtn) {
    syncPatientsNowBtn.disabled = true;
  }
  setSyncPatientsStatus("Đang đồng bộ bệnh nhân mới...", "muted");

  const body = new URLSearchParams();
  body.set("sync_type", "patients");
  body.set("run_inline", "true");

  fetch(syncUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      "X-CSRFToken": csrfToken,
    },
    body: body.toString(),
  })
    .then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.success === false) {
        throw new Error(data.error || data.message || "Không thể đồng bộ bệnh nhân.");
      }
      return data;
    })
    .then((data) => {
      setSyncPatientsStatus(data.message || "Đã đồng bộ bệnh nhân mới.", "success");
      if (hasPatientSearchQuery()) {
        fetchPatients();
      }
    })
    .catch((error) => {
      console.error("syncPatientsNow error:", error);
      setSyncPatientsStatus(error.message || "Đồng bộ bệnh nhân thất bại.", "danger");
    })
    .finally(() => {
      if (syncPatientsNowBtn) {
        syncPatientsNowBtn.disabled = false;
      }
    });
}

// Chọn công ty mới cho hiển thị danh sách
if (companyFilter) {
  companyFilter.addEventListener("change", () => {
    scheduleFetchPatients();
  });
}

if (nameFilter) {
  nameFilter.addEventListener("input", () => {
    scheduleFetchPatients();
  });
}

if (codeFilter) {
  codeFilter.addEventListener("input", () => {
    scheduleFetchPatients();
  });
}

function selectPatient(patient_id, form_type) {
  setActivePatient(patient_id);
  let url = "";

  if (form_type === "dental") {
    url = window.CLINIC_PATIENT_AJAX?.getDentalDataUrl?.replace("/0/", `/${patient_id}/`) || "";
  } else if (form_type === "pathology" || form_type === "pathology_detail") {
    url = window.CLINIC_PATIENT_AJAX?.getPathologyDataUrl?.replace("/0/", `/${patient_id}/`) || "";
  } else {
    alert("Loại form không hợp lệ.");
    return;
  }

  if (!url) {
    alert("Không tìm thấy URL tải dữ liệu bệnh nhân.");
    return;
  }

  fetch(url, {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Không tải được dữ liệu bệnh nhân.");
      }
      return response.json();
    })
    .then((result) => {
      if (result.status === "success" && result.data) {
        const data = result.data;

        // Điền thông tin hành chính chung
        const infoFields = {
          patient_id: data.patient_id,
          patient_code: data.patient_code,
          full_name: data.full_name,
          dob: data.dob,
          gender: data.gender,
        };

        Object.entries(infoFields).forEach(([key, value]) => {
          const el = document.getElementById(key) || document.querySelector(`[name="${key}"]`);
          if (el) {
            if ("value" in el) {
              el.value = value || "";
            } else {
              el.textContent = value || "";
            }
          }
        });

        if (form_type === "dental") {
          const dentalFields = {
            dental_exam_id: data.dental_exam_id,
            dental_exam_created_at: data.created_at_value,
            dental_exam_saved_at: data.latest_saved_at,
            other_oral_conditions: data.other_oral_conditions,
            chewing_ability: data.chewing_ability,
            conclusion: data.conclusion,
          };

          Object.entries(dentalFields).forEach(([key, value]) => {
            const el = document.getElementById(key) || document.querySelector(`[name="${key}"]`);
            if (el) {
              if ("value" in el) {
                el.value = value || "";
              } else {
                el.textContent = value || "";
              }
            }
          });

          // reset dữ liệu răng cũ trước khi gán lại
          document
            .querySelectorAll('input[name^="tooth_upper_"], input[name^="tooth_lower_"]')
            .forEach((input) => {
              input.value = "";
            });

          // Phân loại mất răng
          const missingTypeRadio = document.querySelectorAll('[name="missing_type"]');
          missingTypeRadio.forEach((r) => {
            r.checked = false;
          });

          const lossSelect = document.getElementById("missing_type");
          if (lossSelect) {
            lossSelect.value = data.loss_classification || "";
          }

          if (data.loss_classification) {
            missingTypeRadio.forEach((r) => {
              r.checked = r.value === data.loss_classification;
            });
          }

          // Phân loại sức khỏe răng miệng
          const healthSelect = document.getElementById("health_classification");
          if (healthSelect) {
            healthSelect.value = data.health_classification || "";
          }

          // Dữ liệu răng chi tiết
          if (data.tooth_details) {
            Object.entries(data.tooth_details).forEach(([fieldName, value]) => {
              const input = document.querySelector(`[name="${fieldName}"]`);
              if (input) input.value = value || "";
            });
          }
        }

        if (form_type === "pathology") {
          const selectedOption = companyFilter?.options?.[companyFilter.selectedIndex];
          const companyName = selectedOption?.dataset?.value || "";
          const companyInput = document.getElementById("company");
          if (companyInput) {
            companyInput.value = companyName;
          }
        }

        if (form_type === "pathology_detail" && data.results) {
          const container = document.getElementById("resultList");
          if (!container) return;

          container.innerHTML = "";

          data.results.forEach((r) => {
            const div = document.createElement("div");
            div.className = "mb-3";
            div.id = `evaluation_${r.id}`;

            let bgClass = "";
            if (r.evaluation === "normal") {
              bgClass = "bg-success bg-opacity-10 border border-success p-2 rounded transition-bg";
            } else if (r.evaluation === "follow") {
              bgClass = "bg-danger bg-opacity-10 border border-danger p-2 rounded transition-bg";
            }

            div.innerHTML = `
              <div class="card-body ${bgClass}" id="card_body_${r.id}">
                <p><strong>Vị trí lấy mẫu:</strong> ${r.location}</p>
                <p><strong>Ngày ra kết quả:</strong> ${r.result_date}</p>

                <div class="mb-3" id="evaluation_${r.id}">
                  <label class="me-3">
                    <input type="radio" name="eval_${r.id}" value="normal" ${r.evaluation === "normal" ? "checked" : ""}> Bình thường
                  </label>
                  <label>
                    <input type="radio" name="eval_${r.id}" value="follow" ${r.evaluation === "follow" ? "checked" : ""}> Theo dõi
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
        document.dispatchEvent(
          new CustomEvent("clinicalPatientDataLoaded", {
            detail: {
              formType: form_type,
              data: data,
            },
          })
        );
      } else {
        alert(result.message || "Không tìm thấy dữ liệu.");
      }
    })
    .catch((error) => {
      console.error("Lỗi khi tải dữ liệu bệnh nhân:", error);
      alert(error.message || "Lỗi khi tải dữ liệu bệnh nhân.");
    });
}

const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}T${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
const printDateEl = document.getElementById("printDate");
if (printDateEl) {
  printDateEl.value = today || "";
}

document.addEventListener("DOMContentLoaded", function () {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = "opacity 0.5s ease";
      alert.style.opacity = "0";
      setTimeout(() => alert.remove(), 500);
    }, 4000);
  });

  hidePatientContainer();
  setSyncPatientsStatus("Chỉ lấy dữ liệu BN mới nhất từ HIS.", "muted");

  if (syncPatientsNowBtn) {
    syncPatientsNowBtn.addEventListener("click", function () {
      syncPatientsNow();
    });
  }

  const btnSaveAndPrint = document.getElementById("btnSaveAndPrint");
  const btnSaveOnly = document.getElementById("btnSaveOnly");
  const dentalForm = document.getElementById("dental-exam-form");
  const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");

  if (btnSaveAndPrint && dentalForm && csrfInput) {
    btnSaveAndPrint.addEventListener("click", function (e) {
      e.preventDefault();

      const formData = new FormData(dentalForm);
      const csrfToken = csrfInput.value;

      fetch(API_SAVE_DENTAL_EXAM_URL, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            if (data.data && data.data.id) {
              const dentalExamIdInput = document.getElementById("dental_exam_id");
              if (dentalExamIdInput) {
                dentalExamIdInput.value = data.data.id;
              }
              const createdAtInput = document.getElementById("dental_exam_created_at");
              const savedAtInput = document.getElementById("dental_exam_saved_at");
              if (createdAtInput || savedAtInput) {
                const now = new Date();
                const yyyy = now.getFullYear();
                const mm = String(now.getMonth() + 1).padStart(2, "0");
                const dd = String(now.getDate()).padStart(2, "0");
                const hh = String(now.getHours()).padStart(2, "0");
                const mi = String(now.getMinutes()).padStart(2, "0");
                const ss = String(now.getSeconds()).padStart(2, "0");
                const stamp = `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
                if (createdAtInput && !createdAtInput.value) {
                  createdAtInput.value = stamp;
                }
                if (savedAtInput) {
                  savedAtInput.value = stamp;
                }
              }
              const printDateInput = document.getElementById("printDate");
              if (printDateInput && !printDateInput.value) {
                printDateInput.value = stamp.replace(" ", "T").slice(0, 16);
              }
            }
            in_phieu();
          } else {
            alert("❌ Lỗi khi lưu dữ liệu: " + (data.message || "Không xác định"));
          }
        })
        .catch((error) => {
          console.error("Lỗi in", error);
          alert("❌ Có lỗi khi lưu/in dữ liệu.");
        });
    });
  }

  if (btnSaveOnly && dentalForm && csrfInput) {
    btnSaveOnly.addEventListener("click", function (e) {
      e.preventDefault();

      const formData = new FormData(dentalForm);

      fetch(API_SAVE_DENTAL_EXAM_URL, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrfInput.value,
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            showSuccessToast("Lưu dữ liệu thành công");
            if (data.data && data.data.id) {
              const dentalExamIdInput = document.getElementById("dental_exam_id");
              if (dentalExamIdInput) {
                dentalExamIdInput.value = data.data.id;
              }
              const createdAtInput = document.getElementById("dental_exam_created_at");
              const savedAtInput = document.getElementById("dental_exam_saved_at");
              if (createdAtInput || savedAtInput) {
                const now = new Date();
                const yyyy = now.getFullYear();
                const mm = String(now.getMonth() + 1).padStart(2, "0");
                const dd = String(now.getDate()).padStart(2, "0");
                const hh = String(now.getHours()).padStart(2, "0");
                const mi = String(now.getMinutes()).padStart(2, "0");
                const ss = String(now.getSeconds()).padStart(2, "0");
                const stamp = `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
                if (createdAtInput && !createdAtInput.value) {
                  createdAtInput.value = stamp;
                }
                if (savedAtInput) {
                  savedAtInput.value = stamp;
                }
              }
              const printDateInput = document.getElementById("printDate");
              if (printDateInput && !printDateInput.value) {
                printDateInput.value = stamp.replace(" ", "T").slice(0, 16);
              }
            }
          } else {
            showCustomToast(data.message || "Lưu dữ liệu thất bại!");
          }
        })
        .catch((error) => {
          showCustomToast("Có lỗi kết nối server!");
          console.error(error);
        });
    });
  }

  initListCompanyPatientActions();
});

function in_phieu() {
  try {
    const hoTen = document.querySelector('[name="full_name"]')?.value || "";
    const maBN = document.querySelector('[name="patient_code"]')?.value || "";
    const ngaySinh = document.querySelector('[name="dob"]')?.value || "";
    const gioiTinh = document.querySelector('[name="gender"]')?.value || "";
    const missing_type = document.querySelector("#missing_type")?.value || "";
    const other_conditions = document.querySelector('[name="other_oral_conditions"]')?.value || "";
    const conclusion = document.querySelector('[name="conclusion"]')?.value || "";
    const sucNhai = document.querySelector('[name="chewing_ability"]')?.value || "";
    const health_classification = document.querySelector('[name="health_classification"]')?.value || "";
    
    const printDateInput = document.getElementById("printDate")?.value || "";
    const createdAtInput = document.getElementById("dental_exam_created_at")?.value || "";
    const latestSavedAtInput = document.getElementById("dental_exam_saved_at")?.value || "";
    function parseDbDateTime(value) {
      if (!value) return null;
      const parts = String(value).trim().split(/[- :]/);
      if (parts.length < 5) return null;
      const [year, month, day, hour, minute, second = "00"] = parts.map(Number);
      if ([year, month, day, hour, minute].some(Number.isNaN)) return null;
      return new Date(year, month - 1, day, hour, minute, Number.isNaN(second) ? 0 : second);
    }

    function formatPrintDate(dateObj) {
      const day = String(dateObj.getDate()).padStart(2, "0");
      const month = String(dateObj.getMonth() + 1).padStart(2, "0");
      const year = dateObj.getFullYear();
      const hour = String(dateObj.getHours()).padStart(2, "0");
      const minute = String(dateObj.getMinutes()).padStart(2, "0");
      return `${hour} giờ ${minute} phút, ngày ${day} tháng ${month} năm ${year}`;
    }

    const createdAt = parseDbDateTime(createdAtInput);
    const updatedAt = parseDbDateTime(latestSavedAtInput);
    const chosenDate = parseDbDateTime(printDateInput);
    const printDateSource = chosenDate || updatedAt || createdAt || new Date();
    printDateFormatted = formatPrintDate(printDateSource);

    const upperTeeth = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
    const lowerTeeth = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

    const printSection = document.getElementById("printSection");
    if (!printSection) {
      throw new Error("Không tìm thấy vùng in printSection.");
    }

    const printContent = printSection.cloneNode(true);

    const fullNameEl = printContent.querySelector(".js-print-fullname");
    const idEl = printContent.querySelector(".js-print-ID");
    const dobEl = printContent.querySelector(".js-print-dob");
    const genderEl = printContent.querySelector(".js-print-gender");
    const missingTypeEl = printContent.querySelector("#printMissing_type");
    const otherConditionsEl = printContent.querySelector("#printOther_conditions");
    const sucNhaiEl = printContent.querySelector("#printSucNhai");
    const healthClassEl = printContent.querySelector(".js-health-classification");
    const printDateTextEl = printContent.querySelector(".js-print-date");
    const conclusionEl = printContent.querySelector("#printConclusion");

    if (fullNameEl) fullNameEl.textContent = hoTen;
    if (idEl) idEl.textContent = maBN;
    if (dobEl) dobEl.textContent = ngaySinh;
    if (genderEl) genderEl.textContent = gioiTinh;
    if (missingTypeEl) missingTypeEl.textContent = missing_type;
    if (otherConditionsEl) otherConditionsEl.textContent = other_conditions;
    if (sucNhaiEl) sucNhaiEl.textContent = sucNhai ? `${sucNhai} %` : "";
    if (healthClassEl) healthClassEl.textContent = health_classification;
    if (printDateTextEl) printDateTextEl.textContent = printDateFormatted;
    if (conclusionEl) conclusionEl.textContent = conclusion;

    const signatureImg = printContent.querySelector("#signature-img");
    if (signatureImg) {
      const signatureSrc = (signatureImg.getAttribute("src") || "").trim();
      if (!signatureSrc) {
        signatureImg.classList.add("hidden");
      } else {
        signatureImg.classList.remove("hidden");
      }
    }

    const doctorNameEl = printContent.querySelector(".js-print-doctor-name");
    if (doctorNameEl) {
      const doctorName = (doctorNameEl.textContent || "").trim();
      const wrapper = doctorNameEl.closest(".signature-name");
      if (wrapper) {
        if (!doctorName) {
          wrapper.classList.add("hidden");
        } else {
          wrapper.classList.remove("hidden");
        }
      }
    }

    upperTeeth.forEach((tooth) => {
      const val = document.querySelector(`[name="tooth_upper_${tooth}"]`)?.value || "";
      const cell = printContent.querySelector(`#printTooth_${tooth}`);
      if (cell) cell.textContent = val;
    });

    lowerTeeth.forEach((tooth) => {
      const val = document.querySelector(`[name="tooth_lower_${tooth}"]`)?.value || "";
      const cell = printContent.querySelector(`#printTooth_${tooth}`);
      if (cell) cell.textContent = val;
    });

    const printFrame = document.createElement("iframe");
    printFrame.setAttribute("aria-hidden", "true");
    printFrame.style.position = "fixed";
    printFrame.style.right = "0";
    printFrame.style.bottom = "0";
    printFrame.style.width = "0";
    printFrame.style.height = "0";
    printFrame.style.border = "0";
    document.body.appendChild(printFrame);

    const frameWindow = printFrame.contentWindow;
    const frameDocument = frameWindow ? frameWindow.document : null;
    if (!frameWindow || !frameDocument) {
      if (printFrame.parentNode) {
        printFrame.parentNode.removeChild(printFrame);
      }
      throw new Error("Khong khoi tao duoc khung in.");
    }

    const cleanupPrintFrame = function () {
      if (printFrame.parentNode) {
        printFrame.parentNode.removeChild(printFrame);
      }
    };

    frameDocument.open();
    frameDocument.write(`
      <html>
      <head>
        <title>Phieu kham RHM</title>
        <link rel="stylesheet" href="${window.location.origin}/static/clinical/css/dental_print.css">
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
    frameDocument.close();

    printFrame.onload = function () {
      frameWindow.focus();
      frameWindow.print();
    };

    frameWindow.onafterprint = cleanupPrintFrame;
    setTimeout(cleanupPrintFrame, 60000);
  } catch (e) {
    alert("Đã xảy ra lỗi khi tạo phiếu in:\n" + e.message);
    console.error("Print error:", e);
  }
}

// xóa form khám
function clearDentalForm() {
  const container = document.querySelector(".js-form-container");
  if (!container) return;

  container.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach((el) => {
    el.value = "";
    el.classList.remove("highlight-nonzero", "highlight-empty");
  });

  container.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach((el) => {
    el.checked = false;
  });
}

// tự động điền tất cả input là 0
function fillMainComplainWithZero() {
  const mainComplainInputs = document.querySelectorAll('.js-complaint-table input[type="text"]');
  mainComplainInputs.forEach((input) => {
    input.value = "0";
  });
  updateInputHighlights();
}

// tự động điền giá trị vào input khi click vào các chú thích
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

      const wordRegex = /\S+/g;
      let match,
        closestWord = "",
        closestStart = -1,
        closestEnd = -1;

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
        const newVal =
          original.slice(0, closestStart).trimEnd() +
          " " +
          original.slice(closestEnd).trimStart();
        const newCursor = original.slice(0, closestStart).trimEnd().length + 1;
        activeInput.value = newVal.trim();
        activeInput.setSelectionRange(newCursor, newCursor);
      } else if (closestWord) {
        const newVal =
          original.slice(0, closestStart) + value + original.slice(closestEnd);
        const newCursor = closestStart + value.length;
        activeInput.value = newVal;
        activeInput.setSelectionRange(newCursor, newCursor);
      } else {
        const needsSpace = cursorPos > 0 && original[cursorPos - 1] !== " ";
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
      updateInputHighlights();
    });
  });
});

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

updateInputHighlights();

document.querySelectorAll(".complaint-table td input").forEach((input) => {
  input.addEventListener("input", updateInputHighlights);
});

// chỉ cho phép nhập các giá trị từ 1 đến 11, 11.1–11.4 hoặc √1, ngăn cách bằng dấu phẩy
function validateMainComplain(input) {
  const value = input.value.trim() || "";
  const allowedValues = [
    ...Array.from({ length: 11 }, (_, i) => (i + 1).toString()),
    ..."11.1,11.2,11.3,11.4".split(","),
    "√1",
  ];

  const values = value.split(",").map((v) => v.trim());

  const allValid = values.every((v) => allowedValues.includes(v));
  if (!allValid) {
    input.setCustomValidity("Chỉ nhập giá trị từ 1 đến 11, 11.1–11.4 hoặc √1.");
    input.reportValidity();
  } else {
    input.setCustomValidity("");
  }
}

// giới hạn nhập số từ 1 đến 100 cho sức nhai
function validateSucNhai(input) {
  let value = input.value || "";

  if (value.length > 3) {
    input.value = value.slice(0, 3);
    return;
  }

  const num = parseInt(value, 10);

  if (isNaN(num)) {
    input.setCustomValidity("Vui lòng nhập số hợp lệ từ 1 đến 100");
    input.reportValidity();
    return;
  }

  if (num > 100 || num < 1) {
    input.setCustomValidity("Chỉ được nhập số từ 1 đến 100");
    input.reportValidity();
  } else {
    input.setCustomValidity("");
  }
}

//###############################
// Cập nhật đánh giá kết quả (pathology_detail.html)
//###############################
function updateEvaluation(resultId) {
  const radios = document.getElementsByName(`eval_${resultId}`);
  const msgDiv = document.getElementById(`status_msg_${resultId}`);
  const cardBody = document.getElementById(`card_body_${resultId}`);

  let selectedValue = "";
  radios.forEach((r) => {
    if (r.checked) selectedValue = r.value || "";
  });

  if (!selectedValue) {
    msgDiv.innerHTML = `<div class="text-danger status-msg">⚠️ Vui lòng chọn một đánh giá.</div>`;
    setTimeout(() => {
      msgDiv.innerHTML = "";
    }, 3000);
    return;
  }

  msgDiv.innerHTML = `<div class="text-secondary">
    <span class="spinner-border spinner-border-sm me-1"></span>Đang cập nhật...
  </div>`;

  const updateUrl = window.CLINIC_PATIENT_AJAX?.updatePathologyEvaluationUrl || "update_pathology_evaluation/";

  fetch(updateUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      result_id: resultId,
      evaluation: selectedValue,
    }),
  })
    .then((res) => {
      if (!res.ok) throw new Error("Lỗi kết nối server");
      return res.json();
    })
    .then((data) => {
      if (data.status === "success") {
        msgDiv.innerHTML =
          selectedValue === "normal"
            ? `<div class="text-success status-msg">✔️ Đã cập nhật: <strong>Bình thường</strong></div>`
            : `<div class="text-danger status-msg">⚠️ Đã cập nhật: <strong>Theo dõi</strong></div>`;

        if (cardBody) {
          cardBody.classList.remove(
            "bg-success",
            "bg-danger",
            "border",
            "border-success",
            "border-danger",
            "bg-opacity-10"
          );

          if (selectedValue === "normal") {
            cardBody.classList.add("bg-success", "bg-opacity-10", "border", "border-success", "rounded", "p-2");
          } else {
            cardBody.classList.add("bg-danger", "bg-opacity-10", "border", "border-danger", "rounded", "p-2");
          }
        }
      } else {
        throw new Error(data.message || "Lỗi không xác định");
      }
    })
    .catch((err) => {
      msgDiv.innerHTML = `<div class="text-danger status-msg">❌ ${err.message}</div>`;
    })
    .finally(() => {
      setTimeout(() => {
        msgDiv.innerHTML = "";
      }, 3000);
    });
}

// js modal edit - delete - toast patient in list
function initListCompanyPatientActions() {
  const editModalEl = document.getElementById("editPatientModal");
  const deleteModalEl = document.getElementById("deletePatientModal");
  const editForm = document.getElementById("editPatientForm");
  const confirmDeleteBtn = document.getElementById("confirmDeletePatientBtn");

  if (!editModalEl || !deleteModalEl || !editForm || !window.CLINIC_PATIENT_AJAX) {
    return;
  }

  const editModal = new bootstrap.Modal(editModalEl);
  const deleteModal = new bootstrap.Modal(deleteModalEl);

  function clearEditErrors() {
    ["ma_bn", "ho_ten", "gioi_tinh", "ngay_sinh"].forEach((name) => {
      const input = document.getElementById(`edit_${name}`);
      const error = document.getElementById(`error_${name}`);
      if (input) input.classList.remove("is-invalid");
      if (error) error.textContent = "";
    });

    const generalError = document.getElementById("editPatientGeneralError");
    if (generalError) {
      generalError.classList.add("d-none");
      generalError.textContent = "";
    }
  }

  function setEditLoading(isLoading) {
    const btn = document.getElementById("savePatientBtn");
    if (!btn) return;

    const text = btn.querySelector(".js-btn-text");
    const spinner = btn.querySelector(".js-btn-spinner");

    btn.disabled = isLoading;
    if (spinner) spinner.classList.toggle("d-none", !isLoading);
    if (text) text.textContent = isLoading ? "Đang lưu..." : "Lưu thay đổi";
  }

  function setDeleteLoading(isLoading) {
    if (!confirmDeleteBtn) return;

    const text = confirmDeleteBtn.querySelector(".js-btn-text");
    const spinner = confirmDeleteBtn.querySelector(".js-btn-spinner");

    confirmDeleteBtn.disabled = isLoading;
    if (spinner) spinner.classList.toggle("d-none", !isLoading);
    if (text) text.textContent = isLoading ? "Đang xóa..." : "Xóa";
  }

  function showListCompanyToast(message, type = "success") {
    const toastEl = document.getElementById("listCompanyToast");
    const toastBody = document.getElementById("listCompanyToastBody");
    if (!toastEl || !toastBody) return;

    toastBody.textContent = message;
    toastEl.classList.remove("text-bg-success", "text-bg-danger", "text-bg-warning");
    toastEl.classList.add(
      type === "success" ? "text-bg-success" :
      type === "warning" ? "text-bg-warning" : "text-bg-danger"
    );

    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 3000 });
    toast.show();
  }

  function updatePatientRow(patient) {
    const row = document.getElementById(`patient-row-${patient.id}`);
    if (!row) return;

    row.querySelector(".patient-ma-bn").textContent = patient.ma_bn;
    row.querySelector(".patient-ho-ten").textContent = patient.ho_ten;
    row.querySelector(".patient-gioi-tinh").textContent = patient.gioi_tinh;

    const ngaySinhCell = row.querySelector(".patient-ngay-sinh");
    if (ngaySinhCell) {
      ngaySinhCell.textContent = patient.ngay_sinh;
      ngaySinhCell.dataset.date = patient.ngay_sinh_iso;
    }

    const editBtn = row.querySelector(".js-edit-patient-btn");
    if (editBtn) {
      editBtn.dataset.maBn = patient.ma_bn;
      editBtn.dataset.hoTen = patient.ho_ten;
      editBtn.dataset.gioiTinh = patient.gioi_tinh;
      editBtn.dataset.ngaySinh = patient.ngay_sinh_iso;
    }

    const deleteBtn = row.querySelector(".js-delete-patient-btn");
    if (deleteBtn) {
      deleteBtn.dataset.patientName = patient.ho_ten;
    }
  }

  function reindexPatientRows() {
    document.querySelectorAll("#patientTableBody tr").forEach((row, index) => {
      const sttCell = row.querySelector(".patient-stt");
      if (sttCell) sttCell.textContent = index + 1;
    });
  }

  document.addEventListener("click", function (e) {
    const editBtn = e.target.closest(".js-edit-patient-btn");
    if (editBtn) {
      clearEditErrors();

      document.getElementById("edit_patient_id").value = editBtn.dataset.patientId || "";
      document.getElementById("edit_ma_bn").value = editBtn.dataset.maBn || "";
      document.getElementById("edit_ho_ten").value = editBtn.dataset.hoTen || "";
      document.getElementById("edit_gioi_tinh").value = editBtn.dataset.gioiTinh || "";
      const ngaySinhEl = document.getElementById("edit_ngay_sinh");
      if (ngaySinhEl) {
        const dateVal = editBtn.dataset.ngaySinh || null;
        if (ngaySinhEl._flatpickr) {
          ngaySinhEl._flatpickr.setDate(dateVal, false);
        } else {
          ngaySinhEl.value = dateVal || "";
        }
      }

      editModal.show();
      return;
    }

    const deleteBtn = e.target.closest(".js-delete-patient-btn");
    if (deleteBtn) {
      document.getElementById("delete_patient_id").value = deleteBtn.dataset.patientId || "";
      document.getElementById("delete_patient_name").textContent = deleteBtn.dataset.patientName || "";
      deleteModal.show();
    }
  });

  editForm.addEventListener("submit", function (e) {
    e.preventDefault();
    clearEditErrors();
    setEditLoading(true);

    const patientId = document.getElementById("edit_patient_id").value;
    const formData = new FormData(editForm);
    const csrfToken = editForm.querySelector("[name=csrfmiddlewaretoken]").value;
    const url = window.CLINIC_PATIENT_AJAX.updateBaseUrl.replace("/0/", `/${patientId}/`);

    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: formData,
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) {
          throw data;
        }
        return data;
      })
      .then((data) => {
        updatePatientRow(data.patient);
        editModal.hide();
        showListCompanyToast(data.message || "Cập nhật thành công", "success");
      })
      .catch((error) => {
        if (error && error.errors) {
          Object.entries(error.errors).forEach(([field, message]) => {
            const input = document.getElementById(`edit_${field}`);
            const errorBox = document.getElementById(`error_${field}`);
            if (input) input.classList.add("is-invalid");
            if (errorBox) errorBox.textContent = message;
          });
        } else {
          const generalError = document.getElementById("editPatientGeneralError");
          if (generalError) {
            generalError.textContent = error.message || "Có lỗi xảy ra khi cập nhật.";
            generalError.classList.remove("d-none");
          }
          showListCompanyToast(error.message || "Cập nhật thất bại", "danger");
        }
      })
      .finally(() => {
        setEditLoading(false);
      });
  });

  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener("click", function () {
      const patientId = document.getElementById("delete_patient_id").value;
      const csrfToken =
        document.querySelector("#editPatientForm [name=csrfmiddlewaretoken]")?.value ||
        document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
        "";
      const url = window.CLINIC_PATIENT_AJAX.deleteBaseUrl.replace("/0/", `/${patientId}/`);

      setDeleteLoading(true);

      fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then(async (response) => {
          const data = await response.json();
          if (!response.ok) {
            throw data;
          }
          return data;
        })
        .then((data) => {
          const row = document.getElementById(`patient-row-${data.patient_id}`);
          if (row) row.remove();
          reindexPatientRows();
          deleteModal.hide();
          showListCompanyToast(data.message || "Xóa thành công", "success");
        })
        .catch((error) => {
          showListCompanyToast(error.message || "Xóa thất bại", "danger");
        })
        .finally(() => {
          setDeleteLoading(false);
        });
    });
  }
}

