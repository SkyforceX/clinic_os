document.addEventListener("DOMContentLoaded", function () {
  const topbarAccount = document.getElementById("topbar-account");
  const accountBtn    = document.getElementById("account-menu-btn");

  if (!topbarAccount || !accountBtn) return;

  // Toggle khi click vào nút tài khoản
  accountBtn.addEventListener("click", function (e) {
    e.stopPropagation(); // không lan ra document
    topbarAccount.classList.toggle("open");
  });

  // Click ra ngoài -> đóng menu
  document.addEventListener("click", function (e) {
    if (!topbarAccount.contains(e.target)) {
      topbarAccount.classList.remove("open");
    }
  });

  // Nhấn ESC -> đóng menu
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      topbarAccount.classList.remove("open");
    }
  });
});


function toggleSidebar(forceOpen = null) {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  if (!sidebar) return;

  const isMobile = window.matchMedia("(max-width: 1023px)").matches;

  if (isMobile) {
    // MOBILE: chỉ dùng active + overlay, không dùng collapsed/shifted
    const isOpen = sidebar.classList.contains("active");
    const nextOpen = (forceOpen === null) ? !isOpen : !!forceOpen;

    sidebar.classList.toggle("active", nextOpen);
    sidebar.classList.remove("collapsed");

    document.body.classList.toggle("sidebar-open", nextOpen);
    if (overlay) overlay.setAttribute("aria-hidden", nextOpen ? "false" : "true");
    return;
  }

  // DESKTOP: giữ cơ chế thu gọn (collapsed)
  const isCollapsed = sidebar.classList.contains("collapsed");
  sidebar.classList.toggle("collapsed", !isCollapsed);
  sidebar.classList.toggle("active", isCollapsed); // optional cho đúng logic cũ
}

// đóng khi bấm overlay / ESC
document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("sidebar-overlay");
  if (overlay) overlay.addEventListener("click", () => toggleSidebar(false));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") toggleSidebar(false);
  });
});



// chế độ darkmode
// const toggle = document.getElementById("darkModeToggle");
// toggle.addEventListener("change", function () {
//   document.body.classList.toggle("dark", this.checked);
// });

// ==== SUCCESS toast thông báo ==== //
function showSuccessToast(msg) {
  // Xóa toast cũ nếu có
  document.querySelectorAll('.custom-toast, .custom-toast-overlay').forEach(el => el.remove());

  // Tạo overlay
  const overlay = document.createElement('div');
  overlay.className = 'custom-toast-overlay';
  document.body.appendChild(overlay);

  // Tạo toast
  const toast = document.createElement('div');
  toast.className = 'custom-toast';
  toast.innerText = msg;
  document.body.appendChild(toast);

  // Hiện overlay và toast
  setTimeout(() => {
    overlay.classList.add('show');
    toast.classList.add('show');
  }, 10);

  setTimeout(() => {
    toast.classList.remove('show');
    overlay.classList.remove('show');
    setTimeout(() => {
      toast.remove();
      overlay.remove();
    }, 600);
  }, 1500); 
}

// ==== CUSTOM toast thông báo ==== //
function showCustomToast(msg) {
  // Xóa toast lỗi cũ nếu có
  document.querySelectorAll('.custom-toast, .custom-toast-overlay').forEach(el => el.remove());

  // Tạo overlay
  const overlay = document.createElement('div');
  overlay.className = 'custom-toast-overlay show';
  document.body.appendChild(overlay);

  // Tạo toast lỗi
  const toast = document.createElement('div');
  toast.className = 'custom-toast custom-toast--error show';
  toast.innerText = msg;
  document.body.appendChild(toast);

  // Đóng khi click ra ngoài (overlay)
  overlay.addEventListener('click', removeToast);
  // Đóng khi click vào chính toast
  toast.addEventListener('click', removeToast);

  function removeToast() {
    toast.classList.remove('show');
    overlay.classList.remove('show');
    setTimeout(() => {
      toast.remove();
      overlay.remove();
    }, 400);
  }
}



// Hàm loại bỏ dấu tiếng Việt
function removeVietnameseTones(str) {
    return str.normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "") // Remove diacritics
        .replace(/đ/g, "d").replace(/Đ/g, "D");
}

// Hàm lấy giá trị cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}