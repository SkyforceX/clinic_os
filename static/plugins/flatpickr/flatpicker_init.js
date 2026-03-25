// Hàm khởi tạo flatpickr cho selector tùy chọn
function initFlatpickr(selector = ".date-picker") {
    flatpickr(selector, {
      dateFormat: "Y-m-d",      // định dạng gửi về Django
      altInput: true,           // hiển thị định dạng khác cho người dùng
      altFormat: "d/m/Y",       // hiển thị dd/mm/yyyy
      locale: flatpickr.l10ns.vn, // tiếng Việt
      allowInput: true,
      disableMobile: true,
      //maxDate: "today"          // (tùy chọn) chặn chọn ngày tương lai
    });
};

document.addEventListener("DOMContentLoaded", function () {
    // Ngăn khởi tạo trùng khi load lại nhiều lần (ví dụ HTMX / Turbo)
    if (window.__fpInit) return;
    window.__fpInit = true;
    initFlatpickr();
});


