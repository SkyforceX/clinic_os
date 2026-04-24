// Global date picker initialization
// All input[type="date"] → flatpickr: hiển thị dd/mm/yyyy, submit Y-m-d về backend

var _FP_CFG = {
    dateFormat: "Y-m-d",
    altInput: true,
    altFormat: "d/m/Y",
    allowInput: true,
    disableMobile: true,
};

function _initOne(el) {
    if (!el || el._flatpickr) return;
    flatpickr(el, Object.assign({}, _FP_CFG, { locale: flatpickr.l10ns.vn }));
}

// Init tất cả input[type="date"] trong container (hoặc toàn trang)
function initAllDatePickers(container) {
    (container || document).querySelectorAll('input[type="date"]').forEach(_initOne);
}

// Dùng sau khi append row động (innerHTML hoặc cloneNode)
// Tự dọn flatpickr artifacts nếu row đến từ cloneNode
function reinitRowDatePickers(row) {
    row.querySelectorAll('.flatpickr-alt-input').forEach(function(el) { el.remove(); });
    row.querySelectorAll('.flatpickr-input').forEach(function(el) {
        if (el.type === 'hidden') {
            el.type = 'date';
            el.classList.remove('flatpickr-input');
        }
    });
    row.querySelectorAll('input[type="date"]').forEach(function(el) {
        flatpickr(el, Object.assign({}, _FP_CFG, { locale: flatpickr.l10ns.vn }));
    });
}

window.initAllDatePickers = initAllDatePickers;
window.reinitRowDatePickers = reinitRowDatePickers;

// Backward compat: initFlatpickr('.date-picker') vẫn hoạt động
window.initFlatpickr = function(selector) {
    if (selector) {
        document.querySelectorAll(selector).forEach(_initOne);
    } else {
        initAllDatePickers();
    }
};

document.addEventListener('DOMContentLoaded', function () {
    initAllDatePickers();
});
