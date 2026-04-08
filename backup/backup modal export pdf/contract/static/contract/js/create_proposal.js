document.addEventListener("DOMContentLoaded", function() {
  //**** select all
  function setAllCheckboxes(col, checked) {
    document.querySelectorAll('.service-check[data-col="'+col+'"]').forEach(cb => {
      if (!cb.disabled) cb.checked = checked;
    });
    // Gọi hàm tính tổng lại
    if (typeof updateTotal === "function") updateTotal();
  }
  document.querySelectorAll('.check-all').forEach(thCb => {
    thCb.addEventListener('change', function() {
      setAllCheckboxes(this.getAttribute('data-col'), this.checked);
    });
  });

  // Khi tick/untick từng checkbox, nếu tất cả checkbox trong cột đã được chọn, thì tick luôn "check-all"
  ["male", "female-single", "female-family"].forEach(col => {
    document.querySelectorAll('.service-check[data-col="'+col+'"]').forEach(cb => {
      cb.addEventListener("change", function() {
        const all = Array.from(document.querySelectorAll('.service-check[data-col="'+col+'"]'))
                          .filter(cb => !cb.disabled);
        const checked = all.filter(cb => cb.checked);
        const thCb = document.querySelector('.check-all[data-col="'+col+'"]');
        if (thCb) thCb.checked = all.length > 0 && checked.length === all.length;
        if (typeof updateTotal === "function") updateTotal();
      });
    });
  });

  //**** Tự động tính tổng cho từng đối tượng
  function formatNumber(n) {
    return n.toLocaleString('vi-VN');
  }
  function updateTotal() {
    let sumMale = 0, sumFemaleSingle = 0, sumFemaleFamily = 0;
    // Tổng NAM
    document.querySelectorAll('.cb-male:checked').forEach(cb => {
      let val = cb.getAttribute('data-price').replace(/[^\d]/g, '');
      if (val) sumMale += parseInt(val, 10);
    });
    // Tổng NỮ ĐỘC THÂN
    document.querySelectorAll('.cb-female-single:checked').forEach(cb => {
      let val = cb.getAttribute('data-price').replace(/[^\d]/g, '');
      if (val) sumFemaleSingle += parseInt(val, 10);
    });
    // Tổng NỮ GIA ĐÌNH
    document.querySelectorAll('.cb-female-family:checked').forEach(cb => {
      let val = cb.getAttribute('data-price').replace(/[^\d]/g, '');
      if (val) sumFemaleFamily += parseInt(val, 10);
    });
    // Cập nhật UI
    document.getElementById('total-male').innerText = formatNumber(sumMale);
    document.getElementById('total-female-single').innerText = formatNumber(sumFemaleSingle);
    document.getElementById('total-female-family').innerText = formatNumber(sumFemaleFamily);
  }

  // Gắn event cho từng checkbox đối tượng
  document.querySelectorAll('.cb-male, .cb-female-single, .cb-female-family').forEach(cb => {
    cb.addEventListener('change', updateTotal);
  });

  // Tính tổng ban đầu khi load trang
  updateTotal();

  //**** JS CẬP NHẬT ƯU ĐÃI MIỄN PHÍ - sau func updateTotal ****//
  document.querySelectorAll('.cb-uu-dai').forEach(function(cbUuDai) {
    cbUuDai.addEventListener('change', function() {
      let row = cbUuDai.getAttribute('data-row');
      ['male', 'female-single', 'female-family'].forEach(function(type) {
        let td = document.querySelector(`.price-${type}[data-row="${row}"]`);
        let cbObj = td ? td.querySelector('input[type="checkbox"]') : null;
        if (cbUuDai.checked) {
          // Ẩn, set checked, set value=0, hiện chữ Miễn phí
          if (cbObj) {
            cbObj.checked = true;
            cbObj.value = 0;
            cbObj.setAttribute('data-price', 0);  // cho JS tính tổng 
            cbObj.style.opacity = '0';
            cbObj.style.pointerEvents = "none";
          }
          if (td && !td.querySelector('.quote-cell-orange')) {
            let span = document.createElement('span');
            span.textContent = 'Miễn phí';
            span.className = 'text-mienphi'; // class để add/remove
            td.classList.add('quote-cell-orange');
            td.appendChild(span);
          }
        } else {
          // Hiện lại, bỏ checked, set value về gốc, xóa chữ Miễn phí
          if (cbObj) {
            cbObj.style.opacity = '';
            cbObj.style.pointerEvents = "";
            cbObj.checked = false;
            cbObj.value = cbObj.getAttribute('data-origin');
            cbObj.setAttribute('data-price', cbObj.getAttribute('data-origin')); // cho JS tính tổng
          }
          let span = td ? td.querySelector('.text-mienphi') : null;
          if (span) span.remove();
          td.classList.remove('quote-cell-orange');
        }
      });
      // *** GỌI updateTotal() SAU MỖI LẦN THAY ĐỔI ƯU ĐÃI ***
      updateTotal();
    });
  });
});

//**** AJAX LƯU BẢNG BÁO GIÁ ****//
// document.addEventListener("DOMContentLoaded", function() {
//   document.getElementById("quotation-form").addEventListener("submit", function(e) {
//   e.preventDefault(); 
//   // Thu thập thông tin khách hàng từ các input
//   const contact_name = document.getElementById('contact_name').value || '';
//   const company_name = document.getElementById('company_name').value || '';
//   const company_address = document.getElementById('company_address').value || '';
//   const quotation_id = document.getElementById('quotation_id').value || '';

//   // Thu thập dịch vụ
//   let services = [];
//   let currentGroup = "";
//   document.querySelectorAll("tbody tr").forEach(row => {
//     if (row.classList.contains("quote-row-group")) {
//         // Nhóm mới, cập nhật group hiện tại
//         currentGroup = row.querySelector("span")?.textContent.trim() || "";
//     }
//     if (row.classList.contains("service-row")) {
//       let id = row.getAttribute("data-service-id");
//       let item_name = row.querySelector(".item-name")?.textContent.trim() || "";
//       let description = row.querySelector(".item-desc")?.textContent.trim() || "";
//       let price = row.querySelector(".cb-male")?.dataset.price || "0";
//       if (!price || isNaN(price) || price === "{}") price = "0";
//       let checked_male = row.querySelector('input[data-col="male"]')?.checked || false;
//       let checked_female_single = row.querySelector('input[data-col="female-single"]')?.checked || false;
//       let checked_female_family = row.querySelector('input[data-col="female-family"]')?.checked || false;

//       // Chỉ push dịch vụ có ít nhất 1 đối tượng được check (nếu muốn)
//       if (checked_male || checked_female_single || checked_female_family) {
//         services.push({
//           id,
//           group_name: currentGroup,
//           item_name,
//           description,
//           price,
//           checked_male,
//           checked_female_single,
//           checked_female_family,
//         });
//       }
//     }
//   });

//   // Kiểm tra có chọn dịch vụ nào không
//   if (services.length == 0) {
//     document.getElementById("save-result").innerHTML = "<span style='color:red'>Vui lòng chọn ít nhất 1 dịch vụ!</span>";
//     return;
//   }

//   // Gửi AJAX
//   fetch("{% url 'contract:save_quotation' %}", {
//     method: "POST",
//     headers: {
//       "Content-Type": "application/json",
//       "X-CSRFToken": "{{ csrf_token }}",
//     },
//     body: JSON.stringify({
//       quotation_id: quotation_id, contact_name, company_name, company_address, services
//     })
//   })
//   .then(res => res.json())
//   .then(data => {
//     if (data.success) {
//       // Show Bootstrap toast
//       var toastEl = document.getElementById('successToast');
//       var toast = new bootstrap.Toast(toastEl, { delay: 2200 });
//       document.getElementById('toastMessage').textContent = "Đã lưu báo giá thành công!";
//       toast.show();
//       // show btn xem báo giá
//       document.getElementById("view-quotation-wrap").disabled = false;
//       // gán quotation ID cho btn xuất pdf
//       document.getElementById("quotation_id").value = data.quotation_id;
//     } else {
//       // show toast báo lỗi
//       var toastEl = document.getElementById('successToast');
//       var toast = new bootstrap.Toast(toastEl, { delay: 3000 });
//       document.getElementById('toastMessage').textContent = "Có lỗi: " + data.error;
//       toastEl.classList.remove('bg-success');
//       toastEl.classList.add('bg-danger');
//       toast.show();
//       // Đổi lại màu thành công nếu lưu lại lần khác
//       toastEl.classList.remove('bg-danger');
//       toastEl.classList.add('bg-success');
//     }
//   })
//   .catch(err => {
//     var toastEl = document.getElementById('successToast');
//     var toast = new bootstrap.Toast(toastEl, { delay: 3000 });
//     document.getElementById('toastMessage').textContent = err;
//     toastEl.classList.remove('bg-success');
//     toastEl.classList.add('bg-danger');
//     toast.show();
//     toastEl.classList.remove('bg-danger');
//     toastEl.classList.add('bg-success');
//   });
//   });
// });