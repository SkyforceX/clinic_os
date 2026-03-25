function slugify(str) {
  return str.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

// Lấy unique REPORT_NAME làm nhóm (phiếu) bên trái
function getUniqueGroups(reports) {
  const names = [];
  reports.forEach(r => {
    if (!names.includes(r.REPORT_NAME)) names.push(r.REPORT_NAME);
  });
  return names;
}

// Render danh sách phiếu bên trái
function renderLeft(groups) {
  let html = groups.map((name, idx) => `
    <div class="ehr-list-item${idx === 0 ? ' active' : ''}" data-group="${slugify(name)}">
      ${name}
    </div>
  `).join('');
  document.getElementById('ehr-list').innerHTML = html;
}

// Render dịch vụ bên phải cho group được chọn
function renderDetail(groupName, reports) {
  const groupReports = reports.filter(r => r.REPORT_NAME === groupName);

  if (groupReports.length === 0) {
    document.getElementById('ehr-detail').innerHTML = `<div class="ehr-empty">Không có dữ liệu.</div>`;
    return;
  }

  let html = `
    <div class="ehr-detail-title">${groupName}</div>
    <div class="ehr-detail-list">
      ${groupReports.map((r, idx) => `
        <div class="ehr-detail-row">
          <div class="ehr-service-name">${r.TENDICHVU || r.REPORT_NAME}</div>
          <button class="ehr-pdf-btn" data-url="${r.URLFILE}">Xem PDF</button>
        </div>
      `).join('')}
    </div>
  `;
  document.getElementById('ehr-detail').innerHTML = html;
}

//==================== RENDER PATIENT RECORD ===========================//
document.addEventListener('DOMContentLoaded', function() {
    // Hiện "Đang tải dữ liệu..." ngay khi load
  document.getElementById('ehr-detail').innerHTML = `<div class="ehr-empty">Đang tải dữ liệu...</div>`;
  // 1. Fetch API lấy báo cáo bệnh nhân
  fetch(API_PATIENT_RECORD_URL)
    .then(res => res.json())
    .then(data => {
      if (!data.success) {
        let errMsg = data.error
        document.getElementById('ehr-detail').innerHTML = `<div class="ehr-empty">Có lỗi xảy ra. Vui lòng liên hệ quản trị viên</div>`;
        // document.getElementById('ehr-detail').innerHTML = errMsg;
        return;
      }
      const reports = data.reports || [];
      if (!reports.length) {
        document.getElementById('ehr-detail').innerHTML = `<div class="ehr-empty">Không có dữ liệu.</div>`;
        return;
      }
      // 2. Render sidebar & detail
      const groups = getUniqueGroups(reports);
      renderLeft(groups);
      renderDetail(groups[0], reports);

      // 3. Chọn group (bên trái)
      document.getElementById('ehr-list').addEventListener('click', function(e) {
        const item = e.target.closest('.ehr-list-item');
        if (!item) return;
        document.querySelectorAll('.ehr-list-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        const groupName = groups.find(name => slugify(name) === item.getAttribute('data-group'));
        renderDetail(groupName, reports);
      });

      // 4. Xem PDF (ở cột phải)
      document.getElementById('ehr-detail').addEventListener('click', function(e) {
        if (e.target.classList.contains('ehr-pdf-btn')) {
          openPdfModal(e.target.getAttribute('data-url'));
        }
      });
    })
    .catch(err => {
      document.getElementById('ehr-detail').innerHTML = `<div class="ehr-empty">Có lỗi xảy ra. Vui lòng liên hệ quản trị viên</div>`;
      // document.getElementById('ehr-detail').innerHTML = err.message;
    });

  // Đóng modal khi click ra ngoài hoặc bấm X
  document.getElementById('pdf-modal-close').onclick = closePdfModal;
  document.getElementById('pdf-modal').addEventListener('click', function(e) {
    if (e.target === this) closePdfModal();
  });
});

// Xử lý modal PDF
function openPdfModal(url) {
  document.getElementById('pdf-frame').src = url;
  document.getElementById('pdf-modal').style.display = 'flex';
}

function closePdfModal() {
  document.getElementById('pdf-modal').style.display = 'none';
  document.getElementById('pdf-frame').src = "";
}

document.getElementById('pdf-modal-close').onclick = closePdfModal;

// Đóng modal khi click ra ngoài (nền tối)
document.getElementById('pdf-modal').addEventListener('click', function(e) {
  // Nếu click đúng vùng nền (không phải nội dung modal)
  if (e.target === this) {
    closePdfModal();
  }
});
