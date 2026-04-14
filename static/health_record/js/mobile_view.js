  // DESKTOP: click danh sách trái
  (function attachDesktopList() {
    const listEl = document.getElementById('ehr-list');
    if (!listEl) return;
    listEl.querySelectorAll('.ehr-list-item').forEach(item => {
      item.addEventListener('click', () => {
        const type = item.dataset.type; // 'blood' | 'imaging' | 'periodic_book'
        renderListByType(type);
      });
    });
  })();

  // MOBILE: tabs
  (function attachMobileTabs() {
    const tabs = document.querySelectorAll('#ehr-mobile-tabs .nav-link');
    if (!tabs.length) return;

    const setActive = (btn) => {
      tabs.forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
    };

    tabs.forEach(btn => {
      btn.addEventListener('click', () => {
        setActive(btn);
        const type = btn.dataset.type; // 'blood' | 'imaging' | 'periodic_book'
        renderListByType(type);
        // auto scroll tới vùng kết quả trên mobile
        const detail = document.getElementById('ehr-detail');
        if (detail) detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    // Chọn mặc định tab "Máu"
    const first = document.querySelector('#ehr-mobile-tabs .nav-link[data-type="blood"]');
    if (first) first.click();
  })();

