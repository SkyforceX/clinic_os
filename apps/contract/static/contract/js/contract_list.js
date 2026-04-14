document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.open-detail-modal').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const row = btn.closest('tr');
      document.getElementById('modalCompany').innerText = row.dataset.company;
      document.getElementById('modalContractNumber').innerText = row.dataset.contractNumber;
      document.getElementById('modalEmployee').innerText = row.dataset.employee;
      if (document.getElementById('modalBloodCollection'))
        document.getElementById('modalBloodCollection').innerText = row.dataset.bloodCollection || '';
      document.getElementById('modalStart').innerText = row.dataset.start;
      document.getElementById('modalEnd').innerText = row.dataset.end;
      if (document.getElementById('modalStatus'))
        document.getElementById('modalStatus').innerHTML = row.dataset.status || '';

      if (document.getElementById('modalEditLink'))
        document.getElementById('modalEditLink').href = row.dataset.editUrl;


      const modal = new bootstrap.Modal(document.getElementById('detailModal'));
      modal.show();
    });
  });
});
//-- JS modal danh sách hợp đồng -->
// -----------------------
//-- JS hiển thị modal upload bệnh nhân
document.addEventListener('DOMContentLoaded', function () {
  const uploadModalEl = document.getElementById('uploadPatientModal');
  const uploadModal = new bootstrap.Modal(uploadModalEl);

  document.querySelectorAll('.open-upload-modal-desktop, .open-upload-modal-mobile').forEach(button => {
    button.addEventListener('click', function (e) {
      e.preventDefault();
      
        // Lấy data trực tiếp từ chính button vừa click
        const companyId = this.getAttribute('data-company-id');
        const companyName = this.getAttribute('data-company-name');
        const contractId = this.getAttribute('data-contract-id');

        // Set thông tin công ty
        document.getElementById('modal-company-id').value = companyId;
        document.getElementById('modal-company-name').textContent = companyName;
        document.getElementById('create-company-id').value = companyId;


        // Gán link cho nút Sửa và Xóa trong modal
        document.getElementById('modalEditLink').href = `appointment/edit_${contractId}`;
        document.getElementById('modalDeleteLink').href = `appointment/delete_${contractId}`;

        // Reset form + hiển thị modal
        document.getElementById('uploadForm').reset();
        uploadModal.show();
        document.getElementById('upload-company-id').value = companyId;

        // Gọi AJAX lấy danh sách bệnh nhân
        const listContainer = document.getElementById('patientTableBody');
        listContainer.innerHTML = '<div class="text-center py-3">Đang tải danh sách...</div>';

        // "this" là button được click
        const apiUrl = this.dataset.apiUrl;

        // fetch patient list
        fetch(apiUrl, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          credentials: 'same-origin' // để mang cookie session, tránh bị redirect login
        })
        .then(async (res) => {
          const ct = res.headers.get('content-type') || '';
          const text = await res.text();

          // Nếu HTTP không OK, show lỗi
          if (!res.ok) {
            throw new Error(`HTTP ${res.status} — ${text.slice(0, 200)}`);
          }

          // Nếu server trả JSON đúng chuẩn
          if (ct.includes('application/json')) {
            try {
              return JSON.parse(text);
            } catch (e) {
              throw new Error(`JSON parse error: ${e.message}. Body: ${text.slice(0, 200)}`);
            }
          }

          // Nếu không phải JSON (có thể HTML trang login/lỗi)
          // Nhận diện trang login của Django (có form login) hoặc template HTML
          if (text.trim().startsWith('<')) {
            throw new Error('Server trả về HTML (có thể bị chuyển hướng tới trang đăng nhập hoặc lỗi 500).');
          }

          throw new Error('Server trả về dữ liệu không phải JSON.');
        })
      .then(data => {
          const tbody = document.getElementById('patientTableBody');
          tbody.innerHTML = ''; // Xóa dữ liệu cũ

          const btnUpload = document.getElementById('btn-upload-excel');

          const isPresent = (v) => {
            if (v === null || v === undefined) return false;
            const s = String(v).trim();
            if (s === '' || s.toLowerCase() === 'null' || s.toLowerCase() === 'undefined') return false;
            return true;
  };

          function renderPdfButton(type, iconClass, title, files, patient) {
              // files là mảng [{ file, visit_date, created_at }]
              if (!Array.isArray(files) || files.length === 0) return "";

              // files đã được backend sắp xếp desc theo visit_date
              return files.map((doc, idx) => {
                const url  = encodeURI(doc.file);
                const date = doc.visit_date ? ` (${doc.visit_date})` : "";
                const badge = files.length > 1 ? `<span class="badge rounded-pill ms-1">${idx+1}</span>` : "";
                return `
                  <button class="btn btn-light btn-icon view-pdf"
                    data-doc-id="${doc.id || ''}" 
                    data-ma-bn="${patient.ma_bn || ''}"
                    data-type="${type}"
                    data-path="${url}"
                    data-visit-date="${doc.visit_date || ''}"
                    title="${title} - ${patient.ho_ten || ''}${date}">
                    <i class="${iconClass}"></i>${badge}
                  </button>
                `;
              }).join("");
            }

            // ======= Main render =======
            if (data.patients && data.patients.length > 0) {
              data.patients.forEach((p, index) => {
                const row = document.createElement("tr");

                // tạo từng nhóm nút theo loại tài liệu
                const periodicBtn = renderPdfButton(
                  "periodic_book",
                  "fa-solid fa-file-medical",
                  "Sổ khám định kỳ",
                  p.periodic_book_files,
                  p
                );

                const bloodBtn = renderPdfButton(
                  "blood",
                  "fa-solid fa-vial",
                  "Kết quả xét nghiệm máu",
                  p.blood_files,
                  p
                );

                const imagingBtn = renderPdfButton(
                  "imaging",
                  "fa-solid fa-image",
                  "Kết quả chẩn đoán hình ảnh",
                  p.imaging_files,
                  p
                );

                // Gộp các nút lại
                const fileButtons = `${periodicBtn}${bloodBtn}${imagingBtn}`;

                // render từng cột
                row.innerHTML = `
                  <td class="text-center">${index + 1}</td>
                  <td class="text-center">${p.ma_bn || ""}</td>
                  <td>${p.ho_ten || ""}</td>
                  <td class="text-center">${p.gioi_tinh || ""}</td>
                  <td class="text-center">${p.ngay_sinh || ""}</td>
                  <td class="text-center">${p.phone || ""}</td>
                  <td class="text-center">${fileButtons}</td>
                `;

                tbody.appendChild(row);
              });
            // Nếu đã có danh sách BN, khóa nút upload
            if (btnUpload) btnUpload.disabled = true;
        } else {
            tbody.innerHTML = `<tr><td colspan="4" class="text-muted text-center">Danh sách trống</td></tr>`;
          // Nếu không có BN, mở lại nút upload
          if (btnUpload) btnUpload.disabled = false;
        }
      })
        .catch(err => {
          console.error(err);
          document.getElementById('patientTableBody').innerHTML = `<tr><td colspan="4" class="text-danger text-center">${err.me}</td></tr>`;
          // Nếu lỗi,  mở lại nút upload
          const btnUpload = document.getElementById('btn-upload-excel');
          if (btnUpload) btnUpload.disabled = false;
        });
    });
  });
});

// ----------------------------
// JS ajax lưu danh sách bệnh nhân từ file Excel
document.getElementById("uploadForm").addEventListener("submit", function (e) {
  e.preventDefault();

  const form = e.target;
  const formData = new FormData(form);
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const spinner = document.getElementById("uploadSpinner");

  // Show spinner
  spinner.classList.remove("d-none");

  fetch(AJAX_UPLOAD_URL, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken,
      "X-Requested-With": "XMLHttpRequest"
    },
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      spinner.classList.add("d-none"); // Hide spinner

      // 1. Chuyển focus trước khi đóng modal
      document.activeElement.blur();

      if (data.success) {
        // 1. Tắt modal
        const modalEl = document.getElementById("uploadPatientModal");
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        // 2. Cập nhật thông báo
        document.getElementById("toastMessage").innerText = data.message || "Tải lên thành công!";

        // 3. Hiện toast
        const toastElement = document.getElementById("uploadToast");
        const toast = new bootstrap.Toast(toastElement);
        toast.show();

        // 4. (Tùy chọn) Gọi lại hàm load danh sách bệnh nhân tại đây

      } else {
        let errMsg = data.error || "Có lỗi xảy ra!";
        // Nếu có details (danh sách dòng conflict), nối lại thành 1 chuỗi để alert
        if (data.details && data.details.length) {
          errMsg += "\n\n" + data.details.join("\n");
        }
        alert(errMsg);
      }
    })
    .catch(err => {
      spinner.classList.add("d-none"); // Hide spinner
      console.error(err);
      alert(err);
    });
});

//-- JS thêm mới 1 khách hàng thuộc công ty

document.addEventListener('DOMContentLoaded', function () {
  const createForm = document.getElementById('createPatientForm');
  if (!createForm) {
    console.error("Không tìm thấy form #createPatientForm");
    return;
  }

  createForm.addEventListener('submit', function (e) {
    e.preventDefault();

    const formData = new FormData(createForm);
    const csrfToken = formData.get('csrfmiddlewaretoken');
    const companyId = formData.get('company_id');

    console.log('Submitting form for company', companyId);

    fetch(AJAX_CREATE_PATIENT_URL, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
      },
      body: formData
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        // Cập nhật thông báo
        document.getElementById("toastMessage").innerText = data.message || "Tải lên thành công!";

        // Hiện toast
        const toastElement = document.getElementById("uploadToast");
        const toast = new bootstrap.Toast(toastElement);
        toast.show();

        createForm.reset();
      } else {
        alert('Lỗi: ' + (data.error || 'Không rõ nguyên nhân'));
        // Cập nhật thông báo
        document.getElementById("toastMessage").innerText = data.error || "Có lỗi xảy ra!";

        // Hiện toast
        const toastElement = document.getElementById("uploadToast");
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
      }
    })
    .catch(err => {
      console.error(err);
      alert('Có lỗi xảy ra khi thêm bệnh nhân: ' + err);
    });
  });
});



//-- JS websocket để cập nhật trạng thái hợp đồng

  // const socket = new WebSocket('ws://' + window.location.host + '/ws/contracts/');
  //
  // socket.onmessage = function(e) {
  //   const data = JSON.parse(e.data);
  //   if (data.type === 'approved') {
  //     const row = document.querySelector(`[data-contract-id="${data.contract_id}"]`);
  //     if (row) {
  //       row.querySelector('.status-cell').innerText = "Đã duyệt ✅";
  //     }
  //   }
  // }


//-- JS modal confirm delete
  document.addEventListener('DOMContentLoaded', function () {
    const deleteButtons = document.querySelectorAll('.btn-delete-confirm');
    const contractInfoEl = document.getElementById('contractInfo');
    const confirmBtn = document.getElementById('confirmDeleteBtn');

    deleteButtons.forEach(btn => {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const contractId = this.dataset.contractId;
        const contractNumber = this.dataset.contractNumber;
        const url = this.href;

        contractInfoEl.textContent = `#${contractNumber}`;
        confirmBtn.href = url;

        const modal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
        modal.show();
      });
    });
  });

