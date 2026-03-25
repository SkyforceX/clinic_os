document.addEventListener('DOMContentLoaded', function () {
  const formEl = document.querySelector('form.needs-validation');
  const ajaxUrl = formEl.dataset.ajaxUrl; // đã có trong form: data-ajax-url="..."
  const companySel = document.getElementById('id_company');

  // khi prefill patient, TomSelect sẽ nhận option sẵn trong HTML
  const patientTom = new TomSelect('#id_patient', {
    valueField: 'id',
    labelField: 'text',
    searchField: ['text','patient_code','name','dob'], // tìm theo nhiều trường
    openOnFocus: true,
    preload: 'focus',          // gọi load() khi focus lần đầu
    create: false,
    persist: false,
    loadThrottle: 250,         // debounce
    // Cho phép load ngay sau khi có company
    shouldLoad: function(query) {
      return !!companySel.value;
    },

    load: function (query, callback) {
      const companyId = companySel.value;
      if (!companyId) return callback(); // chưa chọn công ty -> không gọi

      // Không gõ gì thì vẫn load full:
      const url = `${ajaxUrl}?company_id=${encodeURIComponent(companyId)}&q=${encodeURIComponent(query||'')}`;
      fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}})
        .then(r => r.json())
        .then(data => callback(data.results || []))
        .catch(() => callback());
    }
  });

  // Khi đổi công ty -> clear patient & reset
  companySel.addEventListener('change', function () {
    patientTom.clear(true);       // xóa value
    patientTom.clearOptions();    // xóa danh sách cũ
    patientTom.disable();
    if (this.value) {
      patientTom.enable();
      // => dành cho trigger load top:
      // patientTom.load('');
    }
  });

  // Trạng thái ban đầu
  if (!companySel.value) {
    patientTom.disable();
    patientTom.settings.placeholder = '--- Chọn công ty trước ---';
    patientTom.updatePlaceholder();
  }
});



// document.addEventListener("DOMContentLoaded", function () {
//   const companySel  = document.getElementById("id_company");
//   const patientSel  = document.getElementById("id_patient");
//   // lấy url fetch từ form
//   const formEl     = document.querySelector("form[data-ajax-url]");
//   const ajaxUrl    = formEl?.dataset.ajaxUrl;
//
//   if (!ajaxUrl || !companySel || !patientSel) return;
//
//   // Giữ option trống đầu tiên
//   function setPlaceholder(selectEl, text) {
//     selectEl.innerHTML = "";
//     const opt = document.createElement("option");
//     opt.value = "";
//     opt.textContent = text;
//     selectEl.appendChild(opt);
//   }
//
//   function disableAndClear(selectEl, placeholder) {
//     setPlaceholder(selectEl, placeholder);
//     selectEl.disabled = true;
//     selectEl.setAttribute("aria-disabled", "true");
//   }
//
//   function enableAndFill(selectEl, items, placeholder) {
//     setPlaceholder(selectEl, placeholder);
//     items.forEach(it => {
//       const o = document.createElement("option");
//       o.value = it.id;
//       o.textContent = it.text;
//       selectEl.appendChild(o);
//     });
//     selectEl.disabled = false;
//     selectEl.removeAttribute("aria-disabled");
//   }
//
//   // auto-load khi tự fill company
//   function loadPatients(companyId) {
//     if (!companyId) {
//       disableAndClear(patientSel, "--- Chọn công ty trước ---");
//       return;
//     }
//     disableAndClear(patientSel, "Đang tải...");
//     fetch(`${ajaxUrl}?company_id=${encodeURIComponent(companyId)}`, {
//       headers: {"X-Requested-With": "XMLHttpRequest"}
//     })
//     .then(r => r.json())
//     .then(data => {
//       enableAndFill(patientSel, data.results, "--- Chọn khách hàng ---");
//       // (tuỳ chọn) nếu muốn tự chọn lại patient cũ sau khi reload:
//       const prev = patientSel.getAttribute("data-prev"); // bạn có thể set trong template
//       if (prev) patientSel.value = prev;
//     })
//     .catch((error) => {
//         console.error("Fetch error:", error);
//         alert(error.message);
//       disableAndClear(patientSel, "Lỗi tải danh sách");
//     });
//   }
//
//   // 1) Trạng thái ban đầu
//   if (!companySel.value) {
//     // chưa chọn company -> disable patient
//     disableAndClear(patientSel, "--- Chọn công ty trước ---");
//   } else {
//     // đã được prefill sau redirect:
//     // chỉ auto-fetch nếu patient hiện chưa có danh sách (<= 1 option placeholder)
//     if (patientSel.options.length <= 1) {
//       loadPatients(companySel.value);
//     }
//     // nếu form bound error từ server đã render sẵn danh sách -> không fetch lại
//   }
//
//   // 2) Khi user đổi công ty -> fetch lại
//   companySel.addEventListener("change", function () {
//     loadPatients(this.value);
//   });
// });