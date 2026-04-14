function openModal(dateStr) {
    const modal = document.getElementById("slotModal");
    const label = document.getElementById("modal-date-label");
    const am = document.getElementById("check-am");
    const pm = document.getElementById("check-pm");
    const amLabel = document.getElementById("label-am");
    const pmLabel = document.getElementById("label-pm");
    const dateInput = document.getElementById("selected-date");

    modal.style.display = "flex";
    setTimeout(() => modal.classList.remove('hide'), 10);
     // Chuyển định dạng YYYY-MM-DD ➜ dd/mm/yyyy
    const dateParts = dateStr.split("-");
    if (dateParts.length === 3) {
        const [year, month, day] = dateParts;
        const formattedDate = `${day}/${month}/${year}`;
        label.innerText = "Đăng ký khám ngày " + formattedDate;
    } else {
        label.innerText = "Đăng ký khám";
    }
    dateInput.value = dateStr;  // truyền giá trị ngày

    am.value = `AM`;
    pm.value = `PM`;
    am.checked = false;
    pm.checked = false;

    // Lấy status slot từng ca
    let slotStatus = SLOT_STATUS && SLOT_STATUS[dateStr] ? SLOT_STATUS[dateStr] : {"am": 0, "pm": 0};

    // Ẩn/hiện label tương ứng
    if (amLabel) {
        if (slotStatus.am > 0) {
            amLabel.style.display = '';
            am.disabled = false;
        } else {
            amLabel.style.display = 'none';
            am.disabled = true;
        }
    }
    if (pmLabel) {
        if (slotStatus.pm > 0) {
            pmLabel.style.display = '';
            pm.disabled = false;
        } else {
            pmLabel.style.display = 'none';
            pm.disabled = true;
        }
    }

    // Nếu chỉ còn 1 ca mở, tự chọn luôn ca đó
    if (slotStatus.am > 0 && slotStatus.pm === 0) am.checked = true;
    if (slotStatus.pm > 0 && slotStatus.am === 0) pm.checked = true;
    
}

function closeModal() {
    const modal = document.getElementById('slotModal');
    modal.classList.add('hide');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 250); 
}

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("td.clickable").forEach(function (cell) {
        cell.addEventListener("click", function () {
            const dateStr = this.dataset.date;
            if (dateStr) openModal(dateStr);
        });
    });

    const modal = document.getElementById("slotModal");
    modal.addEventListener("click", function(event) { // chỉ đóng khi click vào modal-overlay
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeModal();
    });
});


// modal approve / delete contract
let deleteForm = null;
let approveForm = null;

document.addEventListener("click", function(e){

  if (e.target.classList.contains("btn-delete-contract")) {
      const form = e.target.closest("form");
      deleteForm = form;

      const company = e.target.dataset.company;
      document.getElementById("delete-company-name").textContent = company;

      const modal = new bootstrap.Modal(
          document.getElementById("deleteContractModal")
      );

      modal.show();
  }

  if (e.target.classList.contains("btn-approve-contract")) {
      const form = e.target.closest("form");
      approveForm = form;

      const company = e.target.dataset.company;
      document.getElementById("approve-company-name").textContent = company;

      const modal = new bootstrap.Modal(
          document.getElementById("approveContractModal")
      );

      modal.show();
  }

});

document.getElementById("confirm-delete-contract").addEventListener("click", function(){
    if (deleteForm) {
        deleteForm.submit();
    }
});

document.getElementById("confirm-approve-contract").addEventListener("click", function(){
    if (approveForm) {
        approveForm.submit();
    }
});

