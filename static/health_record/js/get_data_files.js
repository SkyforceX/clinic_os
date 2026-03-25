// ====== DATA ======
const REPORTS = JSON.parse(document.getElementById('ehr-data').textContent || '[]');

// ====== DOM ======
const listEl   = document.getElementById('ehr-list');
const detailEl = document.getElementById('ehr-detail');
const modal    = document.getElementById('pdf-modal');
const pdfFrame = document.getElementById('pdf-frame');
const btnClose = document.getElementById('pdf-modal-close');

// ====== HELPERS ======
function openPdf(url, title){
  if(!url){
    alert('Không tìm thấy tệp để xem.');
    return;
  }
  pdfFrame.src = url + '#toolbar=1&navpanes=0&scrollbar=1';
  modal.style.display = 'flex';
  detailEl.scrollTop = 0;
}

function closePdf(){
  modal.style.display = 'none';
  pdfFrame.src = '';
}

btnClose.addEventListener('click', closePdf);
modal.addEventListener('click', (e)=>{ if(e.target === modal) closePdf(); });

// ====== RENDER ======
function renderListByType(type){
  // type: 'blood' | 'imaging' | 'periodic_book'

  const LABELS = {
    blood: 'Phiếu kết quả xét nghiệm máu',
    imaging: 'Phiếu kết quả chẩn đoán hình ảnh',
    periodic_book: 'Sổ khám sức khỏe định kỳ'
  };

  const label = LABELS[type] || 'Kết quả khám';

  if(!REPORTS.length){
    detailEl.innerHTML = `<div class="ehr-empty">Chưa có ${label.toLowerCase()}.</div>`;
    return;
  }

  // Lọc các bản ghi có URL đúng loại
  const urlKey = `${type}_url`;  // vd: blood_url, imaging_url, periodic_book_url
  const items = REPORTS
    .filter(it => it[urlKey])
    .sort((a,b) => (a.date_str < b.date_str ? 1 : -1)); // mới nhất trước

  if(!items.length){
    detailEl.innerHTML = `<div class="ehr-empty">Chưa có ${label.toLowerCase()}.</div>`;
    return;
  }

  const rows = items.map(it => {
    const url = it[urlKey];
    return `
      <div class="ehr-row">
        <div>
          <div><strong>${label}</strong></div>
          <small>${it.display_date}</small>
        </div>
        <div class="ehr-actions">
          <a href="#" class="btn btn-sm btn-outline-primary js-open" data-url="${url}">Xem PDF</a>
          <a href="${url}" class="btn btn-sm btn-outline-secondary" download>Tải xuống</a>
          <a href="${url}" class="btn btn-sm btn-outline-dark" target="_blank" rel="noopener">Mở tab mới</a>
        </div>
      </div>
    `;
  }).join('');

  detailEl.innerHTML = rows || `<div class="ehr-empty">Chưa có dữ liệu.</div>`;

  // Gắn sự kiện "Xem PDF"
  detailEl.querySelectorAll('.js-open').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      openPdf(a.dataset.url, label);
    });
  });
}

// ====== EVENTS ======
listEl.querySelectorAll('.ehr-list-item').forEach(item => {
  item.addEventListener('click', () => {
    const type = item.dataset.type; // 'blood' | 'imaging' | 'periodic_book'
    renderListByType(type);
  });
});
