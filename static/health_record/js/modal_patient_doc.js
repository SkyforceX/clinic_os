(function(){
  const RESULTS_BASE = (window.RESULTS_URL || "/data/results").replace(/\/+$/,"");

  function toResultUrl(pathOrUrl) {
    if (!pathOrUrl) return null;
    const s = String(pathOrUrl).trim();
    if (/^https?:\/\//i.test(s)) return s;     // absolute
    const rel = s.replace(/^\/+/, "");
    return `${RESULTS_BASE}/${rel}`;
  }

  // --- Cập nhật mapping doc_type mới ---
  function buildTitle(btn){
    const LABELS = {
      periodic_book: "Sổ khám sức khỏe định kỳ",
      blood: "Kết quả xét nghiệm máu",
      imaging: "Kết quả chẩn đoán hình ảnh"
    };
    const typeKey = (btn.dataset.type || "").trim(); // 'periodic_book' | 'blood' | 'imaging'
    const type = LABELS[typeKey] || "Kết quả khám";
    const name = btn.dataset.patientName || "";
    const date = btn.dataset.date || btn.dataset.year || "";
    return [type, name, date].filter(Boolean).join(" - ");
  }

  // Hàm kiểm tra file tồn tại (HEAD request)
  async function fileExists(url) {
    try {
      const res = await fetch(url, { method: "HEAD" });
      return res.ok;
    } catch (err) {
      console.warn("Kiểm tra file thất bại:", err);
      return false;
    }
  }

  // Hiển thị thông báo lỗi trong modal thay vì iframe (GIỮ NGUYÊN ĐỊNH DẠNG MODAL)
  function showError(message) {
    const body = document.querySelector("#pdfModal .modal-body");
    body.innerHTML = `
      <div class="d-flex flex-column justify-content-center align-items-center text-danger py-5">
        <i class="fa-solid fa-circle-exclamation fa-3x mb-3"></i>
        <p class="fs-5 fw-semibold">${message}</p>
      </div>
    `;
  }

  // Lấy CSRF
function getCookie(name) {
  const v = `; ${document.cookie}`;
  const parts = v.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

// Khôi phục iframe khi hiển thị PDF hợp lệ (GIỮ NGUYÊN ĐỊNH DẠNG MODAL)
function showIframe(url) {
    const body = document.querySelector("#pdfModal .modal-body");
    body.innerHTML = `<iframe id="pdfViewer" src="${url}" width="100%" height="100%" style="border:0;"></iframe>`;
}

const tbody = document.getElementById("patientTableBody");
if (!tbody) return;

const btnDelete = document.getElementById("btnDeleteDoc");
const modalEl = document.getElementById("pdfModal");
const modal = new bootstrap.Modal(modalEl);

// reset dataset mỗi lần mở
function setModalDocContext({ docId = "", url = "", btnEl = null } = {}) {
  modalEl.dataset.docId = docId;
  modalEl.dataset.url = url;
  // Lưu lại ref đến nút vừa bấm để xoá trên UI nếu xoá thành công
  modalEl._sourceBtn = btnEl || null;
}

tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest(".view-pdf");
    if (!btn) return;

    const raw = btn.dataset.url || btn.dataset.path || "";
    const url = btn.dataset.url ? raw : toResultUrl(raw);
    const docId = btn.dataset.docId || "";

    const titleEl = document.getElementById("pdfModalLabel");
    if (titleEl) titleEl.textContent = buildTitle(btn);

    if (!url) {
        showError("Không tìm thấy đường dẫn phiếu PDF.");
        modal.show();
        setModalDocContext({ docId: "", url: "", btnEl: null });
        return;
      }

    // Kiểm tra file có tồn tại không
    const exists = await fileExists(url);
    if (!exists) {
      showError("Không tìm thấy tệp PDF trên hệ thống. Phiếu có thể chưa được tải lên hoặc đã bị xóa.");
      modal.show();
      setModalDocContext({ docId, url: "", btnEl: btn });
      return;
    }

    // Nếu file hợp lệ → hiển thị iframe
    showIframe(url);
    setModalDocContext({ docId, url, btnEl: btn });
    modal.show();
});

// Bấm xoá
btnDelete.addEventListener("click", async () => {
  const docId = modalEl.dataset.docId;
  if (!docId) return;

  if (!confirm("Bạn có chắc muốn xoá phiếu này? Hành động không thể hoàn tác.")) return;

  try {
    const resp = await fetch(`/ehr/api/patient-docs/${docId}/delete/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || "Xoá thất bại");
    }
    // UI: ẩn modal, xoá nút PDF tương ứng
    modal.hide();
    const sourceBtn = modalEl._sourceBtn;
    if (sourceBtn) {
      sourceBtn.remove();
    }
    // (tuỳ chọn) nếu cột không còn nút nào, bạn có thể để lại thông báo
    // sourceBtn.closest('td').insertAdjacentHTML('beforeend', '<span class="text-muted">Không còn phiếu</span>');
  } catch (err) {
    alert("Lỗi xoá phiếu: " + (err.message || err));
  }
});

  // Dọn khi đóng (GIỮ NGUYÊN ĐỊNH DẠNG MODAL)
  document.getElementById("pdfModal").addEventListener("hidden.bs.modal", () => {
    const body = document.querySelector("#pdfModal .modal-body");
    body.innerHTML = `<div class="d-flex justify-content-center align-items-center text-muted py-5">
        <p class="mb-0">Đang tải...</p>
      </div>`;
  });
})();
